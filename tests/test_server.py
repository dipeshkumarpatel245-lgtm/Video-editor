import pytest


@pytest.fixture(scope="module")
def running(client, fixture_files):
    r = client.post("/api/upload", data={"kind": "template"},
                    files={"file": ("demo.mp4", open(fixture_files["source"], "rb"), "video/mp4")})
    j = r.json()
    assert j["ok"]
    clip_ids = []
    for p in fixture_files["clips"]:
        rr = client.post("/api/upload", data={"kind": "clip"},
                         files={"file": (p.split("/")[-1], open(p, "rb"), "video/mp4")})
        clip_ids.append(rr.json()["file_id"])
    r = client.post("/api/analyze", data={"file_id": j["file_id"], "title": "Server Fixture"})
    assert r.status_code == 200
    return {"client": client, "template_id": r.json()["template_id"], "clip_ids": clip_ids}


def test_health(client):
    assert client.get("/health").json()["ok"] is True


def test_upload_and_analyze(running):
    r = running["client"].post("/api/recreate", data={
        "template_id": running["template_id"], "mode": "replace",
        "clip_ids": ",".join(running["clip_ids"])})
    j = r.json()
    assert j["ok"]
    eid = j["edit_id"]

    for fmt in ("fcpxml", "premiere", "edl", "capcut"):
        rr = running["client"].post("/api/export", data={"edit_id": eid, "fmt": fmt, "title": "T"})
        assert rr.status_code == 200, fmt
        assert len(rr.content) > 200


def test_render_endpoint(running):
    r = running["client"].post("/api/recreate", data={
        "template_id": running["template_id"], "mode": "recut",
        "clip_ids": ",".join(running["clip_ids"])})
    eid = r.json()["edit_id"]
    rr = running["client"].post("/api/render", data={"edit_id": eid, "width": 320, "height": 180, "fps": 24})
    assert rr.status_code == 200
    body = rr.json()
    assert body["ok"] is True
    assert body["render_url"].startswith("/api/render/stream/")
    assert body["size"] > 10000
    stream = running["client"].get(body["render_url"])
    assert stream.status_code == 200
    assert stream.headers["content-type"] == "video/mp4"
    assert len(stream.content) == body["size"]
    ranged = running["client"].get(body["render_url"], headers={"Range": "bytes=0-1023"})
    assert ranged.status_code == 206
    assert len(ranged.content) == 1024


def test_static_spa_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Video Template Studio" in r.content
    r = client.get("/app.js")
    assert r.status_code == 200