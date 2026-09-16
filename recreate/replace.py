"""Mode A: timing-preserving replacement of template slots with user clips."""
from __future__ import annotations
import numpy as np
import edit as editm
from .matching import assign, trim_plan


def _transition(t: dict | None) -> dict | None:
    if not t:
        return None
    ttype = t.get("type")
    if ttype in ("cut", "none", None):
        return None
    kind = ("dissolve" if ttype in ("dissolve", "crossfade", "cross", "smoothness")
            else "fadeblack" if ttype in ("fadeblack", "dip")
            else "flash" if ttype == "flash"
            else "dissolve")
    return {"type": kind, "duration": float(min(1.5, max(0.2, t.get("duration", 0.5))))}


def _transform_from_motion(motion: dict | None, dur: float) -> dict:
    if not motion:
        return {"scale": 1.0, "x": 0, "y": 0}
    cls = motion.get("classification", "static")
    t = {"scale": 1.0, "x": 0, "y": 0}
    if cls in ("zoom_in",):
        t["zoom_seq"] = [{"t": 0.0, "zoom": 1.0}, {"t": max(0.05, dur), "zoom": 1.15}]
        t["scale"] = 1.0
    elif cls == "zoom_out":
        t["zoom_seq"] = [{"t": 0.0, "zoom": 1.15}, {"t": max(0.05, dur), "zoom": 1.0}]
        t["scale"] = 1.0
    return t


def _color_from_tags(tags: list[str] | None) -> dict:
    tags = tags or []
    col = {"temp": 0, "sat": 1.0, "exposure": 0}
    if "bw" in tags:
        col["sat"] = 0.0
    if "warm" in tags:
        col["temp"] = 0.15
    if "cool" in tags:
        col["temp"] = -0.15
    if "dark" in tags:
        col["exposure"] = -0.1
    if "high_sat" in tags:
        col["sat"] = 1.35
    return col


def _grade_color(sh: dict, template: dict) -> dict:
    """Transfer the template shot's measured grade onto the recreated window."""
    stats = sh.get("color") or {}
    tags = list(stats.get("tags", []))
    sat = stats.get("sat")
    temp = stats.get("temp")
    luma = stats.get("luma")
    col = {
        "tags": tags,
        "sat": 1.0,
        "temp": 0.0,
        "exposure": 0.0,
    }
    if "bw" in tags:
        col["sat"] = 0.0
    elif "high_sat" in tags:
        col["sat"] = 1.7
    elif isinstance(sat, (int, float)):
        col["sat"] = float(np.clip(sat / 0.35, 0.0, 2.5))
    if isinstance(temp, (int, float)):
        col["temp"] = float(temp)
    if "dark" in tags:
        col["exposure"] = -0.1
    elif "bright" in tags:
        col["exposure"] = 0.1
    if "warm" in tags and abs(col["temp"]) < 0.12:
        col["temp"] = 0.15
    if "cool" in tags and abs(col["temp"]) < 0.12:
        col["temp"] = -0.15
    matrix = (template.get("color_look") or {}).get("matrix")
    if matrix and len(matrix) >= 9:
        col["matrix"] = [float(x) for x in matrix[:9]]
    col.setdefault("mean_rgb", stats.get("mean_rgb"))
    return col


def build_replace_edit(template: dict, clips: list[dict], assignment: list[dict] | None = None,
                       source_audio: str | None = None) -> dict:
    """Build an Edit that preserves template timing, swapping in user clips."""
    shots = template["shots"]
    if assignment is None:
        assignment = assign(template, clips)
    if not clips:
        raise ValueError("need at least one custom clip for replace mode")
    # fill any missing slots with the best reusable clip (allow reuse)
    for a in assignment:
        if a.get("clip_idx") is None:
            a["clip_idx"] = 0
            a["score"] = 0.0
    segments = []
    fpss = template["meta"]["fps"]
    for a, sh in zip(assignment, shots):
        idx = a["clip_idx"]
        cl = clips[idx] if 0 <= idx < len(clips) else clips[0]
        slot_dur = sh["end"] - sh["start"]
        plug = trim_plan(cl, slot_dur, sh["start"], src_start=a.get("src_start"))
        segment = editm.segment(
            idx=sh["idx"],
            file=cl["file"],
            name=cl["file"].split("/")[-1],
            src_start=plug["src_start"],
            src_end=plug["src_end"],
            start=sh["start"],
            end=sh["end"],
            speed=plug["speed"],
            transition_in=_transition(sh.get("transition_in")),
            transform=_transform_from_motion(sh.get("motion"), slot_dur),
            color=_grade_color(sh, template),
            text=_clean_text(sh.get("text", [])),
            audio={"gain": 0.0},
            _fit=plug,
        )
        segments.append(segment)

    meta = {
        "fps": fpss,
        "width": template["meta"]["resolution"][0],
        "height": template["meta"]["resolution"][1],
        "duration": template["meta"]["duration"],
        "title": "Recreated (replace)",
        "mode": "replace",
    }
    if source_audio:
        meta["source_audio"] = source_audio
    edit_ = editm.empty_edit(meta)
    edit_["segments"] = segments
    edit_.setdefault("assignment", [
        {"shot": i, "clip": a.get("clip_idx"), "score": a.get("score")}
        for i, a in enumerate(assignment)
    ])
    return editm.recompute_duration(edit_)


def _clean_text(text: list[dict]) -> list[dict]:
    out = []
    for t in text:
        if t.get("text"):
            out.append({"text": t["text"], "start": t.get("t", 0.0), "end": t.get("t", 0.0) + 1.0,
                        "confidence": t.get("confidence", 1.0)})
    return out


_pl = None