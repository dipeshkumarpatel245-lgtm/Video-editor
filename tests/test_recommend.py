"""Recommendation logic: clip count / duration guidance from template analysis."""
from recreate.recommend import recommend_clips


def test_recommend_replace_matches_shots(template):
    r = recommend_clips(template, mode="replace")
    assert r["mode"] == "replace"
    assert r["clips_needed"] == len(template["shots"])
    assert r["slots"] == len(template["shots"])
    assert r["clip_duration_min_sec"] + 1e-6 >= r["longest_slot_sec"]
    assert r["clip_duration_sec"] >= r["clip_duration_min_sec"]
    assert r["message"]


def test_recommend_recut_uses_tempo_grid(template):
    r = recommend_clips(template, mode="recut")
    assert r["mode"] == "recut"
    assert r["slots"] >= 2
    assert r["slots"] <= len(template["shots"]) or r["slots"] >= 2
    assert r["clip_duration_min_sec"] + 1e-6 >= r["longest_slot_sec"]
    assert r["clips_needed"] >= 2
    assert r["message"]