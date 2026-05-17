"""F2: НДС-флажок — тесты для determine_vat_zone."""
from __future__ import annotations

import pytest
from src.core.checkup_questions import (
    VAT_ZONE_APPROACHING,
    VAT_ZONE_BELOW,
    VAT_ZONE_ESTABLISHED,
    VAT_ZONE_FIRST_TIME,
    determine_vat_zone,
)
from src.core.checkup_report import render_vat_section


@pytest.mark.parametrize(
    "answer_text, expected_zone",
    [
        # Цифры через «млн»
        ("Выручка 5 млн рублей за 2025 год, УСН без НДС", VAT_ZONE_BELOW),
        ("Оборот компании около 15 млн ₽ в год", VAT_ZONE_APPROACHING),
        ("Выручка 35 млн за последние 12 месяцев, режим УСН", VAT_ZONE_FIRST_TIME),
        ("ARR 120 млн, EBITDA 18 млн, маржа 15%. Работаем с НДС.", VAT_ZONE_ESTABLISHED),
        # Уже на НДС
        ("Мы на ОСНО, платим НДС 20% уже 3 года, оборот 200 млн", VAT_ZONE_ESTABLISHED),
    ],
)
def test_determine_vat_zone(answer_text: str, expected_zone: str) -> None:
    result = determine_vat_zone(answer_text)
    assert result["zone"] == expected_zone
    assert result["description"]
    assert result["advice"]


def test_vat_zone_returns_required_keys() -> None:
    result = determine_vat_zone("Выручка 25 млн")
    assert set(result.keys()) >= {"zone", "description", "advice"}


def test_render_vat_section_empty_answers() -> None:
    assert render_vat_section([]) == ""


def test_render_vat_section_contains_header() -> None:
    """render_vat_section возвращает HTML с нужным заголовком."""
    from unittest.mock import MagicMock

    answer = MagicMock()
    answer.question_key = "m2_ebitda"
    answer.text = "Выручка 30 млн за год, маржа 20%, УСН"

    html = render_vat_section([answer])
    assert "НДС-флажок 2026" in html
    assert "Ваша зона" in html
