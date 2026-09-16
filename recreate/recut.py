"""Mode B: adaptive re-cut that snaps clips to the template's beat rhythm."""
from __future__ import annotations
import numpy as np
import edit as editm
from .matching import _cos


def _window_target(template: dict, t0: float, t1: float) -> dict | None:
    """Feature target for the beat window derived from overlapping template shots."""
    mean = None
    n = 0
    tags = set()
    for sh in template["shots"]:
        ov = min(sh["end"], t1) - max(sh["start"], t0)
        if ov > 0:
            f = (sh.get("content") or {}).get("feature")
            if f:
                mean = np.zeros(len(f)) if mean is None else mean
                mean += np.array(f)
                n += 1
            tags |= set((sh.get("content") or {}).get("tags", []))
    if n == 0:
        return None
    mean /= n
    return {"feature": mean, "tags": list(tags)}


def _window_color(template: dict, t0: float, t1: float) -> dict:
    """Average the template grade over shots overlapping the window."""
    sat = temp = 0.0
    wsum = 0.0
    tags = set()
    for sh in template["shots"]:
        ov = min(sh["end"], t1) - max(sh["start"], t0)
        if ov <= 0:
            continue
        col = sh.get("color") or {}
        wsum += ov
        if isinstance(col.get("sat"), (int, float)):
            sat += float(col["sat"]) * ov
        if isinstance(col.get("temp"), (int, float)):
            temp += float(col["temp"]) * ov
        tags |= set(col.get("tags", []))
    col = {"temp": 0.0, "sat": 1.0, "exposure": 0.0}
    if wsum > 0:
        sat_v, temp_v = sat / wsum, temp / wsum
        if "bw" in tags:
            col["sat"] = 0.0
        elif "high_sat" in tags:
            col["sat"] = 1.7
        else:
            col["sat"] = float(np.clip(sat_v / 0.35, 0.0, 2.5))
        col["temp"] = float(temp_v)
        if "dark" in tags:
            col["exposure"] = -0.1
    matrix = (template.get("color_look") or {}).get("matrix")
    if matrix and len(matrix) >= 9:
        col["matrix"] = [float(x) for x in matrix[:9]]
    return col


def beat_boundaries(template: dict, max_window: float = 8.0) -> list[float]:
    """Rhythm-window boundaries: strong beats snapped, long gaps tiled into max_window."""
    beats = template["beatmap"]
    if len(beats) < 2:
        # no beat info -> fall back to uniform splices of medium duration
        beats = [{"t": i * 2.0, "strength": 1.0} for i in range(0, int(template["meta"]["duration"] // 2) + 1)]
    strengths = np.array([b.get("strength", 1.0) for b in beats])
    thr = float(np.percentile(strengths, 55)) if len(strengths) else 0.0
    key_beats = [b for b in beats if b.get("strength", 1.0) >= thr]
    if len(key_beats) < 2:
        key_beats = beats

    bnds = []
    for k in range(len(key_beats) - 1):
        t0, t1 = key_beats[k]["t"], key_beats[k + 1]["t"]
        while t1 - t0 > max_window - 1e-6:
            bnds.append(round(t0, 4))
            t0 += max_window
        bnds.append(round(t0, 4))
    bnds.append(round(key_beats[-1]["t"], 4))
    return sorted(set([0.0] + [round(b, 4) for b in bnds]))


def build_recut_edit(template: dict, clips: list[dict],
                     beat_tolerance: float = 0.08,
                     max_window: float = 8.0,
                     source_audio: str | None = None) -> dict:
    """Assemble a beat-matched edit from user clips."""
    n_clips = len(clips)
    if n_clips == 0:
        raise ValueError("need at least one custom clip for recut mode")

    # boundaries = strong beats snapped; chunk long gaps into max_window tiles
    bnds = beat_boundaries(template, max_window)

    segments = []
    fpss = template["meta"]["fps"]
    end_t = float(template["meta"]["duration"])
    clip_usage = {j: {"cursor": 0.0, "dur": clips[j]["duration"]} for j in range(n_clips)}
    clip_usage_count = [0] * n_clips
    DIV = 0.12

    def consume(j: int, length: float, prefer_start: float):
        """Return (src_start, src_end, speed) for clip j covering length."""
        u = clip_usage[j]
        dur = u["dur"]
        if length >= dur * 0.9:
            s = 0.0
            e = dur
            sp = dur / length
            return s, e, max(0.7, sp)
        s = u["cursor"]
        e = s + length
        if e > dur:
            s = 0.0
            e = length
        u["cursor"] = e
        return s, e, 1.0

    # iterate windows between consecutive boundaries (tiles the full timeline)
    for k in range(len(bnds) - 1):
        t0 = bnds[k]
        t1 = bnds[k + 1]
        dur = t1 - t0
        if dur <= 0.05:
            continue
        target = _window_target(template, t0, t1)

        # pick clip maximizing content fit, keep it varied
        best = (None, -999.0)
        for j, cl in enumerate(clips):
            sc = _cos(target["feature"], cl.get("feature")) if target and target.get("feature") is not None else 0.0
            sc -= DIV * clip_usage_count[j]
            if sc > best[1]:
                best = (j, sc)
        j, _sc = best
        if j is None:
            j = k % n_clips
        clip_usage_count[j] += 1

        src_start, src_end, speed = consume(j, dur, 0)
        seg = editm.segment(
            idx=k,
            file=clips[j]["file"],
            name=clips[j]["file"].split("/")[-1],
            src_start=round(src_start, 4),
            src_end=round(src_end, 4),
            start=round(t0, 4),
            end=round(t1, 4),
            speed=round(speed, 4),
            transition_in=None,
            color=(_window_color(template, t0, t1) or {}),
            transform={"scale": 1.0, "x": 0, "y": 0},
            text=[],
            audio={"gain": 0.0},
        )
        segments.append(seg)

    meta = {
        "fps": fpss,
        "width": template["meta"]["resolution"][0],
        "height": template["meta"]["resolution"][1],
        "duration": template["meta"]["duration"],
        "title": "Recreated (recut)",
        "mode": "recut",
    }
    if source_audio:
        meta["source_audio"] = source_audio
    edit_ = editm.empty_edit(meta)
    edit_["segments"] = segments
    edit_ = editm.recompute_duration(edit_)

    # tail-fill: size the passthrough from the recomputed timeline end so the
    # edit always reaches template duration regardless of beat-grid offsets
    reached = edit_["segments"][-1]["end"] if edit_["segments"] else 0.0
    remaining = end_t - reached
    if remaining > 0.05:
        src_len = min(clips[0]["duration"], remaining)
        passthrough = editm.segment(
            idx=len(edit_["segments"]),
            file=clips[0]["file"], name=clips[0]["file"].split("/")[-1],
            src_start=0.0, src_end=src_len,
            start=reached, end=end_t,
            speed=round(src_len / remaining, 4) if remaining > 0 else 1.0,
            transition_in=None, transform={"scale": 1.0, "x": 0, "y": 0},
            text=[], audio={"gain": 0.0},
        )
        edit_["segments"].append(passthrough)
        edit_ = editm.recompute_duration(edit_)
    return edit_


def _color_of(clip: dict) -> dict:
    return {"temp": 0, "sat": 1.0, "exposure": 0}