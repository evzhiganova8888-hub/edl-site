"""Бриф-форматтер для Sales-чата."""
from datetime import datetime, timezone
from types import SimpleNamespace

from src.core.notifications import (
    build_lead_brief,
    build_payment_success_brief,
    build_refund_request_brief,
)


def _user(**kwargs):
    defaults = dict(
        id=1,
        telegram_id=12345,
        telegram_username="katya",
        first_name="Катя",
        last_name="Жиганова",
        segment="services_legal",
        sub_profile="ai_threat",
        stage="warm",
        email=None,
        phone=None,
        company_name="EDL OS",
        company_size=8,
        company_revenue_range="<30M",
        quiz_score=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _app(**kwargs):
    defaults = dict(id="app-uuid", type="audit", source="purchase_intent")
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_lead_brief_contains_segment_and_sla():
    text = build_lead_brief(user=_user(), application=_app(), extra_context="маржа упала")
    assert "Юр-консалтинг" in text
    assert "warm" in text
    assert "ai_threat" in text
    assert "24 рабочих часа" in text
    assert "маржа упала" in text


def test_payment_brief_has_amount_and_email():
    user = _user(email="x@y.ru")
    text = build_payment_success_brief(
        user=user, application=_app(), amount_rub=9000.0, receipt_url="https://r/1"
    )
    assert "9000" in text
    assert "x@y.ru" in text
    assert "audit" in text


def test_refund_brief_has_reason():
    text = build_refund_request_brief(
        user=_user(), application=_app(), reason="не разобрались с маржей"
    )
    assert "ЗАПРОС ВОЗВРАТА" in text
    assert "не разобрались" in text
