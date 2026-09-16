"""Celery application for the Video Template Studio worker."""
from __future__ import annotations

from celery import Celery

from config import BROKER_URL

celery_app = Celery(
    "videotemplate",
    broker=BROKER_URL,
    backend=BROKER_URL,
    include=["workers.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "workers.tasks.analyze_task": {"queue": "analysis"},
        "workers.tasks.render_task": {"queue": "render"},
        "workers.tasks.export_task": {"queue": "analysis"},
        "workers.tasks.recreate_task": {"queue": "analysis"},
    },
)