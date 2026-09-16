"""Color-grade analysis: estimate per-shot look, detect filters, and export a 3D LUT."""
from __future__ import annotations
import numpy as np
from config import ANALYSIS_FPS, ANALYSIS_WIDTH, EXPORT_LUT_SIZE


def _extract_shot_means(frames: np.ndarray, shot: dict, fps: float) -> tuple[np.ndarray, dict]:
    """Average RGB + variance stats for a shot."""
    s = int(round(shot["start"] * fps))
    e = max(s + 1, int(round(shot["end"] * fps)))
    seg = frames[s:e]
    if len(seg) == 0:
        return np.zeros(3), {}
    f = seg.astype(np.float64) / 255.0
    mean_rgb = f.mean(axis=(0, 1, 2))
    var = f.std(axis=(0, 1, 2))
    r, g, b = mean_rgb
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    sat = 0 if luma <= 1e-6 else np.sqrt((r - luma) ** 2 + (g - luma) ** 2 + (b - luma) ** 2) / (luma + 1e-6)
    # temperature proxy: warm=red-heavy vs blue
    temp = (r - b)  # + warm, - cool
    stats = {
        "luma": round(float(luma), 4),
        "sat": round(float(sat), 4),
        "temp": round(float(temp), 4),
        "variance": [round(float(x), 4) for x in var],
    }
    return mean_rgb, stats


def make_lut_from_matrix(mat: np.ndarray, size: int = EXPORT_LUT_SIZE) -> str:
    """Build a .cube LUT string from a 3x3 color matrix + bias."""
    n = size
    steps = np.linspace(0, 1, n)
    lines = [f"LUT_3D_SIZE {n}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1", ""]
    for ia in range(n):
        for ib in range(n):
            for ic in range(0, n, 2 if n >= 17 else 1):  # keep size sane
                rgb = np.array([steps[ia], steps[ib], steps[ic]])
                out = mat @ rgb
                out = np.clip(out, 0, 1)
                lines.append(f"{out[0]:.6f} {out[1]:.6f} {out[2]:.6f}")
    return "\n".join(lines)


def analyze_color(frames: np.ndarray, shots: list[dict], fps: float = ANALYSIS_FPS) -> dict:
    """Analyze grade; returns per-shot look + global grade matrix + LUT bytes."""
    shot_colors = []
    collected = []
    for sh in shots:
        mean_rgb, stats = _extract_shot_means(frames, sh, fps)
        collected.append(mean_rgb)
        shot_colors.append({"idx": sh["idx"], **stats, "mean_rgb": [round(float(x), 4) for x in mean_rgb]})

    # global direction: how far frames sit from neutral -> approximate grade matrix
    m = np.mean(collected, axis=0) if collected else np.array([0.5, 0.5, 0.5])
    # neutrality: typical grade drives means away from mid-gray depending on tone
    target = np.array([m.mean()] * 3)  # pull toward neutral-gamma axis
    scale = np.clip(np.linalg.det(np.diag(np.clip(target / np.clip(m, 1e-4, None), 0.6, 1.4))), 0.5, 2.0)
    grade = np.diag(target / np.clip(m, 1e-4, None))
    grade = np.clip(grade, 0.4, 2.0)

    global_is = {
        "matrix": [round(float(x), 4) for x in grade.ravel()],
        "lut": make_lut_from_matrix(grade),
    }

    # classifier helpers available to caller
    def _classify(stats: dict) -> list[str]:
        tags = []
        if stats["sat"] < 0.15:
            tags.append("bw")
        elif stats["sat"] > 0.9:
            tags.append("high_sat")
        if stats["temp"] > 0.12:
            tags.append("warm")
        elif stats["temp"] < -0.12:
            tags.append("cool")
        if stats["luma"] < 0.25:
            tags.append("dark")
        elif stats["luma"] > 0.75:
            tags.append("bright")
        return tags

    for s in shot_colors:
        s["tags"] = _classify(s)

    return {"shots": shot_colors, "global": global_is}