"""Template visualization payload: slim, sanitized, SPA-ready."""
from config import new_id
from template.builder import store
from fastapi.testclient import TestClient
from server.main import app


def _store_rich() -> str:
    tid = new_id("template")
    store({
        "meta": {"duration": 13.0, "title": "T", "fps": 30, "resolution": [720, 404]},
        "tempo": 120.0,
        "beatmap": [{"t": 0.0, "strength": 1.0}, {"t": 0.5, "strength": 200.0}],
        "loudness": {"curve": [{"t": 0.0, "db": -20.0}, {"t": 1.0, "db": -5.0}]},
        "structure": [{"act": "intro", "start": 0.0, "end": 4.0}],
        "shots": [
            {"start": 0.0, "end": 4.0, "idx": 0,
             "color": {"mean_rgb": [0.5, 0.1, 0.2], "sat": 1.2, "temp": 0.1, "luma": 0.2, "tags": ["warm"]},
             "motion": {"classification": "pan"},
             "transition_in": None, "transition_out": {"type": "cut"}},
            {"start": 4.0, "end": 99.0, "idx": 1},
        ],
        "color_look": {"matrix": [1.0] * 9, "lut": "LUT..."},
    }, tid)
    return tid


def test_viz_slim_and_sanitized():
    tid = _store_rich()
    j = TestClient(app).get(f"/api/templates/{tid}/viz").json()
    assert j["ok"]
    assert j["shots"][1]["end"] == 13.0          # phantom end clamped to duration
    assert j["shots"][0]["color"]["mean_rgb"] == [0.5, 0.1, 0.2]
    assert j["tempo"] == 120.0 and j["structure"] and j["beats"] and j["loudness"]
    assert "feature" not in str(j["shots"]) and "content" not in str(j["shots"])
    assert "color_look" not in j


def test_viz_missing_template():
    r = TestClient(app).get("/api/templates/does_not_exist_zz/viz")
    assert r.status_code == 404


def test_viz_empty_structure_still_ok():
    tid = new_id("template")
    store({
        "meta": {"duration": 5.0, "title": "E"},
        "tempo": None,
        "shots": [{"start": 0.0, "end": 5.0, "idx": 0}],
    }, tid)
    j = TestClient(app).get(f"/api/templates/{tid}/viz").json()
    assert j["ok"] and j["shots"] and j["structure"] == [] and j["beats"] == []