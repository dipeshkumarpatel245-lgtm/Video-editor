"""Template filesystem helpers."""
from __future__ import annotations
import json
from pathlib import Path
from config import TEMPLATE_DIR


def default_template_path(template_id: str) -> Path:
    return TEMPLATE_DIR / f"{template_id}.json"


def sanitize_shots(template: dict) -> dict:
    """Clamp shot boundaries to the real media duration; drop/merge degenerate shots.

    Older analysis passes could store shot ends beyond the video length
    (e.g. a 13.9s file with a ''last shot'' ending at 30.3s), which poisoned
    downstream duration math. This normalizes shots in place.
    """
    meta = template.get("meta") or {}
    try:
        dur = float(meta.get("duration") or 0.0)
    except (TypeError, ValueError):
        dur = 0.0
    shots = template.get("shots") or []
    if not shots:
        return template
    if dur <= 0:
        dur = max(float(s.get("end", 0.0)) for s in shots)
    clean = []
    for s in shots:
        try:
            a, b = float(s.get("start", 0.0)), float(s.get("end", 0.0))
        except (TypeError, ValueError):
            continue
        a = min(max(a, 0.0), dur)
        b = min(max(b, 0.0), dur)
        if b - a > 1e-4:
            clean.append((a, b, s))
    clean.sort(key=lambda t: (t[0], t[1]))
    merged = []
    for a, b, orig in clean:
        if merged and a < merged[-1][1] - 1e-4:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b), merged[-1][2])
        else:
            merged.append((a, b, orig))
    if not merged:
        merged = [(0.0, dur, {})]
    if merged[0][0] > 1e-4:
        merged.insert(0, (0.0, merged[0][0], {}))
    if dur - merged[-1][1] > 1e-4:
        merged.append((merged[-1][1], dur, {}))
    out = []
    for i, (a, b, orig) in enumerate(merged):
        item = dict(orig)
        item["start"] = round(a, 4)
        item["end"] = round(b, 4)
        item["idx"] = i
        out.append(item)
    template["shots"] = out
    return template


def store(template: dict, template_id: str) -> Path:
    sanitize_shots(template)
    path = default_template_path(template_id)
    path.write_text(json.dumps(template, indent=2, ensure_ascii=False))
    return path


def fetch(template_id: str) -> dict:
    return sanitize_shots(json.loads(default_template_path(template_id).read_text()))


def exists(template_id: str) -> bool:
    return default_template_path(template_id).exists()