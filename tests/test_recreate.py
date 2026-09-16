from edit import lint, recompute_duration


def test_replace_preserves_timing(template, clip_features):
    from recreate.replace import build_replace_edit

    e = build_replace_edit(template, clip_features, source_audio=template["meta"].get("_source"))
    assert lint(e) == [], lint(e)
    assert e["meta"]["mode"] == "replace"
    assert len(e["segments"]) == len(template["shots"])
    d = e["meta"]["duration"]
    assert abs(d - template["meta"]["duration"]) < 0.1
    # every slot got a clip (no empty files)
    assert all(s["file"] for s in e["segments"])


def test_recut_is_contiguous(template, clip_features):
    from recreate.recut import build_recut_edit

    e = build_recut_edit(template, clip_features, source_audio=template["meta"].get("_source"))
    assert lint(e) == [], lint(e)
    pref = 0.0
    for s in e["segments"]:
        assert abs(s["start"] - pref) < 1e-4, s["idx"]
        pref = s["end"]
    assert abs(pref - template["meta"]["duration"]) < 0.1
    assert all(s["file"] for s in e["segments"])
    assert len(e["segments"]) > len(template["shots"])  # beat-level granularity


def test_shot_assignment_matches_slots(template, clip_features):
    from recreate.matching import assign

    a = assign(template, clip_features)
    assert len(a) == len(template["shots"])
    # all slots have either a valid clip or are marked unassigned (fill handled by builder)
    assert all(x["clip_idx"] is None or 0 <= x["clip_idx"] < len(clip_features) for x in a)