"""Final Cut Pro XML (FCPXML 1.9) export. Imports into DaVinci Resolve & Final Cut Pro."""
from __future__ import annotations
from xml.sax.saxutils import escape


def _frame_duration(fps: float) -> str:
    if abs(fps - 23.976) < 0.1:
        return "1001/24000s"
    if abs(fps - 24) < 0.1:
        return "100/2400s"
    if abs(fps - 25) < 0.1:
        return "100/2500s"
    if abs(fps - 29.97) < 0.1:
        return "1001/30000s"
    if abs(fps - 30) < 0.1:
        return "100/3000s"
    if abs(fps - 50) < 0.1:
        return "100/5000s"
    if abs(fps - 59.94) < 0.1:
        return "1001/60000s"
    if abs(fps - 60) < 0.1:
        return "100/6000s"
    return f"100/{int(round(fps * 100))}s"


def _s(sec: float) -> str:
    return f"{sec}s"


def _asset_id(i: int) -> str:
    return f"r{i}"


def _n(elem, key, val):
    if val:
        return f' {key}="{escape(str(val))}"'
    return ""


def export_fcpxml(edit: dict, title: str = "Recreated") -> str:
    meta = edit["meta"]
    fps = float(meta["fps"])
    width = int(meta.get("width", 1280))
    height = int(meta.get("height", 720))
    segments = sorted(edit["segments"], key=lambda s: s["start"])
    total = meta.get("duration", _last(segments))

    # assign resource ids
    fmt_v = _asset_id(1)
    fmt_a = _asset_id(2)
    asset_ids = {seg["idx"]: _asset_id(3 + i) for i, seg in enumerate(segments)}
    trans_ids = {}
    t_count = 0
    fmt_name = f"FFVideoFormat{width}x{height}p{round(fps)}"

    resources = [
        f'<format id="{fmt_v}" name="{fmt_name}" frameDuration="{_frame_duration(fps)}" '
        f'width="{width}" height="{height}"/>',
        f'<format id="{fmt_a}" name="FFAudioFormatPCM" sampleRate="{48000}"/>',
    ]

    spine_items: list[str] = []
    for i, seg in enumerate(segments):
        rid = asset_ids[seg["idx"]]
        src_dur = max(0.0, seg["src_end"] - seg["src_start"])
        tim_start = seg["start"]
        tim_dur = max(0.0, seg["end"] - seg["start"])
        name = seg.get("name", "clip.mp4")

        resources.append(
            f'<asset id="{rid}" name="{escape(name)}" uid="{rid}-{i}" '
            f'start="0s" duration="{_s(max(src_dur, tim_dur))}" hasVideo="1" hasAudio="1" '
            f'videoSources="1" audioSources="1" audioChannels="2" format="{fmt_v}">'
            f'<media-rep kind="original-media" src="file://{seg["file"]}"/>'
            f"</asset>"
        )

        clip = (
            f'<asset-clip ref="{rid}" name="{escape(name)}" '
            f'duration="{_s(tim_dur)}" start="{_s(tim_start)}" '
            f'offset="{_s(seg["src_start"])}" '
            f'format="{fmt_v}" tcStart="0s">'
            f'<audio><source-start>{_s(tim_start)}</source-start><source-duration>{_s(tim_dur)}</source-duration></audio>'
        )
        # optional color tweak + LUT note
        colpfx = ""
        if seg.get("color"):
            col = seg["color"]
            colpfx = _color_params(col)
        clip += colpfx + "</asset-clip>"
        spine_items.append((tim_start, "clip", clip))

        # outgoing transition to next
        next_seg = segments[i + 1] if i + 1 < len(segments) else None
        if next_seg is not None:
            ti = next_seg.get("transition_in") or seg.get("transition_out")
            ttype = (ti or {}).get("type", "cut")
            if ttype not in ("cut", "none", None):
                t_count += 1
                tid = f"tr{t_count}"
                dur = float(ti.get("duration", 0.5))
                fcp_name = _fcp_transition_name(ttype)
                trans_ids[seg["idx"]] = tid
                resources.append(
                    f'<transition id="{tid}" name="{fcp_name}" duration="{_s(dur)}"/>'
                )
                cut = next_seg["start"]
                t_start = max(seg["start"], cut - dur / 2)
                spine_items.append((t_start, "transition",
                                    f'<transition ref="{tid}" start="{_s(t_start)}" duration="{_s(dur)}"/>'))

    spine_items.sort(key=lambda x: x[0])
    spine = "\n          ".join(item for _, _, item in spine_items)
    # gap if first clip starts > 0
    if segments and segments[0]["start"] > 0:
        spine = f'<gap start="0s" duration="{_s(segments[0]["start"])}"/>\n          ' + spine

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE fcpxml>\n'
        f'<fcpxml version="1.9">\n'
        f'  <resources>\n{"    ".join(resources)}\n  </resources>\n'
        f'  <library>\n'
        f'    <event name="{escape(title)}">\n'
        f'      <project name="{escape(title)}">\n'
        f'        <sequence duration="{_s(total)}" format="{fmt_v}" tcStart="0s" tcFormat="NDF">\n'
        f'          <spine>\n          {spine}\n          </spine>\n'
        f'        </sequence>\n'
        f'      </project>\n'
        f'    </event>\n'
        f'  </library>\n'
        f'</fcpxml>\n'
    )
    return xml


def _color_params(col: dict) -> str:
    parts = []
    if col.get("sat", 1.0) != 1.0:
        parts.append(f'<adjust-color reference="1" saturationAmount="{round(col["sat"], 4)}"/>')
    if col.get("temp", 0) != 0:
        parts.append(f'<adjust-color reference="1" temperatureAmount="{round(col["temp"] * 100, 2)}"/>')
    return "\n" + "".join(parts)


def _fcp_transition_name(ttype: str) -> str:
    return {
        "dissolve": "Cross Dissolve",
        "crossfade": "Cross Dissolve",
        "cross": "Cross Dissolve",
        "fadeblack": "Dip to Black Dissolve",
        "dip": "Dip to Black Dissolve",
        "flash": "Flash",
        "wipeleft": "Wipe",
        "pushl": "Push",
    }.get(ttype, "Cross Dissolve")


def _last(segments) -> float:
    return segments[-1]["end"] if segments else 0.0