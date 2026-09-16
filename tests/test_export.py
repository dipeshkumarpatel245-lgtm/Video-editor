import xml.etree.ElementTree as ET

import pytest


@pytest.mark.parametrize("fmt,ext,mime", [
    ("fcpxml", "fcpxml", "application/xml"),
    ("premiere", "xml", "application/xml"),
    ("edl", "edl", "text/plain"),
])
def test_export_formats(template, clip_features, fmt, ext, mime):
    from recreate.replace import build_replace_edit
    from export import export

    e = build_replace_edit(template, clip_features)
    name, data, mt = export(e, fmt, "T")
    assert name.endswith(f".{ext}")
    assert mt == mime
    assert len(data) > 200

    text = data.decode("utf-8", "replace")
    if fmt == "fcpxml":
        ET.fromstring(text)  # well-formed
    elif fmt == "premiere":
        ET.fromstring(text)
    else:
        assert text.strip().startswith("TITLE")


def test_export_capcut_draft(template, clip_features):
    from recreate.replace import build_replace_edit
    from export import export_capcut

    e = build_replace_edit(template, clip_features)
    out = export_capcut(e, "DraftTest")
    import json, glob

    files = glob.glob(out + "/**/*", recursive=True)
    assert any(f.endswith("draft_content.json") for f in files)
    content = json.loads(open(glob.glob(out + "/draft_content.json")[0]).read())
    assert content  # non-empty draft


def _tc_to_sec(tc: str, fps: float = 30.0) -> float:
    h, m, s, f = (int(x) for x in tc.split(":"))
    return h * 3600 + m * 60 + s + f / fps


def test_edl_times_are_monotonic(template, clip_features):
    from recreate.replace import build_replace_edit
    from export import export

    e = build_replace_edit(template, clip_features)
    _, data, _ = export(e, "edl", "T")
    rec_ins = []
    for line in data.decode().splitlines():
        parts = line.split()
        if len(parts) >= 7 and parts[0].isdigit():
            rec_ins.append(_tc_to_sec(parts[5]))
    assert len(rec_ins) == len(e["segments"])
    assert rec_ins == sorted(rec_ins)