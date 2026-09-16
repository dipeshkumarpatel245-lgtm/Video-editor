"""Lightweight content features per shot (color layout + edge histograms).

When OpenCLIP / torch is available (GPU deployments, VT_USE_OCR or a custom
hook) these can be replaced by vision embeddings; this module stays dependency-free.
"""
from __future__ import annotations
import numpy as np
from config import ANALYSIS_FPS


def _hist(data: np.ndarray, bins: int = 16) -> np.ndarray:
    data = np.asarray(data, dtype=np.float64)
    data = data[np.isfinite(data)]
    h, _ = np.histogram(data, bins=bins, range=(0, 1))
    s = h.sum()
    return h / s if s > 0 else np.zeros(bins)


def shot_feature(frames: np.ndarray, shot: dict, fps: float) -> dict:
    """Feature vector + tags for one shot."""
    s = int(round(shot["start"] * fps))
    e = max(s + 1, int(round(shot["end"] * fps)))
    seg = frames[s:e]
    if len(seg) == 0:
        return {"feature": None, "tags": ["empty"], "brightness": 0.5, "motion": 0.0}

    f = seg.astype(np.float64) / 255.0
    mean_bright = f.mean()

    # color histogram (3x downweighted spatial layout)
    n = min(len(seg), 5)
    idx = np.linspace(0, len(seg) - 1, n, dtype=int)
    feats = []
    for i in idx:
        img = seg[i]
        r, g, b = img[..., 0], img[..., 1], img[..., 2]
        y = 0.2126 * r + 0.7152 * g + 0.0722 * b
        u = (b - y) * 0.492
        v = (r - y) * 0.877
        feats.append(np.concatenate([
            _hist(y, 12),
            _hist(u, 8),
            _hist(v, 8),
        ]))
    feature = np.mean(feats, axis=0)
    feature /= (np.linalg.norm(feature) + 1e-8)

    # motion within shot (avg inter-frame RGB diff)
    d = np.abs(np.diff(f, axis=0)).mean() if len(seg) > 1 else 0.0

    # edge texture indicator (first-order diff energy)
    grad = np.abs(np.diff(f[..., 0], axis=0)).mean() + np.abs(np.diff(f[..., 0], axis=1)).mean() / (seg.shape[2] or 1)

    # coarse tags from brightness/motion
    tags = []
    if mean_bright < 0.3:
        tags.append("dark")
    elif mean_bright > 0.7:
        tags.append("bright")
    if grey := (f.std() < 0.08):
        tags.append("low_contrast")
    if d > 0.05:
        tags.append("motion")
    if grad < 0.02:
        tags.append("flat")
    else:
        tags.append("textured")

    return {
        "feature": [round(float(x), 6) for x in feature],
        "tags": tags,
        "brightness": round(float(mean_bright), 4),
        "motion": round(float(d), 4),
        "contrast": round(float(f.std()), 4),
    }