"""Recommend upload parameters (clip count / durations) for best recreation output."""
from __future__ import annotations

from .recut import beat_boundaries


def recommend_clips(template: dict, mode: str = "replace") -> dict:
    """Return clip-count and clip-duration guidance derived from template analysis."""
    meta = template.get("meta") or {}
    dur = float(meta.get("duration", 0.0))
    shots = template.get("shots") or []
    slot_lens = [float(s["end"]) - float(s["start"]) for s in shots]
    longest = max(slot_lens) if slot_lens else dur

    if mode == "recut":
        bnds = beat_boundaries(template)
        windows = [bnds[i + 1] - bnds[i] for i in range(len(bnds) - 1)
                   if bnds[i + 1] - bnds[i] > 0.05]
        if not windows:
            windows = [dur]
        longest_w = max(windows)
        mean_w = sum(windows) / len(windows)
        clips_needed = max(2, int(round(len(windows) / 2)))
        min_dur = round(longest_w, 1)
        ideal_dur = round(max(longest_w * 1.25, mean_w + 1.0), 1)
        message = (
            f"Tempo grid splits the template into {len(windows)} rhythm windows "
            f"(avg {mean_w:.1f}s, longest {longest_w:.1f}s). Upload at least {clips_needed} "
            f"clips — ideally one per window — each at least {min_dur:.0f}s (ideally {ideal_dur:.0f}s) "
            f"so every window plays at natural speed."
        )
        return {
            "mode": "recut", "slots": len(windows), "clips_needed": clips_needed,
            "clip_duration_min_sec": min_dur, "clip_duration_sec": ideal_dur,
            "longest_slot_sec": round(longest_w, 1), "message": message,
        }

    if not slot_lens:
        min_dur = round(dur, 1)
        return {
            "mode": "replace", "slots": 0, "clips_needed": 1,
            "clip_duration_min_sec": min_dur, "clip_duration_sec": round(dur * 1.2, 1),
            "longest_slot_sec": min_dur,
            "message": f"Template has no shot data yet; use a clip of at least {dur:.0f}s.",
        }

    mean = sum(slot_lens) / len(slot_lens)
    clips_needed = len(shots)
    min_dur = round(longest * 1.05, 1)
    ideal_dur = round(longest * 1.5, 1)
    message = (
        f"Template has {len(shots)} shots (avg {mean:.1f}s, longest {longest:.1f}s). "
        f"Upload {clips_needed} clips so each shot gets its own footage — each at least "
        f"{min_dur:.0f}s (ideally {ideal_dur:.0f}s) so every clip fills its slot and leaves "
        f"headroom for best-window matching."
    )
    return {
        "mode": "replace", "slots": len(shots), "clips_needed": clips_needed,
        "clip_duration_min_sec": min_dur, "clip_duration_sec": ideal_dur,
        "longest_slot_sec": round(longest, 1), "message": message,
    }