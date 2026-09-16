"""REST API for the Video→Template→Recreate web app."""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse

from config import (MEDIA_DIR, EDIT_DIR, RENDER_DIR, ANALYSIS_DIR, LUT_DIR,
                    EXPORT_DIR, new_id)
from analysis.pipeline import analyze
from template import builder
from template.schema import validate
from recreate.matching import clip_feature
from recreate.replace import build_replace_edit
from recreate.recut import build_recut_edit
from recreate.render import render as render_edit
from recreate.recommend import recommend_clips
from export import export, export_capcut, export_capcut_package
from ffutils import probe_json

router = APIRouter(prefix="/api")


def _ok(**kw) -> dict:
    kw.setdefault("ok", True)
    return kw


def _media_path(file_id: str) -> Path:
    p = MEDIA_DIR / f"{file_id}.mp4"
    if not p.exists():
        raise HTTPException(404, f"media {file_id} not found")
    return p


@router.post("/upload")
async def upload(kind: str = Form("template"), file: UploadFile = File(...)):
    """Accept a media file; kind = template|clip."""
    if kind not in ("template", "clip"):
        raise HTTPException(400, "kind must be 'template' or 'clip'")
    fid = new_id(kind)
    dest = MEDIA_DIR / f"{fid}.mp4"
    with dest.open("wb") as out:
        while chunk := await file.read(1 << 20):
            out.write(chunk)
    try:
        raw = probe_json(str(dest))
        info = {}
        for s in raw.get("streams", []):
            if s.get("codec_type") == "video":
                info = {**info, **{k: s.get(k) for k in ("width", "height", "duration", "r_frame_rate")},
                        "duration": float(s.get("duration") or raw.get("format", {}).get("duration") or 0.0)}
        if "width" not in info:
            raise ValueError("no video stream")
    except Exception:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, "file is not a usable video")
    return _ok(file_id=fid, kind=kind, size=dest.stat().st_size,
               duration=float(info.get("duration", 0.0)),
               width=int(info.get("width", 0)), height=int(info.get("height", 0)))


@router.post("/analyze")
async def do_analyze(file_id: str = Form(...), title: str = Form("")):
    """Analyze a template video into a canonical template."""
    src = _media_path(file_id)
    template = analyze(str(src))
    template["meta"]["title"] = title or src.stem.replace("template_", "", 1)
    template["meta"]["_source"] = str(src)
    validate(template)
    tid = new_id("template")
    builder.store(template, tid)
    return _ok(template_id=tid, title=template["meta"]["title"],
               duration=template["meta"]["duration"],
               beats=len(template.get("beatmap", [])),
               shots=len(template.get("shots", [])),
               tempo=template.get("tempo"),
               recommendation=recommend_clips(template),
               summary=_summary(template))


def _summary(t: dict) -> dict:
    structure = t.get("structure") or {}
    if isinstance(structure, dict):
        acts = [a.get("label") for a in structure.get("acts", [])]
    elif isinstance(structure, list):
        acts = [a.get("label") for a in structure if isinstance(a, dict)]
    else:
        acts = []
    return {
        "resolution": t["meta"].get("resolution"),
        "fps": t["meta"].get("fps"),
        "tempo": t.get("tempo"),
        "loudness": t.get("loudness"),
        "acts": acts,
    }


@router.get("/templates")
async def list_templates():
    items = []
    tdir = builder.default_template_path("_").parent
    for p in sorted(tdir.glob("*.json")):
        t = json.loads(p.read_text())
        items.append({"id": p.stem, "title": t["meta"].get("title", p.stem),
                      "duration": t["meta"].get("duration"),
                      "shots": len(t.get("shots", []))})
    items.sort(key=lambda i: i["id"])
    return _ok(templates=items)


@router.get("/templates/{template_id}")
async def get_template(template_id: str):
    if not builder.exists(template_id):
        raise HTTPException(404, "template not found")
    return builder.fetch(template_id)


@router.get("/templates/{template_id}/viz")
async def template_viz(template_id: str):
    """Slim visualization payload for the SPA storyboard (no heavy per-shot features/LUT)."""
    if not builder.exists(template_id):
        raise HTTPException(404, "template not found")
    t = builder.fetch(template_id)
    meta = t.get("meta") or {}
    shots = []
    for s in t.get("shots") or []:
        shots.append({
            "start": s.get("start"),
            "end": s.get("end"),
            "duration": round(float(s.get("end", 0.0)) - float(s.get("start", 0.0)), 4),
            "color": {k: s.get("color", {}).get(k) for k in ("mean_rgb", "sat", "temp", "luma", "tags") if k in (s.get("color") or {})},
            "motion": {"classification": (s.get("motion") or {}).get("classification")}
            if isinstance(s.get("motion"), dict) else {},
            "transition": {
                "in": (s.get("transition_in") or {}).get("type"),
                "out": (s.get("transition_out") or {}).get("type"),
            },
        })
    curve = (t.get("loudness") or {}).get("curve") or []
    step = max(1, int(len(curve) / 200))
    structure = t.get("structure") or []
    if isinstance(structure, dict):
        structure = structure.get("acts") or structure.get("segments") or []
    return _ok(template_id=template_id,
               title=meta.get("title"),
               duration=meta.get("duration"),
               fps=meta.get("fps"),
               resolution=meta.get("resolution"),
               tempo=t.get("tempo"),
               shots=shots,
               beats=[{"t": b.get("t"), "strength": b.get("strength")}
                      for b in (t.get("beatmap") or [])],
               loudness=[{"t": c.get("t"), "db": c.get("db")} for c in curve[::step]],
               structure=[{"act": (a.get("label") or a.get("act")) if isinstance(a, dict) else a,
                           "start": a.get("start"), "end": a.get("end")}
                          for a in structure if isinstance(a, dict)],
               )


@router.post("/recreate")
async def do_recreate(template_id: str = Form(...), mode: str = Form("replace"),
                      clip_ids: str = Form("")):
    """Build a recreated edit; clip_ids = comma-separated file ids."""
    if mode not in ("replace", "recut"):
        raise HTTPException(400, "mode must be 'replace' or 'recut'")
    if not builder.exists(template_id):
        raise HTTPException(404, "template not found")
    template = builder.fetch(template_id)
    ids = [cid.strip() for cid in clip_ids.split(",") if cid.strip()]
    if not ids:
        raise HTTPException(400, "need at least one clip")
    clips = []
    for cid in ids:
        src = _media_path(cid)
        clips.append(clip_feature(str(src)))
    # audio bed: use the template's own source when available, else first clip
    source_audio = template.get("meta", {}).get("_source") or str(MEDIA_DIR / ids[0])
    build = build_replace_edit if mode == "replace" else build_recut_edit
    edit = build(template, clips, source_audio=source_audio)
    eid = new_id("edit")
    (EDIT_DIR / f"{eid}.json").write_text(json.dumps(edit))
    return _ok(edit_id=eid, mode=mode, duration=edit["meta"]["duration"],
               segments=len(edit["segments"]),
               recommendation=recommend_clips(template, mode),
               assignment=edit.get("assignment", []))


@router.get("/edits/{edit_id}")
async def get_edit(edit_id: str):
    return json.loads(_edit_path(edit_id).read_text())


@router.post("/export")
async def do_export(edit_id: str = Form(...), fmt: str = Form("fcpxml"),
                    title: str = Form("Recreated")):
    """Export an edit to an editor format and return the file."""
    edit = json.loads(_edit_path(edit_id).read_text())
    if fmt in ("fcpxml", "premiere", "edl"):
        name, data, mime = export(edit, fmt, title)
        ext_dir = EXPORT_DIR / new_id("x")
        ext_dir.mkdir(parents=True, exist_ok=True)
        path = ext_dir / name
        path.write_bytes(data)
        return FileResponse(path, media_type=mime, filename=name)
    if fmt == "capcut":
        ext_dir = EXPORT_DIR / new_id("capcut")
        draft = export_capcut(edit, title)
        zip_path = shutil.make_archive(str(ext_dir), "zip", root_dir=str(Path(draft).parent),
                                       base_dir=Path(draft).name)
        return FileResponse(zip_path, media_type="application/zip",
                            filename=f"{title}_capcut.zip")
    if fmt == "capcut_pkg":
        ext_dir = EXPORT_DIR / new_id("x")
        pkg = Path(export_capcut_package(edit, title))
        zip_path = shutil.make_archive(str(ext_dir), "zip", root_dir=str(pkg))
        return FileResponse(zip_path, media_type="application/zip",
                            filename=f"{title}_capcut_media.zip")
    raise HTTPException(400, f"unknown format {fmt}")


@router.post("/render")
async def do_render(edit_id: str = Form(...), width: int = Form(720), height: int = Form(404),
                    fps: int = Form(30)):
    """Render a preview MP4 of the edit (returns a streamable URL)."""
    edit = json.loads(_edit_path(edit_id).read_text())
    out = RENDER_DIR / f"{edit_id}_{max(2, width)}x{max(2, height)}@{max(1, fps)}fps.mp4"
    progress = []
    render_edit(edit, str(out), width=max(2, width), height=max(2, height), fps=fps,
                progress_hook=progress.append)
    return _ok(render_url=f"/api/render/stream/{out.name}", name=out.name,
               size=out.stat().st_size)


@router.get("/render/stream/{name}")
async def stream_render(name: str):
    p = RENDER_DIR / Path(name).name
    if not p.exists() or not p.is_file():
        raise HTTPException(404, "render not found")
    return FileResponse(p, media_type="video/mp4", filename=p.name,
                        content_disposition_type="inline",
                        headers={"Cache-Control": "no-store", "Accept-Ranges": "bytes"})


def _edit_path(edit_id: str) -> Path:
    p = EDIT_DIR / f"{edit_id}.json"
    if not p.exists():
        raise HTTPException(404, "edit not found")
    return p