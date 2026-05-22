"""Сводка метрик пилота — форматирование и пороги."""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")

from src.tasks.pilot_metrics import (
    TARGET_COMPLETION_RATE,
    TARGET_COUPON_USE_RATE,
    TARGET_PLUS_REVENUE_RUB,
    TARGET_REFUND_RATE,
    format_digest,
)


def test_targets_match_tz():
    """Пороги из ТЗ §11.3 пилота 5 клиентов."""
    assert TARGET_PLUS_REVENUE_RUB == 70_000  # 5 × 14к
    assert TARGET_COUPON_USE_RATE == 0.4       # ≥40% (2 из 5)
    assert TARGET_REFUND_RATE == 0.2           # ≤20% (1 из 5)
    assert TARGET_COMPLETION_RATE == 0.8       # ≥80%


def _sample_metrics(**overrides):
    base = {
        "window_days": 7,
        "total_paid": 5,
        "plus_count": 5,
        "completed": 5,
        "in_progress": 0,
        "refund_count": 1,
        "refund_rate": 0.2,
        "coupons_total": 5,
        "coupons_used": 2,
        "coupon_use_rate": 0.4,
        "avg_progress_minutes": 75,
        "avg_pdf_minutes": 4,
        "fallback_count": 0,
        "fallback_rate": 0.0,
        "completion_rate": 1.0,
        "plus_revenue_rub": 70_000,
        "avg_nps": 8.4,
        "nps_sample_size": 5,
    }
    base.update(overrides)
    return base


def test_digest_includes_all_sections():
    text = format_digest(_sample_metrics())
    for keyword in (
        "Сводка пилота",
        "Чекапы",
        "Воронка Plus → Диагностика",
        "Возвраты",
        "SLA",
        "Выручка Plus",
        "NPS",
    ):
        assert keyword in text


def test_digest_marks_passing_targets_with_check():
    text = format_digest(_sample_metrics())
    # Completion rate = 100% ≥ 80% → ✅
    # Coupon use rate = 40% ≥ 40% → ✅
    # Refund rate = 20% ≤ 20% → ✅
    assert "✅" in text


def test_digest_marks_failing_targets_with_warning():
    text = format_digest(_sample_metrics(
        refund_rate=0.4,             # 40% > 20% → ⚠
        coupon_use_rate=0.1,         # 10% < 40% → ⚠
        avg_progress_minutes=120,    # >90 мин → ⚠
        fallback_rate=0.3,           # 30% > 10% → ⚠
    ))
    assert "⚠️" in text


def test_digest_handles_no_data():
    text = format_digest(_sample_metrics(
        completed=0,
        avg_progress_minutes=None,
        avg_pdf_minutes=None,
        avg_nps=None,
        nps_sample_size=0,
    ))
    # Не падает на отсутствующих данных
    assert "—" in text or "нет данных" in text


def test_digest_formatted_for_telegram_markdown():
    text = format_digest(_sample_metrics())
    # Markdown заголовки и форматирование
    assert "*" in text  # bold/italic markers
    assert "•" in text  # bullets
