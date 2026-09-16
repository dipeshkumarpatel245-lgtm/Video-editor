import pytest


def test_template_is_valid(template):
    from template.schema import validate

    problems = validate(template)
    assert problems == [], problems
    assert template["meta"]["duration"] == pytest.approx(21.0, abs=1.5)
    assert template["meta"]["resolution"][0] > 0


def test_tempo_and_beats(template):
    assert template.get("tempo", 0) > 0
    # 120 BPM source -> tracker should land in a sane window
    assert 100 <= template.get("tempo", 0) <= 145
    beatmap = template["beatmap"]
    assert len(beatmap) >= 5
    ts = [b["t"] for b in beatmap]
    assert sorted(ts) == ts


def test_shots_detected(template):
    shots = template["shots"]
    assert len(shots) >= 5
    for sh in shots:
        assert sh["end"] > sh["start"]
        assert sh["start"] >= -1e-6


def test_loudness_curve(template):
    loud = template.get("loudness", {})
    assert "integrated_lufs" in loud
    curve = loud.get("curve", [])
    assert len(curve) > 0


def test_structure_and_motion(template):
    assert template.get("pacing") is not None
    assert len(template.get("shots", [])) > 0
    assert any("motion" in sh for sh in template["shots"])
    assert isinstance(template.get("freezes"), list)