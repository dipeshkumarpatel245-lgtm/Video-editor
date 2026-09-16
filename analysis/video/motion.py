"""Camera-motion estimation via phase correlation and frame-difference statistics."""
from __future__ import annotations
import numpy as np
from .shots import _luminance, _read_frames_raw
from config import ANALYSIS_FPS


def phase_shift(img1: np.ndarray, img2: np.ndarray) -> tuple[float, float]:
    """Estimate translation (dx,dy) between two grayscale images via phase correlation."""
    f1 = np.fft.fft2(img1.astype(np.float64))
    f2 = np.fft.fft2(img2.astype(np.float64))
    cc = np.fft.ifft2(f1 * np.conj(f2))
    peak = np.unravel_index(np.argmax(np.abs(cc)), cc.shape)
    dy = peak[0] if peak[0] < img1.shape[0] // 2 else peak[0] - img1.shape[0]
    dx = peak[1] if peak[1] < img1.shape[1] // 2 else peak[1] - img1.shape[1]
    return float(dx), float(dy)


def _estimate_zoom(img1: np.ndarray, img2: np.ndarray) -> float:
    """Estimate scale factor via log-polar spectral magnitude ratio."""
    m1 = np.abs(np.fft.fft2(img1.astype(np.float64)))
    m2 = np.abs(np.fft.fft2(img2.astype(np.float64)))
    # radial profile: compare energy at outer vs inner ring
    h, w = m1.shape
    Y, X = np.ogrid[:h, :w]
    R = np.sqrt((X - w / 2) ** 2 + (Y - h / 2) ** 2)
    r_max = min(h, w) // 2
    inner = R < r_max * 0.3
    outer = (R > r_max * 0.3) & (R < r_max * 0.8)
    e1_inner = m1[inner].mean() + 1e-6
    e1_outer = m1[outer].mean() + 1e-6
    e2_inner = m2[inner].mean() + 1e-6
    e2_outer = m2[outer].mean() + 1e-6
    ratio1 = e1_outer / e1_inner
    ratio2 = e2_outer / e2_inner
    scale = (ratio2 / ratio1)
    # >1 means more high-freq (zoom out / sharper), <1 means zoom in (blurrier)
    # map to zoom direction
    return float(np.clip(np.log2(scale), -2, 2))


def _gray_frames(frames: np.ndarray) -> np.ndarray:
    """Per-frame 2D luma images, shape (N,H,W)."""
    rgb = frames.astype(np.float64)
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def analyze_motion(video: str) -> dict:
    """
    Returns per-shot motion summary:
    {
      shots: [{
        idx, pan_x, pan_y, pan_mag, zoom_delta, shake,
        classification: "static"|"pan"|"zoom_in"|"zoom_out"|"handheld"|"dynamic"
      }]
    }
    """
    frames, real_fps, n_frames = _read_frames_raw(video)
    if n_frames < 3:
        return {"shots": []}

    dxs, dys, zooms = [], [], []
    g = _gray_frames(frames)

    for i in range(1, n_frames):
        f1 = g[i - 1]
        f2 = g[i]
        dx, dy = phase_shift(f1, f2)
        dxs.append(dx)
        dys.append(dy)
        zooms.append(_estimate_zoom(f1, f2))

    dxs = np.array(dxs)
    dys = np.array(dys)
    zooms = np.array(zooms)
    step = 1.0 / ANALYSIS_FPS
    times = np.arange(1, n_frames) * step

    # classify segments by running windows
    # simple approach: per-frame class, aggregate per shot? We'll do whole-video stats
    # then split per shot later
    return {
        "per_frame": [{
            "t": round(float(times[i]), 4),
            "dx": round(float(dxs[i]), 3),
            "dy": round(float(dys[i]), 3),
            "zoom": round(float(zooms[i]), 4),
        } for i in range(len(times))],
        "global": {
            "pan_mag": round(float(np.sqrt(np.mean(dxs ** 2 + dys ** 2))), 4),
            "pan_x_mean": round(float(dxs.mean()), 4),
            "pan_y_mean": round(float(dys.mean()), 4),
            "zoom_mean": round(float(zooms.mean()), 4),
            "zoom_std": round(float(zooms.std()), 4),
            "shake": round(float(np.sqrt(np.mean(np.diff(dxs) ** 2 + np.diff(dys) ** 2))), 4),
        },
    }