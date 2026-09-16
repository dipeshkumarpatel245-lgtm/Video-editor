"""Celery task wrappers around the analysis/recreate/export/render pipeline.

These run on the GPU/CPU worker containers; the FastAPI server pushes work
here and fetches results back. Each task is a thin wrapper over the same
library functions the synchronous API uses.
"""
from __future__ import annotations

import json
from pathlib import Path

from analysis.pipeline import analyze
from template import builder
from template.schema import validate
from recreate.matching import clip_feature
from recreate.replace import build_replace_edit
from recreate.recut import build_recut_edit
from recreate.render import render as render_edit
from export import export, export_capcut
from config import MEDIA_DIR, EDIT_DIR, RENDER_DIR, EXPORT_DIR
from workers.celery_app import celery_app


def _media(fid: str) -> str:
    return str(MEDIA_DIR / f"{fid}.mp4")


@celery_app.task(name="workers.tasks.analyze_task", bind=True)
def analyze_task(self, file_id: str, title: str = ""):
    """Analyze template video; store template; return its id + summary."""
    def progress(p: float, msg: str):
        self.update_state(state="PROGRESS", meta={"percent": p, "step": msg})

    template = analyze(_media(file_id), progress=progress)
    template["meta"]["title"] = title or file_id
    template["meta"]["_source"] = _media(file_id)
    problems = validate(template)
    if problems:
        raise ValueError("invalid template: " + "; ".join(problems))
    tid = f"template_{self.request.id[:12]}"
    builder.store(template, tid)
    return {
        "template_id": tid,
        "duration": template["meta"]["duration"],
        "shots": len(template.get("shots", [])),
        "beats": len(template.get("beatmap", [])),
        "tempo": template.get("tempo"),
    }


@celery_app.task(name="workers.tasks.recreate_task")
def recreate_task(template_id: str, mode: str, clip_ids: list[str]):
    template = builder.fetch(template_id)
    clips = [clip_feature(_media(cid)) for cid in clip_ids]
    source_audio = template.get("meta", {}).get("_source") or _media(clip_ids[0])
    build = build_replace_edit if mode == "replace" else build_recut_edit
    edit = build(template, clips, source_audio=source_audio)
    eid = f"edit_{template_id.split('_')[-1]}_{mode}"
    (EDIT_DIR / f"{eid}.json").write_text(json.dumps(edit))
    return {"edit_id": eid, "duration": edit["meta"]["duration"],
            "segments": len(edit["segments"]), "mode": mode}


@celery_app.task(name="workers.tasks.export_task")
def export_task(edit_id: str, fmt: str, title: str = "Recreated"):
    edit = json.loads((EDIT_DIR / f"{edit_id}.json").read_text())
    if fmt in ("fcpxml", "premiere", "edl"):
        name, data, mime = export(edit, fmt, title)
        out = EXPORT_DIR / edit_id / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        return {"file": str(out), "mime": mime, "name": name}
    if fmt == "capcut":
        out_dir = export_capcut(edit, title)
        return {"dir": out_dir}
    raise KeyError(fmt)


@celery_app.task(name="workers.tasks.render_task")
def render_task(edit_id: str, width: int = 720, height: int = 404, fps: int = 30):
    edit = json.loads((EDIT_DIR / f"{edit_id}.json").read_text())
    out = RENDER_DIR / f"{edit_id}_preview.mp4"
    render_edit(edit, str(out), width=max(2, width), height=max(2, height), fps=fps)
    return {"file": str(out), "size": out.stat().st_size}