"""Premiere-compatible FCP7 XML (XMEML v5) export."""
from __future__ import annotations
from xml.sax.saxutils import escape


def _frames(sec: float, fps: float) -> int:
    return int(round(sec * fps))


def export_fcpxml_7(edit: dict, title: str = "Recreated") -> str:
    meta = edit["meta"]
    fps = int(round(float(meta["fps"])))
    segments = sorted(edit["segments"], key=lambda s: s["start"])
    total_frames = _frames(meta.get("duration", 0.0), fps)
    tc_start = 108000  # 01:00:00:00 at 30fps; scale by fps diff
    tc_start = _frames(3600.0, fps)

    parts: list[str] = []
    transitions: list[str] = []

    for i, seg in enumerate(segments):
        file_id = f"file-{i + 1}"
        clip_id = f"clip-{i + 1}"
        src_in = seg["src_start"]
        src_out = seg["src_end"]
        tim_in = tc_start + _frames(seg["start"], fps)
        tim_out = tc_start + _frames(seg["end"], fps)
        du = _frames(max(0.0, seg["end"] - seg["start"]), fps)
        src_du = _frames(max(0.0, src_out - src_in), fps)
        name = seg.get("name", "clip.mp4")
        clipitem = (
            f'<clipitem id="{clip_id}">\n'
            f'<name>{escape(name)}</name>\n'
            f'<enabled>TRUE</enabled>\n'
            f'<duration>{du}</duration>\n'
            f'<rate><timebase>{fps}</timebase></rate>\n'
            f'<start>{tim_in}</start>\n'
            f'<end>{tim_out}</end>\n'
            f'<in>{src_in * fps:.0f}</in>\n'
            f'<out>{src_out * fps:.0f}</out>\n'
            f'<file id="{file_id}">\n'
            f'<name>{escape(name)}</name>\n'
            f'<pathurl>file://{seg["file"]}</pathurl>\n'
            f'<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>\n'
            f'<duration>{src_du}</duration>\n'
            f'<timecode><rate><timebase>{fps}</timebase></rate><string>00:00:00:00</string></timecode>\n'
            f'<media>\n<video>\n'
            f'<samplecharacteristics>\n'
            f'<width>{int(meta.get("width", 1920))}</width>\n'
            f'<height>{int(meta.get("height", 1080))}</height>\n'
            f'<anamorphic>FALSE</anamorphic>\n'
            f'<pixelaspectratio>square</pixelaspectratio>\n'
            f'<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>\n'
            f'</samplecharacteristics>\n'
            f'</video>\n</media>\n'
            f'</file>\n'
            f'<sourcetrack><mediatype>video</mediatype><trackindex>1</trackindex></sourcetrack>\n'
            f'<masterclipid>{file_id}</masterclipid>\n'
            f'</clipitem>\n'
        )
        parts.append(clipitem)

        # after each clip, if next transition is a dissolve emit transition element
        nxt = segments[i + 1] if i + 1 < len(segments) else None
        if nxt:
            ti = nxt.get("transition_in") or seg.get("transition_out")
            ttype = (ti or {}).get("type", "cut")
            if ttype not in ("cut", "none", None):
                dur = _frames(float(ti.get("duration", 0.5)), fps)
                mid = _frames(nxt["start"], fps)
                transitions.append(
                    f'<transition id="t-{i}" >\n'
                    f'<rate><timebase>{fps}</timebase></rate>\n'
                    f'<start>{mid - dur // 2}</start>\n'
                    f'<end>{mid + dur - dur // 2}</end>\n'
                    f'<effect>\n'
                    f'<name>{_fcpt7_name(ttype)}</name>\n'
                    f'<effectid>{_fcpt7_name(ttype)}</effectid>\n'
                    f'<effectcategory>dissolve</effectcategory>\n'
                    f'</effect>\n'
                    f'<mediatime><rate><timebase>{fps}</timebase></rate><start>{mid - dur // 2}</start><end>{mid + dur - dur // 2}</end></mediatime>\n'
                    f'</transition>\n'
                )

    track_content = "\n".join(parts) + "\n" + "\n".join(transitions)

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE xmeml>\n'
        '<xmeml version="5">\n'
        '<sequence>\n'
        f'<name>{escape(title)}</name>\n'
        f'<duration>{total_frames}</duration>\n'
        f'<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>\n'
        f'<timecode>\n<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>\n'
        f'<string>01:00:00:00</string>\n<frame>{tc_start}</frame>\n'
        f'<displayformat>NDF</displayformat>\n</timecode>\n'
        f'<media>\n<video>\n<track>\n{track_content}\n</track>\n</video>\n'
        f'<audio>\n<track/>\n</audio>\n</media>\n'
        '</sequence>\n'
        '</xmeml>\n'
    )
    return xml


def _fcpt7_name(ttype: str) -> str:
    return {
        "dissolve": "Cross Dissolve",
        "crossfade": "Cross Dissolve",
        "cross": "Cross Dissolve",
        "dip": "Dip to Black Dissolve",
        "fadeblack": "Dip to Black Dissolve",
    }.get(ttype, "Cross Dissolve")