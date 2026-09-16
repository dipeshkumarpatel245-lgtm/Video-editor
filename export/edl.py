"""CMX3600 EDL export (universal fallback: cuts + dissolves)."""
from __future__ import annotations


def _tc(sec: float, fps: float) -> str:
    sec = max(0.0, sec)
    fps_i = int(round(fps))
    total = int(round(sec * fps_i))
    hh = total // (3600 * fps_i)
    mm = (total // (60 * fps_i)) % 60
    ss = (total // fps_i) % 60
    ff = total % fps_i
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def _edl_name(seg) -> str:
    return f"{seg.get('name', 'CLIP')}".replace(" ", "_")[:32]


def export_edl(edit: dict, title: str = "VT_RECREATE") -> str:
    fps = float(edit["meta"]["fps"])
    segments = sorted(edit["segments"], key=lambda s: s["start"])
    lines: list[str] = [
        f"TITLE: {title}",
        "FCM: NON-DROP FRAME",
        "",
    ]
    start_tc = 3600.0  # 01:00:00:00

    # Detect the effective transition before each edit by looking at prev seg's out,
    # but guestrooms: EDL encodes a dissolve on the edit line of the SECOND clip.
    # We emit for each clip: header + dissolve frame count when transition_in is a late transition.
    timing_anchor = {}
    for seg in segments:
        tc_in = _tc(start_tc + seg["start"], fps)
        tc_out = _tc(start_tc + seg["end"], fps)
        src_in = _tc(seg["src_start"], fps)
        src_out = _tc(seg["src_end"], fps)
        reel = f"A{seg['idx'] % 99:02d}"
        name = _edl_name(seg)

        ev = len([l for l in lines if l and l[0].isdigit()]) + 1
        code = f"{ev:03d}"
        ti = seg.get("transition_in")
        ttype = (ti or {}).get("type", "cut")
        if ttype in ("dissolve", "crossfade", "cross"):
            lines.append(f"{code} {name:7} {reel:6} {src_in} {src_out} {tc_in} {tc_out}")
            dur_f = int(round(float(ti.get("duration", 0.5)) * fps))
            lines.append(f"DISSOLVE TO")
            lines.append(f"{dur_f:03d}")
            lines.append("")
        else:
            lines.append(f"{code} {name:7} {reel:6} {src_in} {src_out} {tc_in} {tc_out}")
            lines.append(f"* {seg.get('text', [{}])[0].get('text', '') if seg.get('text') else ''}".rstrip())
            lines.append("")
    return "\n".join(lines) + "\n"


def _blank(*_):  # keep API stable
    return None