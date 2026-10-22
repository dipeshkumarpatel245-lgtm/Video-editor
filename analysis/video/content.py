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


def _frame_style(img: np.ndarray) -> dict:
    """Return per-frame style summary in normalized form."""
    img = np.asarray(img, dtype=np.float64) / 255.0
    mean_rgb = img.reshape(-1, 3).mean(axis=0)
    r, g, b = mean_rgb
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    sat = 0.0 if luma <= 1e-6 else float(np.sqrt((r - luma) ** 2 + (g - luma) ** 2 + (b - luma) ** 2) / (luma + 1e-6))
    temp = float(r - b)
    contrast = float(img.std())
    edge = 0.0
    if img.ndim == 3:
        edge = (
            np.abs(np.diff(img[..., 0], axis=0)).mean()
            + np.abs(np.diff(img[..., 0], axis=1)).mean() / max(1, img.shape[1])
        )
    return {
        "brightness": float(np.clip(luma, 0.0, 1.0)),
        "contrast": float(np.clip(contrast, 0.0, 1.0)),
        "saturation": float(np.clip(sat, 0.0, 1.5)),
        "temperature": float(np.clip(temp, -1.0, 1.0)),
        "edge_density": float(np.clip(edge, 0.0, 1.0)),
        "mean_rgb": [float(np.clip(x, 0.0, 1.0)) for x in mean_rgb.tolist()],
    }


def shot_feature(frames: np.ndarray, shot: dict, fps: float) -> dict:
    """Feature vector + tags for one shot, with a richer style profile for matching."""
    s = int(round(shot["start"] * fps))
    e = max(s + 1, int(round(shot["end"] * fps)))
    seg = frames[s:e]
    if len(seg) == 0:
        return {
            "feature": None,
            "tags": ["empty"],
            "brightness": 0.5,
            "motion": 0.0,
            "contrast": 0.1,
            "saturation": 0.5,
            "temperature": 0.0,
            "edge_density": 0.0,
            "mean_rgb": [0.5, 0.5, 0.5],
        }

    f = seg.astype(np.float64) / 255.0
    mean_bright = f.mean()

    n = min(len(seg), 5)
    idx = np.linspace(0, len(seg) - 1, n, dtype=int)
    feats = []
    style_values = []
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
        style_values.append(_frame_style(img))
    feature = np.mean(feats, axis=0)
    feature /= (np.linalg.norm(feature) + 1e-8)

    d = np.abs(np.diff(f, axis=0)).mean() if len(seg) > 1 else 0.0
    grad = np.abs(np.diff(f[..., 0], axis=0)).mean() + np.abs(np.diff(f[..., 0], axis=1)).mean() / (seg.shape[2] or 1)

    mean_style = {
        "brightness": float(np.mean([v["brightness"] for v in style_values])) if style_values else 0.5,
        "contrast": float(np.mean([v["contrast"] for v in style_values])) if style_values else 0.1,
        "saturation": float(np.mean([v["saturation"] for v in style_values])) if style_values else 0.5,
        "temperature": float(np.mean([v["temperature"] for v in style_values])) if style_values else 0.0,
        "edge_density": float(np.mean([v["edge_density"] for v in style_values])) if style_values else 0.0,
        "mean_rgb": [
            float(np.mean([v["mean_rgb"][0] for v in style_values])) if style_values else 0.5,
            float(np.mean([v["mean_rgb"][1] for v in style_values])) if style_values else 0.5,
            float(np.mean([v["mean_rgb"][2] for v in style_values])) if style_values else 0.5,
        ],
    }

    tags = []
    if mean_bright < 0.3:
        tags.append("dark")
    elif mean_bright > 0.7:
        tags.append("bright")
    if f.std() < 0.08:
        tags.append("low_contrast")
    if d > 0.05:
        tags.append("motion")
    if grad < 0.02:
        tags.append("flat")
    else:
        tags.append("textured")
    if mean_style["saturation"] > 0.8:
        tags.append("high_sat")
    if mean_style["temperature"] > 0.12:
        tags.append("warm")
    elif mean_style["temperature"] < -0.12:
        tags.append("cool")

    return {
        "feature": [round(float(x), 6) for x in feature],
        "tags": tags,
        "brightness": round(float(mean_bright), 4),
        "motion": round(float(d), 4),
        "contrast": round(float(f.std()), 4),
        "saturation": round(float(mean_style["saturation"]), 4),
        "temperature": round(float(mean_style["temperature"]), 4),
        "edge_density": round(float(mean_style["edge_density"]), 4),
        "mean_rgb": [round(float(x), 4) for x in mean_style["mean_rgb"]],
    }


__all__ = ["shot_feature"]
