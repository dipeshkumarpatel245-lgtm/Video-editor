"""Detect significant sound events via onset envelope peaks.

The detector surfaces all local maxima above a robust adaptive threshold.
Downstream fusion (or ML-backed detectors) can filter events that coincide with
the beat grid to isolate off-beat sound effects (impacts, risers, whooshes).
"""
from __future__ import annotations
import numpy as np
from scipy.ndimage import median_filter
from .beats import load_audio_mono, onset_envelope


def detect_sound_events(wav_path: str) -> list[dict]:
    sr, audio = load_audio_mono(wav_path)
    env, hop_sec = onset_envelope(audio, sr)

    if len(env) < 5:
        return []

    # robust baseline via median filter over 0.5s window (odd size)
    win = max(3, int(0.5 / hop_sec) | 1)
    med = median_filter(env, size=win)
    diff = env - med
    # local max detection for peaks
    threshold = float(np.percentile(env[env > 0], 80)) if (env > 0).any() else 0
    threshold = max(threshold, 1.0)
    prev_cross = -100
    events = []
    for i in range(1, len(env) - 1):
        if diff[i] <= 0:
            continue
        if env[i] < threshold:
            continue
        # local max in env (not diff) within ±2 frames
        is_max = env[i] >= env[i - 1] and env[i] >= env[i + 1]
        if not is_max:
            continue
        dt = (i - prev_cross) * hop_sec
        if dt < 0.15:
            continue
        t = i * hop_sec
        # width: frames where diff stays > 20% of peak diff
        peak = diff[i]
        width = 0.0
        for j in range(i + 1, len(diff)):
            if diff[j] < peak * 0.2:
                width = (j - i) * hop_sec
                break
        # classify by width
        if width < 0.12:
            etype = "impact"
        elif width > 0.35:
            etype = "riser"
        else:
            etype = "hit"
        strength = float(env[i])
        events.append({"t": round(t, 4),
                       "type": etype,
                       "strength": round(strength, 2),
                       "width": round(width, 4)})
        prev_cross = i
    return events