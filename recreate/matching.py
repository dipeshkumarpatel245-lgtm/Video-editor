"""Analyze custom clips and match them to template slots with high-fidelity style matching."""
from __future__ import annotations

import os

import numpy as np
from scipy.optimize import linear_sum_assignment

from analysis.probe import probe
from analysis.video.shots import _read_frames_raw
from config import ANALYSIS_FPS


def _style_profile(obj: dict | None) -> dict:
    """Return a normalized style signature for template shots or clip metadata."""
    if not obj:
        return {
            "brightness": 0.5,
            "contrast": 0.1,
            "saturation": 0.5,
            "temperature": 0.0,
            "edge_density": 0.1,
            "motion": 0.0,
            "mean_rgb": [0.5, 0.5, 0.5],
        }
    content = obj.get("content") or obj.get("style") or {}
    color = obj.get("color") or {}
    motion = obj.get("motion") or {}
    rgb = color.get("mean_rgb") or content.get("mean_rgb") or [0.5, 0.5, 0.5]
    return {
        "brightness": float(np.clip(content.get("brightness", color.get("luma", 0.5)), 0.0, 1.0)),
        "contrast": float(np.clip(content.get("contrast", 0.1), 0.0, 1.0)),
        "saturation": float(np.clip(content.get("saturation", color.get("sat", 0.5)), 0.0, 1.5)),
        "temperature": float(np.clip(content.get("temperature", color.get("temp", 0.0)), -1.0, 1.0)),
        "edge_density": float(np.clip(content.get("edge_density", 0.1), 0.0, 1.0)),
        "motion": float(np.clip(content.get("motion", motion.get("shake", motion.get("motion", 0.0))), 0.0, 1.0)),
        "mean_rgb": [float(np.clip(x, 0.0, 1.0)) for x in rgb[:3]],
    }


def _style_similarity(a: dict, b: dict) -> float:
    """Similarity in [0, 1] for style resemblance between template and clip."""
    brightness = 1.0 - min(1.0, abs(a["brightness"] - b["brightness"]))
    contrast = 1.0 - min(1.0, abs(a["contrast"] - b["contrast"]))
    saturation = 1.0 - min(1.0, abs(a["saturation"] - b["saturation"]))
    temperature = 1.0 - min(1.0, abs(a["temperature"] - b["temperature"]))
    edge = 1.0 - min(1.0, abs(a["edge_density"] - b["edge_density"]))
    motion = 1.0 - min(1.0, abs(a["motion"] - b["motion"]))
    rgb_diff = np.linalg.norm(np.asarray(a["mean_rgb"]) - np.asarray(b["mean_rgb"])) / np.sqrt(3.0)
    rgb = 1.0 - min(1.0, rgb_diff)
    return float(np.clip(
        0.23 * brightness + 0.12 * contrast + 0.18 * saturation + 0.15 * temperature
        + 0.10 * edge + 0.10 * motion + 0.12 * rgb,
        0.0, 1.0,
    ))


def _neighbor_style(template: dict, shot_index: int) -> dict:
    """Average style of a shot and its immediate neighbors for continuity-aware matching."""
    shots = template.get("shots") or []
    if not shots:
        return {"brightness": 0.5, "contrast": 0.1, "saturation": 0.5,
                "temperature": 0.0, "edge_density": 0.1, "motion": 0.0,
                "mean_rgb": [0.5, 0.5, 0.5]}
    ids = [shot_index]
    for off in (-1, 1):
        j = shot_index + off
        if 0 <= j < len(shots):
            ids.append(j)
    style_values = [_style_profile(shots[i]) for i in ids]
    return {
        "brightness": float(np.mean([s["brightness"] for s in style_values])),
        "contrast": float(np.mean([s["contrast"] for s in style_values])),
        "saturation": float(np.mean([s["saturation"] for s in style_values])),
        "temperature": float(np.mean([s["temperature"] for s in style_values])),
        "edge_density": float(np.mean([s["edge_density"] for s in style_values])),
        "motion": float(np.mean([s["motion"] for s in style_values])),
        "mean_rgb": [
            float(np.mean([s["mean_rgb"][0] for s in style_values])),
            float(np.mean([s["mean_rgb"][1] for s in style_values])),
            float(np.mean([s["mean_rgb"][2] for s in style_values])),
        ],
    }


def clip_feature(filepath: str, sample_fps: float = 2.0) -> dict:
    """Extract a lightweight aggregated feature vector + style stats for a clip."""
    info = probe(filepath)
    dur = max(0.1, info["duration"])
    frames, real_fps, n = _read_frames_raw(filepath, fps=sample_fps)
    if n == 0:
        return {"file": filepath, "duration": dur, "width": info["width"],
                "height": info["height"], "feature": None, "tags": ["empty"],
                "brightness": 0.5, "motion": 0.0, "nb_frames": 0,
                "scan": None, "scan_fps": sample_fps,
                "contrast": 0.1, "saturation": 0.5, "temperature": 0.0,
                "edge_density": 0.1, "mean_rgb": [0.5, 0.5, 0.5]}

    n_sample = min(n, 12)
    idx = np.linspace(0, n - 1, n_sample, dtype=int)
    feats = np.stack([_frame_sig(frames[i]) for i in idx])
    feature = feats.mean(axis=0)
    feature /= (np.linalg.norm(feature) + 1e-8)
    f = frames[idx].astype(np.float64) / 255.0
    d = np.abs(np.diff(f, axis=0)).mean() if n_sample > 1 else 0.0
    avg = float(np.mean(f))
    tags = []
    if avg < 0.3:
        tags.append("dark")
    elif avg > 0.7:
        tags.append("bright")
    if d > 0.02:
        tags.append("motion")
    scan = np.stack([_frame_sig(frames[i]) for i in range(n)]) if n else None
    rgb = np.clip(f.reshape(-1, 3).mean(axis=0), 0.0, 1.0)
    sat = float(np.sqrt(((rgb - np.mean(rgb)) ** 2).sum()) / (np.mean(rgb) + 1e-6))
    temp = float(rgb[0] - rgb[2])
    contrast = float(f.std())
    edge_density = float(np.abs(np.diff(f[..., 0], axis=0)).mean() + np.abs(np.diff(f[..., 0], axis=1)).mean() / max(1, f.shape[1]))
    return {
        "file": filepath, "duration": dur,
        "width": info["width"], "height": info["height"],
        "feature": feature.tolist(),
        "tags": tags,
        "brightness": round(float(avg), 4),
        "motion": round(float(d), 4),
        "contrast": round(float(np.clip(contrast, 0.0, 1.0)), 4),
        "saturation": round(float(np.clip(sat, 0.0, 1.5)), 4),
        "temperature": round(float(np.clip(temp, -1.0, 1.0)), 4),
        "edge_density": round(float(np.clip(edge_density, 0.0, 1.0)), 4),
        "mean_rgb": [round(float(x), 4) for x in rgb.tolist()],
        "scan": scan, "scan_fps": sample_fps,
        "nb_frames": int(n),
    }


def _frame_sig(img: np.ndarray) -> np.ndarray:
    """28-dim YUV histogram signature for a single frame (L2-normalized)."""
    img = img.astype(np.float64) / 255.0
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    u = (b - y) * 0.492
    v = (r - y) * 0.877

    def _h(data, bins=12):
        counts, _ = np.histogram(data.ravel(), bins=bins, range=(0, 1))
        s = counts.sum()
        if s <= 0:
            return np.zeros(bins)
        return counts / (s * ((1.0 - 0.0) / bins))

    out = np.concatenate([_h(y, 12), _h(u, 8), _h(v, 8)])
    return out / (np.linalg.norm(out) + 1e-8)


def _shot_margins(shot: dict, dissolves: list | None = None) -> tuple[float, float]:
    """Seconds of cross-fade overlap each edge of the shot occupies (0 for cuts)."""
    def _d(tr) -> float:
        if not tr:
            return 0.0
        if tr.get("type") in ("cut", "none", None):
            return 0.0
        return float(tr.get("duration") or 0.5)

    m_in = _d(shot.get("transition_in"))
    m_out = _d(shot.get("transition_out"))
    if (m_in == 0.0 or m_out == 0.0) and dissolves:
        for d in dissolves:
            dt = float(d["t_end"] - d["t_start"])
            if abs(float(d["t_start"]) - float(shot["start"])) < 0.05:
                m_in = max(m_in, dt)
            if abs(float(d["t_end"]) - float(shot["end"])) < 0.05:
                m_out = max(m_out, dt)
    return min(m_in, 1.0), min(m_out, 1.0)


_tpl_cache: dict[str, list | None] = {}


def template_shot_sigs(template: dict) -> list | None:
    """Per-shot mean color signature from the template source frames."""
    src = template.get("meta", {}).get("_source")
    if not src or not os.path.exists(src):
        return None
    if src in _tpl_cache:
        return _tpl_cache[src]
    try:
        frames, _rfps, n = _read_frames_raw(src)
    except Exception:
        _tpl_cache[src] = None
        return None
    if n == 0:
        _tpl_cache[src] = None
        return None
    times = np.arange(n) / ANALYSIS_FPS
    dissolves = template.get("dissolves")
    sigs = []
    for sh in template["shots"]:
        m_in, m_out = _shot_margins(sh, dissolves)
        t0 = float(sh["start"]) + m_in
        t1 = float(sh["end"]) - m_out
        idx = np.flatnonzero((times >= t0) & (times < t1))
        if len(idx) == 0:
            idx = np.flatnonzero((times >= float(sh["start"])) & (times < float(sh["end"])))
        if len(idx) == 0:
            idx = np.array([int(np.clip(round((float(sh["start"]) + float(sh["end"])) / 2 * ANALYSIS_FPS), 0, n - 1))])
        idx = np.clip(idx, 0, n - 1)
        sm = np.stack([_frame_sig(frames[i]) for i in idx]).mean(axis=0)
        sm /= (np.linalg.norm(sm) + 1e-8)
        sigs.append(sm)
    _tpl_cache[src] = sigs
    return sigs


def _best_window(scan: np.ndarray, sfps: float, sig: np.ndarray, slot_dur: float,
                 m_in: float = 0.0, m_out: float = 0.0):
    """Best matching source window in the clip scan for a template slot."""
    if scan is None or sig is None or len(scan) == 0:
        return None, None
    n = len(scan)
    win = max(1, int(round(slot_dur * sfps)))
    s_in = int(round(m_in * sfps))
    s_out = int(round(m_out * sfps))
    if n >= win:
        def _core(seg):
            a = min(s_in, len(seg))
            b = max(a + 1, len(seg) - s_out)
            return seg[a:b] if b > a else seg

        step = max(1, win // 4)
        best = -1.0
        t = 0.0
        for s in range(0, n - win + 1, step):
            sim = _cos(sig, _core(scan[s:s + win]).mean(axis=0))
            if sim > best:
                best, t = sim, s / sfps
        return best, t
    return _cos(sig, scan.mean(axis=0)), 0.0


def _cos(a, b):
    if a is None or b is None:
        return 0.0
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        return 0.0
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def score_matrix(template: dict, clips: list[dict],
                 w_content: float = 0.22, w_style: float = 0.46,
                 w_duration: float = 0.12, w_other: float = 0.20) -> tuple[np.ndarray, np.ndarray]:
    """Return (S, B): S[shot, clip] match scores and B[shot, clip] best offsets.

    This score prioritizes filmic style and continuity so the output matches the template's
    feel even when the source clips are different.
    """
    shots = template["shots"]
    sigs = template_shot_sigs(template)
    dissolves = template.get("dissolves")
    S = np.zeros((len(shots), len(clips)))
    B = np.full((len(shots), len(clips)), np.nan)
    for i, sh in enumerate(shots):
        slot_dur = sh["end"] - sh["start"]
        sh_feat = sh.get("content", {}).get("feature")
        sh_tags = set(sh.get("content", {}).get("tags", []))
        sh_style = _style_profile(sh)
        neigh_style = _neighbor_style(template, i)
        m_in, m_out = _shot_margins(sh, dissolves)
        for j, cl in enumerate(clips):
            src_dur = cl["duration"]
            usable = min(src_dur, slot_dur * 1.2)
            fit = usable / max(slot_dur, 1e-6) if src_dur >= slot_dur * 0.85 else (0.5 * src_dur / max(slot_dur, 1e-6))
            fit = float(np.clip(fit, 0, 1))
            sig = sigs[i] if sigs else None
            scan = cl.get("scan")
            sim, src_t = _best_window(scan, cl.get("scan_fps", 2.0), sig, slot_dur, m_in, m_out)
            if sim is None:
                sim = _cos(sh_feat, cl.get("feature"))
                src_t = None
            content_score = float(np.clip(sim, 0.0, 1.0))
            clip_style = _style_profile(cl)
            style_score = _style_similarity(sh_style, clip_style)
            continuity_score = _style_similarity(neigh_style, clip_style)
            if src_t is not None and src_dur >= slot_dur:
                B[i, j] = float(np.clip(src_t, 0.0, max(0.0, src_dur - slot_dur)))

            aspect = 1.0
            tags = cl.get("tags", [])
            tag_bonus = 1.0 if (sh_tags & set(tags)) else 0.82

            style_penalty = 0.0
            if abs(sh_style["brightness"] - clip_style["brightness"]) > 0.25:
                style_penalty += 0.14
            if abs(sh_style["temperature"] - clip_style["temperature"]) > 0.20:
                style_penalty += 0.12
            if abs(sh_style["saturation"] - clip_style["saturation"]) > 0.28:
                style_penalty += 0.10
            if abs(sh_style["motion"] - clip_style["motion"]) > 0.25:
                style_penalty += 0.12
            if abs(sh_style["contrast"] - clip_style["contrast"]) > 0.20:
                style_penalty += 0.08
            if (sh_style["brightness"] < 0.35 and clip_style["brightness"] > 0.65) or (sh_style["brightness"] > 0.65 and clip_style["brightness"] < 0.35):
                style_penalty += 0.12
            if (sh_style["temperature"] > 0.10 and clip_style["temperature"] < -0.10) or (sh_style["temperature"] < -0.10 and clip_style["temperature"] > 0.10):
                style_penalty += 0.14
            if abs(neigh_style["brightness"] - clip_style["brightness"]) > 0.35:
                style_penalty += 0.08
            if abs(neigh_style["motion"] - clip_style["motion"]) > 0.30:
                style_penalty += 0.08

            final_style = max(0.0, style_score - style_penalty)
            if content_score < 0.25 and final_style < 0.50:
                S[i, j] = -1.0
                continue
            if final_style < 0.66 and continuity_score < 0.60:
                S[i, j] = -0.75
                continue

            S[i, j] = (
                w_content * content_score
                + w_style * final_style
                + 0.18 * continuity_score
                + w_duration * fit
                + w_other * aspect * tag_bonus
            )
    return S, B


def assign(template: dict, clips: list[dict], allow_reuse: bool = False) -> list[dict]:
    """Assign clips to template shots while preferring continuity and visual similarity."""
    n_shots = len(template["shots"])
    n_clips = len(clips)
    S, B = score_matrix(template, clips)
    if n_clips == 0:
        return [{"clip_idx": None, "score": 0.0, "reason": "no clips"} for _ in range(n_shots)]
    if n_clips >= n_shots:
        rows, cols = linear_sum_assignment(-S)
        out = [None] * n_shots
        for r, c in zip(rows, cols):
            out[r] = c
        return [
            {"clip_idx": int(out[i]) if out[i] is not None else None,
             "score": float(S[i, out[i]]) if out[i] is not None else 0.0,
             "src_start": (None if B[i, out[i]] != B[i, out[i]] else float(B[i, out[i]])) if out[i] is not None else None}
            for i in range(n_shots)
        ]

    DIV = 0.15
    out = [None] * n_shots
    used = [0] * n_clips
    for _ in range(n_shots):
        best = (-1e9, -1, -1)
        for i in range(n_shots):
            if out[i] is not None:
                continue
            for j in range(n_clips):
                sc = float(S[i, j]) - DIV * used[j]
                if sc > best[0]:
                    best = (sc, i, j)
        sc, i, j = best
        if i < 0:
            break
        out[i] = j
        used[j] += 1
    return [
        {"clip_idx": int(out[i]),
         "score": float(S[i, out[i]]) if out[i] is not None else 0.0,
         "src_start": (None if out[i] is None or B[i, out[i]] != B[i, out[i]] else float(B[i, out[i]]))}
        for i in range(n_shots)
    ]


def trim_plan(clip: dict, slot_dur: float, slot_start: float, src_start: float | None = None) -> dict:
    """Choose in/out + speed to fill a slot from a clip."""
    src_dur = clip["duration"]
    if src_start is not None and src_dur >= slot_dur:
        hi = max(0.0, src_dur - slot_dur)
        s = float(np.clip(src_start, 0.0, hi))
        return {"strategy": "match", "src_start": round(s, 4), "src_end": round(s + slot_dur, 4),
                "speed": 1.0, "freeze_tail": 0.0}
    if src_dur >= slot_dur:
        avail = src_dur - slot_dur
        start = min(avail * 0.5, slot_dur * 0.3)
        end = start + slot_dur
        return {"strategy": "trim", "src_start": round(start, 4), "src_end": round(end, 4),
                "speed": 1.0, "freeze_tail": 0.0}
    speed = max(0.6, src_dur / slot_dur)
    play = src_dur / speed
    freeze = slot_dur - play
    return {"strategy": "slow_freeze", "src_start": 0.0, "src_end": src_dur,
            "speed": round(speed, 4), "freeze_tail": round(max(0, freeze), 4)}


__all__ = ["clip_feature", "assign", "trim_plan", "score_matrix", "template_shot_sigs"]
