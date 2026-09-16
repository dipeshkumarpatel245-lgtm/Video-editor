"""Loudness analysis: EBU R128 integrated via ffmpeg summary + moment-by-moment RMS curve (numpy)."""
from __future__ import annotations
import re
import numpy as np
from scipy.io import wavfile


def _integrated_from_ffmpeg(wav_path: str) -> tuple[float | None, float | None]:
    try:
        from ffutils import run
        cp = run(["ffmpeg", "-hide_banner", "-i", wav_path,
                  "-af", "ebur128=metadata=1", "-f", "null", "-"], timeout=120)
        log = (cp.stderr or b"").decode("utf-8", errors="replace")
    except Exception as e:
        return None, None
    m_i = re.search(r"I:\s*([-\d.]+)\s*LUFS", log)
    m_l = re.search(r"LRA:\s*([\d.]+)\s*LU", log)
    i = float(m_i.group(1)) if m_i else None
    lra = float(m_l.group(1)) if m_l else None
    return i, lra


def _rms_curve(path: str, hop_ms: float = 100.0) -> tuple[list[dict], int]:
    sr, data = wavfile.read(path)
    if data.dtype.kind == "i":
        data = data.astype(np.float64) / np.iinfo(data.dtype).max
    if data.ndim > 1:
        data = data.mean(axis=1)
    hop = int(sr * hop_ms / 1000)
    n = len(data)
    curve = []
    t = 0.0
    i = 0
    while i < n:
        seg = data[i:i + hop]
        rms = float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0
        db = 20.0 * np.log10(rms + 1e-9)
        curve.append({"t": round(t, 3), "db": round(db, 2)})
        t += hop_ms / 1000.0
        i += hop
    return curve, int(sr)


def _annotate_curve(curve: list[dict]) -> list[dict]:
    """Mark silent / speech-like / music-like segments from dB."""
    for c in curve:
        db = c["db"]
        if db < -45:
            c["label"] = "silence"
        elif db < -28:
            c["label"] = "quiet"
        elif db < -18:
            c["label"] = "medium"
        else:
            c["label"] = "loud"
    return curve


def analyze_loudness(wav_path: str) -> dict:
    integrated, lra = _integrated_from_ffmpeg(wav_path)
    curve, sr = _rms_curve(wav_path)
    curve = _annotate_curve(curve)
    return {
        "integrated_lufs": integrated,
        "lra": lra,
        "curve": curve,
        "sample_rate": sr,
    }