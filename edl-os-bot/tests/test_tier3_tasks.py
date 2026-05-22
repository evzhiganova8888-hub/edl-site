"""TIER 3 celery tasks — fail-safe, dormant, plus-coupon scheduler.

Тесты smoke-уровня: модули корректно импортируются, celery task'и
зарегистрированы, шаблоны/тексты содержат правильные ключевые фразы.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")


def test_failsafe_module_imports_and_task_registered():
    from src.tasks import checkup_failsafe
    from src.tasks.celery_app import celery_app

    assert hasattr(checkup_failsafe, "run_failsafe_scan")
    # Task должен быть зарегистрирован под полным именем
    assert "src.tasks.checkup_failsafe.run_failsafe_scan" in celery_app.tasks


def test_failsafe_threshold_is_5_minutes():
    """ТЗ §3.6 + AC4: ровно 5 минут."""
    from datetime import timedelta
    from src.tasks.checkup_failsafe import FAILSAFE_THRESHOLD

    assert FAILSAFE_THRESHOLD == timedelta(minutes=5)


def test_dormant_thresholds_14_and_30_days():
    """ТЗ §3.6 + EC2: 14 дней — soft, 30 дней — dormant."""
    from src.tasks.dormant_checkup import DORMANT_DAYS, SOFT_REMINDER_DAYS

    assert SOFT_REMINDER_DAYS == 14
    assert DORMANT_DAYS == 30


def test_dormant_module_registered():
    from src.tasks import dormant_checkup
    from src.tasks.celery_app import celery_app

    assert hasattr(dormant_checkup, "run_dormant_scan")
    assert "src.tasks.dormant_checkup.run_dormant_scan" in celery_app.tasks


def test_plus_coupon_scheduler_registered():
    from src.tasks import issue_plus_coupon
    from src.tasks.celery_app import celery_app

    assert hasattr(issue_plus_coupon, "schedule_plus_coupon")
    assert "src.tasks.issue_plus_coupon.schedule_plus_coupon" in celery_app.tasks


def test_pilot_metrics_registered():
    from src.tasks import pilot_metrics
    from src.tasks.celery_app import celery_app

    assert hasattr(pilot_metrics, "run_daily_digest")
    assert "src.tasks.pilot_metrics.run_daily_digest" in celery_app.tasks


def test_beat_schedule_contains_new_tasks():
    """Все TIER 3 джобы есть в beat_schedule."""
    from src.tasks.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    expected = {
        "checkup-failsafe-every-minute",
        "dormant-checkup-daily-1100-msk",
        "pilot-metrics-daily-0900-msk",
        "coupons-expire-overdue-every-15min",
    }
    assert expected.issubset(set(schedule.keys()))


def test_video_brief_contains_cheat_sheet_when_answers_have_digits():
    """Auto cheat-sheet выбирает ответы с цифрами (ТЗ §7.3)."""
    from src.tasks.notify_plus_video import _build_cheat_sheet

    class FakeAnswer:
        def __init__(self, layer, text, is_decline=False):
            self.layer = layer
            self.text = text
            self.is_decline = is_decline

    answers = [
        FakeAnswer("money", "P&L закрываем к 17 числу, маржа 42%, runway 2.4 месяца"),
        FakeAnswer("operations", "Онбординг 32 часа на клиента, ~160к ₽ моего времени"),
        FakeAnswer("strategy", "Не знаю", is_decline=True),
        FakeAnswer("funnel", "Цикл сделки 31 день, конверсия 22%"),
    ]
    cheat = _build_cheat_sheet(answers)
    assert "MONEY" in cheat or "money" in cheat.upper()
    assert "P&L" in cheat or "маржа" in cheat
    # Decline-ответ не должен попасть
    assert "Не знаю" not in cheat


def test_video_brief_cheat_sheet_fallback_when_no_digits():
    from src.tasks.notify_plus_video import _build_cheat_sheet

    class FakeAnswer:
        def __init__(self, layer, text, is_decline=False):
            self.layer = layer
            self.text = text
            self.is_decline = is_decline

    answers = [FakeAnswer("money", "у нас нормально", is_decline=False)]
    cheat = _build_cheat_sheet(answers)
    assert "цифровых ответов не найдено" in cheat.lower()
