"""Shared Edit model produced by the recreate engine and consumed by exporters/renders."""
from __future__ import annotations


def empty_edit(meta: dict | None = None) -> dict:
    return {
        "meta": meta or {"fps": 30, "width": 1280, "height": 720, "duration": 0.0, "title": "Recreated"},
        "segments": [],
    }


def segment(**kw) -> dict:
    base = {
        "idx": 0, "file": "", "name": "", "src_start": 0.0, "src_end": 0.0,
        "start": 0.0, "end": 0.0, "speed": 1.0,
        "transition_in": None, "transition_out": None,
        "transform": {"scale": 1.0, "x": 0, "y": 0},
        "lut": None, "color": {"temp": 0, "sat": 1.0, "exposure": 0},
        "text": [], "audio": {"gain": 0.0},
    }
    base.update(kw)
    return base


def duration(edit: dict) -> float:
    return edit["meta"].get("duration", 0.0)


def recompute_duration(edit: dict) -> dict:
    total = 0.0
    for seg in edit["segments"]:
        total = seg["end"] = max(total, 0.0)  # contiguous
        est = seg["end"] - seg["start"]
        total = seg["end"]
    # normalize segments in order recomputing contiguous timeline
    t = 0.0
    for seg in edit["segments"]:
        seg["start"] = round(t, 6)
        seg["end"] = round(t + (seg["src_end"] - seg["src_start"]) / max(seg["speed"], 1e-4), 6)
        t = seg["end"]
    edit["meta"]["duration"] = round(t, 6)
    return edit


def lint(edit: dict) -> list[str]:
    problems = []
    t = 0.0
    for seg in edit.get("segments", []):
        if seg["end"] < seg["start"]:
            problems.append(f"seg {seg['idx']}: negative duration")
        if seg["src_end"] < seg["src_start"]:
            problems.append(f"seg {seg['idx']}: negative source duration")
    return problems