"""Pricing single-source-of-truth check (§I.4 v3.1, вариант 2).

Сверяет цены в коде с ценами в KB и `texts.py`. При расхождении тест
падает — это форсирует синхронные правки во всех местах при изменении
прайса. Не БД-driven, но дешевле и быстрее.
"""
from __future__ import annotations

from pathlib import Path

from src.bot import texts
from src.bot.handlers import audit

_KB_PRICING = Path(__file__).resolve().parent.parent / "src" / "knowledge_base" / "02_products_pricing.md"


def test_audit_base_price_consistency():
    """9 000 ₽ — в константе кода, в KB и в текстах."""
    assert audit.AUDIT_AMOUNT_RUB == 9000.0
    kb_text = _KB_PRICING.read_text(encoding="utf-8")
    assert "9 000" in kb_text or "9000" in kb_text
    assert "9 000" in texts.AUDIT_INTRO


def test_audit_plus_price_consistency():
    """14 000 ₽ Plus — в константе, в KB, в текстах."""
    assert audit.AUDIT_PLUS_AMOUNT_RUB == 14000.0
    kb_text = _KB_PRICING.read_text(encoding="utf-8")
    assert "14 000" in kb_text or "14000" in kb_text
    assert "14 000" in texts.AUDIT_INTRO


def test_sprint_prices_in_kb():
    """135 / 185 / 260 тыс. ₽ — в KB; константы кода нет (через LLM/тексты)."""
    kb_text = _KB_PRICING.read_text(encoding="utf-8")
    for price in ("135", "185", "260"):
        assert price in kb_text, f"price {price}k not found in KB"
    assert "135" in texts.SPRINT_WAITLIST_INTRO
    assert "185" in texts.SPRINT_WAITLIST_INTRO
    assert "260" in texts.SPRINT_WAITLIST_INTRO


def test_diagnostic_price():
    """45 000 ₽ — в KB и в тексте (TZ_checkup_plus_v2.md §8.4, SoT v1.5)."""
    kb_text = _KB_PRICING.read_text(encoding="utf-8")
    assert "45 000" in kb_text or "45000" in kb_text
    assert "45 000" in texts.DIAGNOSTIC_INTRO


def test_plan_amount_helper():
    """audit._plan_amount возвращает правильные числа для base/plus."""
    assert audit._plan_amount(audit.PLAN_BASE) == 9000.0
    assert audit._plan_amount(audit.PLAN_PLUS) == 14000.0
    assert audit._plan_amount("unknown") == 9000.0  # fallback на base


def test_plan_description_helper():
    """audit._plan_description — разные тексты для Базового и Plus."""
    base_desc = audit._plan_description(audit.PLAN_BASE)
    plus_desc = audit._plan_description(audit.PLAN_PLUS)
    assert "Plus" in plus_desc
    assert "Plus" not in base_desc
