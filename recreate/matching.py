"""Analyze custom clips and match them to template slots with style-aware matching."""
from __future__ import annotations

import os

import numpy as np
from scipy.optimize import linear_sum_assignment

from analysis.probe import probe
from analysis.video.content import shot_feature
from analysis.video.shots import _read_frames_raw
from config import ANALYSIS_FPS, ANALYSIS_WIDTH
from ffutils import run


def _style_profile(obj: dict | None) -> dict:
    """Return normalized style state for template shots or clip metadata."""
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
    rgb = 1.0 - min(1.0, np.linalg.norm(np.asarray(a["mean_rgb"]) - np.asarray(b["mean_rgb"])) / np.sqrt(3.0))
    return float(np.clip(
        0.22 * brightness + 0.12 * contrast + 0.14 * saturation + 0.12 * temperature
        + 0.10 * edge + 0.10 * motion + 0.20 * rgb,
        0.0, 1.0,
    ))


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
    """Per-shot mean signature from the template source frames (cached per file)."""
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
                 w_content: float = 0.38, w_style: float = 0.28,
                 w_duration: float = 0.22, w_other: float = 0.12) -> tuple[np.ndarray, np.ndarray]:
    """Return (S, B): S[shot, clip] match scores and B[shot, clip] best source offsets.

    This uses a stronger visual-style similarity so different clips can still recreate the
    same template mood, pacing, and look.
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
            if src_t is not None and src_dur >= slot_dur:
                B[i, j] = float(np.clip(src_t, 0.0, max(0.0, src_dur - slot_dur)))
            aspect_slot = 1.0
            aspect_clip = 1.0
            aspect = float(1.0 if abs(aspect_slot - aspect_clip) < 0.05 else 0.6)
            tags = cl.get("tags", [])
            tag_bonus = 1.0 if (sh_tags & set(tags)) else 0.82
            style_penalty = 0.0
            if abs(sh_style["brightness"] - clip_style["brightness"]) > 0.35:
                style_penalty += 0.08
            if abs(sh_style["temperature"] - clip_style["temperature"]) > 0.35:
                style_penalty += 0.08
            if abs(sh_style["motion"] - clip_style["motion"]) > 0.35:
                style_penalty += 0.06
            S[i, j] = (w_content * content_score
                       + w_style * max(0.0, style_score - style_penalty)
                       + w_duration * fit
                       + w_other * aspect * tag_bonus)
    return S, B


def assign(template: dict, clips: list[dict], allow_reuse: bool = False) -> list[dict]:
    """Content-aware assignments for every shot, with stronger style preservation."""
    n_shots = len(template["shots"])
    n_clips = len(clips)
    S, B = score_matrix(template, clips)
    if n_clips == 0:
        return [{"clip_idx": None, "score": 0.0, "reason": "no clips"} for _ in range(n_shots)]
    if n_clips >= n_shots:
        rows, cols = linear_sum_assignment(-S)
        done = set()
        out = [None] * n_shots
        for r, c in zip(rows, cols):
            out[r] = c
            done.add(c)
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
