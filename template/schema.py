"""Canonical template model: validation + hot-load/save helpers."""
from __future__ import annotations
import json


TEMPLATE_VERSION = "0.1.0"


def validate(t: dict, strict: bool = True) -> list[str]:
    """Return list of problems; empty list = valid."""
    problems: list[str] = []
    if not isinstance(t, dict):
        return ["template must be an object"]
    meta = t.get("meta", {})
    if "duration" not in meta:
        problems.append("meta.duration missing")
    if not isinstance(t.get("shots"), list):
        problems.append("shots missing")
    if not isinstance(t.get("beatmap"), list):
        problems.append("beatmap missing")
    for i, sh in enumerate(t.get("shots", [])):
        if "start" not in sh or "end" not in sh:
            problems.append(f"shot {i}: start/end missing")
    return problems


def load(path: str) -> dict:
    with open(path) as f:
        t = json.load(f)
    problems = validate(t)
    if problems:
        raise ValueError(f"invalid template: {'; '.join(problems)}")
    return t


def save(t: dict, path: str, indent: int = 2) -> None:
    with open(path, "w") as f:
        json.dump(t, f, indent=indent, ensure_ascii=False)


def to_json_string(t: dict) -> str:
    return json.dumps(t, ensure_ascii=False)


def beats_in_range(t: dict, start: float, end: float) -> list[dict]:
    return [b for b in t.get("beatmap", []) if start <= b["t"] <= end]