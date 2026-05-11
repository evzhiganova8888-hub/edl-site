"""Celery app для долгих задач (refund-таймер, рассылки). Расширим на Этапе 2/3."""
from __future__ import annotations

from celery import Celery

from src.core.config import settings

celery_app = Celery(
    "edl-os-bot",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    timezone=settings.timezone,
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
