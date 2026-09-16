"""Fuse all analysis events into the canonical Template dict."""
from __future__ import annotations
import numpy as np


def _best_transition(cuts: list[dict], dissolves: list[dict], flashes: list[dict], t_prev: float, t_next: float) -> dict:
    """Classify the transition between two shots by proximity to detected events."""
    # default cut
    if t_prev is None or t_next is None:
        return {"type": "cut", "since": 0.0, "source": "assumed"}
    mid = (t_prev + t_next) / 2
    for f in flashes:
        if f["t"] is not None and mid - 0.25 <= f["t"] <= mid + 0.25:
            return {"type": "flash", "duration": 0.25, "location": f["t"], "source": "flash"}
    for d in dissolves:
        if d["t_start"] <= mid <= d["t_end"]:
            return {"type": "dissolve", "duration": round(d["t_end"] - d["t_start"], 4),
                    "location": mid, "source": "dissolve", "confidence": d["confidence"]}
    # precise cut location
    best_cut = min([c for c in cuts], key=lambda c: abs(c["t"] - mid), default=None)
    if best_cut is not None and abs(best_cut["t"] - t_prev) < (t_next - t_prev) * 0.5 + 0.2:
        return {"type": "cut", "location": best_cut["t"], "source": "cut"}
    return {"type": "cut", "location": mid, "source": "assumed"}


def _link_shots(shots: list[dict], cuts: list[dict], dissolves: list[dict], flashes: list[dict]) -> list[dict]:
    """Attach transitions_in/out + per-shot timing to each shot."""
    out = []
    n = len(shots)
    for i, sh in enumerate(shots):
        s = dict(sh)
        prev_end = shots[i - 1]["end"] if i > 0 else None
        t_in = _best_transition(cuts, dissolves, flashes, prev_end, s["start"]) if i > 0 else None
        next_start = shots[i + 1]["start"] if i < n - 1 else None
        t_out = _best_transition(cuts, dissolves, flashes, s["end"], next_start) if i < n - 1 else None
        s["transition_in"] = t_in
        s["transition_out"] = t_out
        s["duration"] = round(s["end"] - s["start"], 4)
        out.append(s)
    return out


def _motion_for_shots(motion_per_frame: list[dict], motion_global: dict, shots: list[dict]) -> list[dict]:
    motion = []
    for sh in shots:
        per = [m for m in motion_per_frame if sh["start"] <= m["t"] <= sh["end"]]
        if not per:
            motion.append({"idx": sh["idx"], "classification": "static"})
            continue
        panx = np.mean([m["dx"] for m in per])
        pany = np.mean([m["dy"] for m in per])
        zoom = np.mean([m["zoom"] for m in per])
        shake = np.std([m["dx"] for m in per]) + np.std([m["dy"] for m in per])
        pan_mag = np.sqrt(panx ** 2 + pany ** 2)
        zoom_a = np.clip(np.mean([m["zoom"] for m in per]), -2, 2)
        if shake > 1.2:
            cls = "handheld"
        elif zoom_a > 0.15:
            cls = "zoom_in"
        elif zoom_a < -0.15:
            cls = "zoom_out"
        elif pan_mag > 0.8:
            cls = "pan"
        else:
            cls = "static"
        motion.append({
            "idx": sh["idx"],
            "classification": cls,
            "pan_x": round(float(panx), 4),
            "pan_y": round(float(pany), 4),
            "pan_mag": round(float(pan_mag), 4),
            "zoom": round(float(zoom_a), 4),
            "shake": round(float(shake), 4),
            "segments": [{"t": m["t"], "dx": m["dx"], "dy": m["dy"], "zoom": m["zoom"]} for m in per[::max(1, len(per)//8)]],
        })
    return motion


def _attach_beats(shots: list[dict], beats: list[dict]) -> list[dict]:
    out = []
    for sh in shots:
        s = dict(sh)
        s["beats"] = [b for b in beats if sh["start"] <= b["t"] <= sh["end"]]
        out.append(s)
    return out


def _attach_events(shots: list[dict], events: list[dict]) -> list[dict]:
    out = []
    for sh in shots:
        s = dict(sh)
        s["sound_events"] = [e for e in events if sh["start"] <= e["t"] <= sh["end"]]
        out.append(s)
    return out


def _structure(shots: list[dict]) -> list[dict]:
    """Rough act segmentation by mean energy/motion."""
    if not shots:
        return []
    energy = [sh.get("audio", {}).get("energy", 0.5) for sh in shots]
    n = len(shots)
    labels = ["intro"] * n
    half = n // 2
    if n >= 4:
        for i in range(half, n):
            labels[i] = "outro" if n - half <= 2 else "build"
        # peak energy window -> drop/peak
        peak_i = int(np.argmax(energy))
        if half <= peak_i < n - 1:
            labels[peak_i] = "peak"
    acts, prev = [], None
    for i, sh in enumerate(shots):
        if labels[i] != prev:
            acts.append({"act": labels[i], "start": sh["start"]})
            prev = labels[i]
    for i in range(len(acts) - 1):
        acts[i]["end"] = acts[i + 1]["start"]
    if acts:
        acts[-1]["end"] = shots[-1]["end"]
    return acts


def fuse(*, probe: dict, beats: dict, loudness: dict, shots: dict,
         motion: dict, speed: dict, color: dict, text: list[dict] | None = None,
         sound_events: list[dict] | None = None) -> dict:
    """Assemble the canonical template."""
    beat_list = beats.get("beats", [])
    motion_per_frame = motion.get("per_frame", [])
    motion_global = motion.get("global", {})
    shot_list = shots.get("shots", [])

    linked = _link_shots(shot_list, shots.get("cuts", []),
                         shots.get("dissolves", []), shots.get("flashes", []))
    linked = _attach_beats(linked, beat_list)
    mv = _motion_for_shots(motion_per_frame, motion_global, linked)
    mv_by_idx = {m["idx"]: m for m in mv}
    events = list(sound_events or [])
    for sh in linked:
        sh["motion"] = mv_by_idx.get(sh["idx"])
    for sh in linked:
        sh["audio"] = {
            "energy": 0.5,
            "onset_rate": float(len(sh["beats"]) / max(0.001, sh["duration"])) if sh["duration"] else 0,
        }
    # annotate sound events: on_beat if within 60ms of a beat
    beat_times = [b["t"] for b in beat_list]
    import bisect
    for ev in events:
        i = bisect.bisect_left(beat_times, ev["t"])
        near = float("inf")
        if i > 0:
            near = min(near, ev["t"] - beat_times[i - 1])
        if i < len(beat_times):
            near = min(near, beat_times[i] - ev["t"])
        ev["on_beat"] = abs(near) < 0.06

    # attach per-shot color looks
    col_by_idx = {c["idx"]: c for c in (color.get("shots") or [])}
    for sh in linked:
        col = col_by_idx.get(sh["idx"])
        if col:
            sh["color"] = {"mean_rgb": col.get("mean_rgb"),
                           "tags": col.get("tags", []),
                           "sat": col.get("sat"),
                           "temp": col.get("temp"),
                           "luma": col.get("luma")}
    text_map = {}
    for t in text or []:
        text_map.setdefault(round(t["t"]), []).append(t)
    for sh in linked:
        t0, t1 = int(sh["start"]), int(sh["end"])
        sh["text"] = text_map.get(t0, []) + text_map.get(t1, [])

    # keep meta.duration consistent with detected shots when shot detection produced a timeline
    if linked:
        dur = round(linked[-1]["end"], 4)
        if abs(dur - probe["duration"]) < 1.5:
            duration = dur
        else:
            duration = round(probe["duration"], 4)
    else:
        duration = round(probe["duration"], 4)

    return {
        "version": "0.1.0",
        "meta": {
            "duration": duration,
            "fps": probe["fps"],
            "resolution": [probe["width"], probe["height"]],
            "has_audio": bool(probe.get("audio_codec")),
        },
        "tempo": beats.get("tempo"),
        "beatmap": beat_list,
        "loudness": loudness,
        "shots": linked,
        "sound_events": events,
        "structure": _structure(linked),
        "color_look": color.get("global"),
        "pacing": speed.get("pacing"),
        "freezes": speed.get("freezes", []),
        "probe": {k: probe[k] for k in ("audio_codec", "audio_channels",
                                        "audio_sample_rate", "format_name", "pixel_format")},
    }