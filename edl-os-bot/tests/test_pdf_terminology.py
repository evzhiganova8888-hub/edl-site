"""Терминология в PDF — без устаревших ошибок (требование 22.05.2026).

- «Вижнар» — ошибочный термин, везде заменён на «Визионер».
- «Диагностика 25k» — устаревшая цена, актуальная 45 000 ₽.
- Юр.идентификатор «ИП Жиганова Екатерина Викторовна» — оставляем.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")

from src.core.checkup_archetypes import ARCHETYPE_META
from src.core.checkup_pdf_v3 import (
    TEMPLATE_PATH,
    build_fallback_data,
    _ensure_static_blocks,
    render_pdf_html,
)


def test_template_does_not_contain_vijnar():
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    # case-insensitive проверка всех вариантов
    lowered = text.lower()
    for variant in ("вижнар", "vijnar"):
        assert variant not in lowered, f"template still contains {variant!r}"


def test_template_uses_vizioner():
    """Заменили на «Визионер» — проверяем что замена прошла."""
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "ВИЗИОНЕР" in text or "Визионер" in text


def test_fallback_data_uses_vizioner():
    data = build_fallback_data(
        archetype="anna_command",
        plan="plus",
        company_legal_name="ООО Тест",
        report_id="X",
        benchmark_avg=54,
        answers_count=16,
        meta=ARCHETYPE_META["anna_command"],
    )
    _ensure_static_blocks(data, plan="plus")
    # Проверим что в executive_summary fallback'а нет «Вижнар»
    summary_text = " ".join(
        item.get("eyebrow", "") + " " + item.get("title", "")
        for item in data["executive_summary"]
    ).lower()
    assert "вижнар" not in summary_text
    # И в готовом HTML тоже
    html = render_pdf_html(data).lower()
    assert "вижнар" not in html


def test_diagnostika_price_is_45k_not_25k():
    """ТЗ SoT v1.5: Диагностика стоит 45 000 ₽, не 25 000."""
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    # Запрещены устаревшие упоминания
    assert "25k" not in text
    assert "25 000 ₽" not in text  # цена Диагностики не 25
    # Допустимые упоминания 45
    assert "45 000 ₽" in text or "45k" in text or "45 000 ₽" in text


def test_legal_identity_preserved():
    """ИП Жиганова — это юр.идентификатор оператора, должен сохраняться."""
    data = build_fallback_data(
        archetype="anna_command",
        plan="basic",
        company_legal_name="ООО Тест",
        report_id="X",
        benchmark_avg=54,
        answers_count=16,
        meta=ARCHETYPE_META["anna_command"],
    )
    _ensure_static_blocks(data, plan="basic")
    legal_blob = " ".join(data["legal_footer"])
    assert "Жиганова Екатерина Викторовна" in legal_blob
    assert "027507994838" in legal_blob


def test_video_signed_as_team_in_template():
    """Подпись видео-разбора — Команда EDL OS (не Катя/Екатерина персонально)."""
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    # «Катя» / «Катерина» как имя автора не должны встречаться
    assert "Катерина Жиганова · Фаундер" not in text
    assert "Катя пересоберёт" not in text
    # Должна быть атрибуция команды
    assert "Команда EDL OS" in text or "команда EDL OS" in text
