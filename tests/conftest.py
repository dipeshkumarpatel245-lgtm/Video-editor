"""Shared pytest fixtures: repo path, synthetic fixture videos, analyzed template."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.make_fixture import make_fixture  # noqa: E402


@pytest.fixture(scope="session")
def fixture_files() -> dict:
    """Build (if missing) and return paths to the synthetic videos."""
    return make_fixture(REPO / "tests")


@pytest.fixture(scope="session")
def template(fixture_files) -> dict:
    """Analyze the fixture source once; reuse across tests."""
    from template.schema import load
    from template import builder
    from config import TEMPLATE_DIR

    out = TEMPLATE_DIR / "test_fixture_template.json"
    if out.exists():
        return load(str(out))
    from analysis.pipeline import analyze

    t = analyze(str(fixture_files["source"]))
    t["meta"]["title"] = "Fixture Template"
    t["meta"]["_source"] = str(fixture_files["source"])
    from template.schema import save

    save(t, str(out))
    return load(str(out))


@pytest.fixture(scope="session")
def clip_features(fixture_files) -> list:
    from recreate.matching import clip_feature

    return [clip_feature(str(p)) for p in sorted(fixture_files["clips"])]


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from server.main import app

    return TestClient(app)