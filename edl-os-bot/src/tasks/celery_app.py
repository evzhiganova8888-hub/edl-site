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
        "src.tasks.checkup_failsafe",   # 5-мин fail-safe (ТЗ AC4)
        "src.tasks.dormant_checkup",    # EC2 — мягкое напоминание 14д + dormant 30д
        "src.tasks.pilot_metrics",      # дневная сводка метрик пилота
        "src.tasks.issue_plus_coupon",  # T+24ч после Plus-видео — авто-купон
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
        # 5-минутный fail-safe для активных Чекапов (ТЗ §3.6, AC4).
        # Каждую минуту сканируем applications с тишиной > 5 мин и
        # отправляем единожды напоминание.
        "checkup-failsafe-every-minute": {
            "task": "src.tasks.checkup_failsafe.run_failsafe_scan",
            "schedule": crontab(minute="*"),
        },
        # Раз в сутки в 11:00 МСК проверяем dormant-Чекапы (EC2):
        # 14 дней — мягкое напоминание, 30 дней — пометка «начать заново».
        "dormant-checkup-daily-1100-msk": {
            "task": "src.tasks.dormant_checkup.run_dormant_scan",
            "schedule": crontab(hour=11, minute=0),
        },
        # Дневная сводка метрик пилота → в @evzhiganova/админ-чат каждое утро.
        "pilot-metrics-daily-0900-msk": {
            "task": "src.tasks.pilot_metrics.run_daily_digest",
            "schedule": crontab(hour=9, minute=0),
        },
    },
)
