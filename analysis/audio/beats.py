"""Detect beats and tempo using spectral-flux onset envelope + DP beat tracking."""
from __future__ import annotations
import numpy as np
from scipy.io import wavfile
from scipy.ndimage import uniform_filter1d
from config import SAMPLE_RATE, TEMPO_LOW, TEMPO_HIGH


def load_audio_mono(path: str) -> tuple[float, np.ndarray]:
    sr, data = wavfile.read(path)
    if data.dtype.kind == "i":
        data = data.astype(np.float64) / np.iinfo(data.dtype).max
    elif data.dtype.kind == "u":
        data = data.astype(np.float64) / np.iinfo(data.dtype).max
    if data.ndim > 1:
        data = data.mean(axis=1)
    return float(sr), data


# ---- onset envelope ----

def spectral_flux(stft_mag: np.ndarray) -> np.ndarray:
    """Rectified spectral flux from STFT magnitude."""
    diff = np.diff(stft_mag, axis=0, prepend=stft_mag[:1])
    return np.clip(diff, 0, None).sum(axis=1)


def onset_envelope(audio: np.ndarray, sr: float, hop_ms: float = 10.0) -> tuple[np.ndarray, float]:
    hop = int(sr * hop_ms / 1000)
    n_fft = 1024
    window = np.hanning(n_fft + 1)[:-1]
    n_frames = max(1, (len(audio) - n_fft) // hop + 1)
    mags = np.zeros((n_frames, n_fft // 2 + 1))
    for i in range(n_frames):
        start = i * hop
        seg = audio[start:start + n_fft]
        if len(seg) < n_fft:
            seg = np.pad(seg, (0, n_fft - len(seg)))
        mags[i] = np.abs(np.fft.rfft(seg * window))
    env = spectral_flux(mags)
    env = np.maximum(env, 0)
    env = uniform_filter1d(env, size=3)
    hop_sec = hop / sr
    return env, hop_sec


# ---- tempo estimation ----

def tempo_from_onset(onset: np.ndarray, hop_sec: float, lo: int = TEMPO_LOW, hi: int = TEMPO_HIGH) -> float:
    """Autocorrelation-based tempo estimation within [lo,hi] BPM."""
    n = len(onset)
    n_lag_max = int(60.0 / lo / hop_sec)
    n_lag_min = max(1, int(60.0 / hi / hop_sec))
    corrs = []
    lags = np.arange(n_lag_min, min(n_lag_max, n // 2))
    if len(lags) == 0:
        return 120.0
    onset_c = onset - onset.mean()
    for lag in lags:
        corrs.append(np.dot(onset_c[:n - lag], onset_c[lag:n]) / n)
    corrs = np.array(corrs)
    best = lags[np.argmax(corrs)]
    return float(round(60.0 / (best * hop_sec), 1))


# ---- beat tracking (DP / Ellis 2007) ----

def beat_track(onset: np.ndarray, hop_sec: float, tempo: float) -> np.ndarray:
    """Estimate beat phase via a comb template, then snap each beat to the nearest onset peak."""
    period = 60.0 / tempo
    period_frames = period / hop_sec
    n = len(onset)
    if period_frames < 2 or n < int(period_frames) * 2:
        return np.arange(0, n) * hop_sec

    # comb filter: best offset/phase by scanning a coarse grid of phases
    phases = np.arange(0, 2 * np.pi, np.pi / 12.0)
    probs = np.zeros(len(phases))
    comb = np.zeros(n)
    for p_i, ph in enumerate(phases):
        # build template: spikes at phase + k*period
        grid = np.arange(ph, ph + 2 * np.pi * (n // int(period_frames)), 2 * np.pi)
        idx = np.minimum((grid * period_frames / (2 * np.pi)).astype(int), n - 1)
        tpl = np.zeros(n)
        tpl[idx] = 1.0
        probs[p_i] = np.dot(tpl, onset) / (tpl.sum() + 1e-6)
    best_ph = phases[np.argmax(probs)]

    first_frame = int(best_ph * period_frames / (2 * np.pi))
    grid_frames = np.arange(first_frame, n, int(round(period_frames))) if period_frames > 2 else np.arange(first_frame, n, 1)
    # refine: snap each grid position to local onset max within +/- 0.25*period
    snap = int(max(1, round(period_frames * 0.25)))
    beats = []
    for g in grid_frames:
        lo, hi = max(0, g - snap), min(n, g + snap + 1)
        if lo < hi:
            best_local = lo + int(np.argmax(onset[lo:hi]))
        else:
            best_local = g
        beats.append(best_local * hop_sec)
    return np.array(sorted(set(beats)))


def _detect_beats_local(env: np.ndarray, hop_sec: float) -> dict:
    """Onset-envelope tracker (autocorrelation tempo + comb phase + peak snap)."""
    tempo = tempo_from_onset(env, hop_sec)
    beats = beat_track(env, hop_sec, tempo)
    # beat strength: interpolate onset envelope at beat times
    times_f = np.arange(len(env)) * hop_sec
    strength = np.interp(beats, times_f, env)
    st_med = float(np.median(strength)) if len(strength) else 0
    energy = ["high" if s > 1.5 * st_med else "normal" for s in strength]
    return {
        "tempo": round(tempo, 2),
        "bpm": round(tempo, 2),
        "beats": [{"t": round(float(t), 4), "strength": round(float(s), 4), "energy": e}
                  for t, s, e in zip(beats, strength, energy)],
    }


def _detect_beats_librosa(sr: float, audio: np.ndarray, env: np.ndarray, hop_sec: float) -> dict | None:
    """DP beat tracker via librosa (mel onset envelope, Ellis-style backtrack)."""
    import librosa
    tempo, beat_frames = librosa.beat.beat_track(y=audio, sr=float(sr), trim=False)
    if beat_frames is None or len(beat_frames) == 0:
        return None
    t = float(tempo.item()) if hasattr(tempo, "item") else float(tempo)
    bt = librosa.frames_to_time(beat_frames, sr=float(sr))
    times_f = np.arange(len(env)) * hop_sec
    strength = np.interp(bt, times_f, env)
    st_med = float(np.median(strength)) if len(strength) else 0
    energy = ["high" if s > 1.5 * st_med else "normal" for s in strength]
    return {
        "tempo": round(t, 2),
        "bpm": round(t, 2),
        "beats": [{"t": round(float(b), 4), "strength": round(float(s), 4), "energy": e}
                  for b, s, e in zip(bt, strength, energy)],
    }


def detect_beats(wav_path: str) -> dict:
    """Full beat detection pipeline; returns beats + tempo + strength.

    Uses librosa (DP beat tracker) when available, otherwise the built-in
    pure-numpy onset tracker. Near-silent audio yields tempo=None / no beats.
    """
    sr, audio = load_audio_mono(wav_path)
    env, hop_sec = onset_envelope(audio, sr)

    # silent / near-silent input -> no meaningful beat structure
    if len(env) == 0 or float(np.max(env)) < 1e-6:
        return {"tempo": None, "bpm": None, "beats": []}

    try:
        res = _detect_beats_librosa(sr, audio, env, hop_sec)
        if res is not None:
            return res
    except Exception:
        pass
    return _detect_beats_local(env, hop_sec)