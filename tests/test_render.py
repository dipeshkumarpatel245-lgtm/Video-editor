import pytest

pytestmark = pytest.mark.slow


def test_render_replace_mp4(template, clip_features, tmp_path):
    from recreate.replace import build_replace_edit
    from recreate.render import render

    e = build_replace_edit(template, clip_features, source_audio=template["meta"].get("_source"))
    out = str(tmp_path / "replace.mp4")
    render(e, out, width=320, height=180, fps=24)
    from ffutils import probe_json

    info = probe_json(out)
    dur = float(info["format"]["duration"])
    assert 10 < dur < template["meta"]["duration"]
    assert info["streams"][0]["width"] == 320


def test_render_recut_mp4(template, clip_features, tmp_path):
    from recreate.recut import build_recut_edit
    from recreate.render import render

    e = build_recut_edit(template, clip_features, source_audio=template["meta"].get("_source"))
    out = str(tmp_path / "recut.mp4")
    render(e, out, width=320, height=180, fps=24)
    from ffutils import probe_json

    dur = float(probe_json(out)["format"]["duration"])
    assert dur > 5