"""Shot-boundary sanitisation (phantom ends beyond media duration)."""
from template.builder import sanitize_shots
from recreate.recommend import recommend_clips


def test_sanitize_clamps_phantom_last_shot():
    t = {
        "meta": {"duration": 13.9167},
        "shots": [
            {"start": 0.0, "end": 4.5, "idx": 0},
            {"start": 12.3, "end": 30.3, "idx": 1},
        ],
    }
    out = sanitize_shots(t)["shots"]
    assert out[-1]["end"] == 13.9167
    assert all(s["start"] >= 0 and s["end"] <= 13.9167 for s in out)


def test_sanitize_drops_degenerate_and_merges_overlap():
    t = {
        "meta": {"duration": 10.0},
        "shots": [
            {"start": 0.0, "end": 4.0},
            {"start": 3.5, "end": 5.0},
            {"start": 6.0, "end": 6.0},
            {"start": 8.0, "end": 99.0},
        ],
    }
    out = sanitize_shots(t)["shots"]
    assert [round(s["start"], 3) for s in out] == [0.0, 8.0]
    assert [round(s["end"], 3) for s in out] == [5.0, 10.0]
    for s in out:
        assert s["end"] - s["start"] > 1e-4
        assert s["end"] <= 10.0


def test_recommend_ignores_phantom_end():
    t = {
        "meta": {"duration": 18.3438, "title": "t"},
        "beatmap": [],
        "shots": [
            {"start": 0.0, "end": 3.5, "idx": 0},
            {"start": 14.2, "end": 43.3, "idx": 1},
        ],
    }
    r = recommend_clips(sanitize_shots(t), "replace")
    assert r["longest_slot_sec"] <= 18.3438
    assert r["clip_duration_sec"] < 18.3438 * 1.6
    assert "43" not in r["message"]