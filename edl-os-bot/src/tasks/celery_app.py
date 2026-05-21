"""Celery app + beat schedule для долгих задач (§6.1 ТЗ v3).

Воскресенье 18:00 МСК — перед началом рабочей недели команда EDL смотрит
сводку + список накопленных багов из @edl_os_bot.
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from src.core.config import settings

celery_app = Celery(
    "edl-os-bot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "src.tasks.refund_check",
        "src.tasks.weekly_voc",
        "src.tasks.notify_plus_video",  # F8
        "src.tasks.expire_coupons",     # 24h TTL для купонов (21.05.2026)
    ],
)
celery_app.conf.update(
    timezone=settings.timezone,
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    beat_schedule={
        "refund-window-check-every-hour": {
            "task": "src.tasks.refund_check.expire_refund_window",
            "schedule": crontab(minute=0),
        },
        # Воскресенье 18:00 МСК — перед началом рабочей недели Катя смотрит
        # сводку + список накопленных багов из @edl_os_bot.
        "weekly-voc-sunday-1800-msk": {
            "task": "src.tasks.weekly_voc.run_weekly",
            "schedule": crontab(hour=18, minute=0, day_of_week="sun"),
        },
        # Каждые 15 минут проверяем просроченные купоны и помечаем status=expired.
        # Корректность не зависит от этого джоба (двойная проверка по времени
        # есть в каждом клиентском пути в coupon_engine), но он держит
        # колонку status актуальной для аналитики и /coupon_info.
        "coupons-expire-overdue-every-15min": {
            "task": "src.tasks.expire_coupons.run_expire_coupons",
            "schedule": crontab(minute="*/15"),
        },
    },
)
