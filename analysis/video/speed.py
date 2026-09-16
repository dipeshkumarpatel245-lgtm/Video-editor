"""Speed / time-effects detection: freeze frames, pacing, fast-motion."""
from __future__ import annotations
import numpy as np
from .shots import _read_frames_raw, _luminance
from config import ANALYSIS_FPS


def detect_speed(video: str) -> dict:
    """Detect freezes, overall pacing, and rhythm profile."""
    frames, real_fps, n_frames = _read_frames_raw(video)
    if n_frames < 3:
        return {"freezes": [], "pacing": "static", "avg_motion": 0.0}

    luma = _luminance(frames) * 255
    diffs = np.abs(np.diff(luma))
    thr = 0.002  # freeze when frames nearly identical

    # freeze frame detection
    freeze_mask = diffs < thr
    freezes = []
    i = 0
    min_freez = int(0.25 * ANALYSIS_FPS)  # >= 250ms
    while i < len(freeze_mask):
        if freeze_mask[i]:
            j = i
            while j < len(freeze_mask) and freeze_mask[j]:
                j += 1
            if j - i >= min_freez:
                freezes.append({
                    "start": round(i / ANALYSIS_FPS, 4),
                    "end": round(j / ANALYSIS_FPS, 4),
                    "duration": round((j - i) / ANALYSIS_FPS, 4),
                })
            i = j
        else:
            i += 1

    avg_motion = float(diffs.mean())
    if avg_motion > 0.020:
        pacing = "fast"
    elif avg_motion > 0.006:
        pacing = "medium"
    else:
        pacing = "slow"

    return {
        "freezes": freezes,
        "pacing": pacing,
        "avg_motion": round(avg_motion, 5),
        "fps_estimate": real_fps,
    }