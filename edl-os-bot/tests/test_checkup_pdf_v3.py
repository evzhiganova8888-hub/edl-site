"""PDF v3 — fallback dataset, рендер шаблона, forbidden-words guard.

Без вызовов Claude: проверяем что fallback dataset валиден по Pydantic-схеме
и что Jinja2-рендер не падает. WeasyPrint не вызываем — он тяжёлый и
требует системных Pango/HarfBuzz.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.checkup_archetypes import ARCHETYPE_META
from src.core.checkup_pdf_v3 import (
    CheckupDataSchema,
    TEMPLATE_PATH,
    _ensure_static_blocks,
    build_fallback_data,
    check_forbidden_words,
    render_pdf_html,
)


def _build_for(plan: str, archetype: str = "anna_command") -> dict:
    meta = ARCHETYPE_META[archetype]  # type: ignore[index]
    data = build_fallback_data(
        archetype=archetype,  # type: ignore[arg-type]
        plan=plan,
        company_legal_name="ООО «Тестовая Школа»",
        report_id="EDL-CHK-2026-0521-0001",
        benchmark_avg=54,
        answers_count=16,
        meta=meta,
    )
    _ensure_static_blocks(data, plan=plan)
    return data


def test_template_file_exists():
    assert TEMPLATE_PATH.exists()
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    # Ключевые признаки — это шаблон Екатерины (1509+ строк)
    assert "edl_chekap_template" in text or "EDL OS · ЧЕКАП" in text
    assert "{{ company.legal_name }}" in text


# ── Fallback dataset ─────────────────────────────────────────────────────────


def test_fallback_basic_validates():
    data = _build_for("basic")
    CheckupDataSchema(**data)


def test_fallback_plus_validates():
    data = _build_for("plus")
    CheckupDataSchema(**data)


def test_basic_has_5_recommendations():
    data = _build_for("basic")
    assert len(data["recommendations"]) == 5


def test_plus_has_7_recommendations():
    data = _build_for("plus")
    assert len(data["recommendations"]) == 7


def test_basic_has_no_plus_blocks():
    data = _build_for("basic")
    # Plus-only блоки могут отсутствовать
    assert data.get("personal_comment") is None
    assert data.get("deep_dive_layer") is None


def test_plus_has_alternatives_three_paths():
    """ТЗ §6.5 — Plus стр. 11 обязательно 3 пути."""
    data = _build_for("plus")
    alts = data["deep_dive_connection"]["alternatives"]
    assert "path_1_own" in alts
    assert "path_2_hiring" in alts
    assert "path_3_agents" in alts
    for key in ("path_1_own", "path_2_hiring", "path_3_agents"):
        path = alts[key]
        for field in ("name", "what_to_do", "founder_time_hours", "cost_rub", "time_to_result"):
            assert field in path, f"{key} missing {field}"


def test_plus_personal_comment_signed_by_team():
    """Решение 21.05.2026: подпись «Команда EDL OS», не лично Екатерина."""
    data = _build_for("plus")
    assert data["personal_comment"]["signature_name"] == "Команда EDL OS"


def test_layers_in_correct_order():
    data = _build_for("basic")
    keys = [l["key"] for l in data["layers"]]
    assert keys == ["strategy", "funnel", "operations", "money"]


def test_executive_summary_has_layer_impact():
    """ТЗ §6.3 — каждая карточка содержит layer_impact."""
    data = _build_for("basic")
    for item in data["executive_summary"]:
        assert item.get("layer_impact"), "missing layer_impact"
        assert "слой" in item["layer_impact"].lower()


# ── Static blocks (guarantee + legal_footer + next_step) ─────────────────────


def test_guarantee_block_has_both_conditions():
    """Условная гарантия с двумя условиями (требование 21.05.2026)."""
    data = _build_for("basic")
    g = data["guarantee"]
    conds_text = " ".join(g["conditions"]).lower()
    assert "рубрик" in conds_text
    assert "рекоменда" in conds_text
    assert "оба" in conds_text or "обоих" in conds_text


def test_legal_footer_has_5_items():
    data = _build_for("basic")
    assert len(data["legal_footer"]) == 5
    # Каждый пункт начинается с цифры
    for i, item in enumerate(data["legal_footer"], 1):
        assert item.startswith(f"{i}."), f"item {i} doesn't start with '{i}.'"


def test_next_step_coupon_only_in_plus():
    basic = _build_for("basic")
    plus = _build_for("plus")
    assert "coupon_price" not in basic["next_step"]
    assert plus["next_step"]["coupon_price"] == "36 000 ₽"
    # Полная цена одинаковая
    assert basic["next_step"]["ticket_price"] == "45 000 ₽"
    assert plus["next_step"]["ticket_price"] == "45 000 ₽"


# ── Render Jinja2 (без WeasyPrint) ───────────────────────────────────────────


def test_render_basic_does_not_throw():
    data = _build_for("basic")
    html = render_pdf_html(data)
    # Базовый sanity: шаблон не пустой, содержит юр.название
    assert "ООО «Тестовая Школа»" in html
    assert "СТРАТЕГИЯ" in html
    assert "ВОРОНКА" in html


def test_render_plus_includes_deep_dive_and_personal():
    data = _build_for("plus")
    html = render_pdf_html(data)
    assert "Команда EDL OS" in html
    assert "СВОИМИ СИЛАМИ" in html  # 3 пути
    assert "НАЁМ СПЕЦИАЛИСТА" in html
    assert "СПРИНТЕ" in html


def test_rendered_html_has_no_forbidden_words():
    """Финальный qa-guard: PDF не содержит запрещённых маркетинговых слов."""
    for plan in ("basic", "plus"):
        data = _build_for(plan)
        html = render_pdf_html(data)
        violations = check_forbidden_words(html)
        assert not violations, f"{plan} PDF has forbidden words: {violations}"


def test_rendered_basic_does_not_include_plus_only_sections():
    data = _build_for("basic")
    html = render_pdf_html(data)
    # Plus-only маркеры
    assert "PLUS · РАСШИРЕННЫЙ ДИАГНОЗ" not in html
    assert "PLUS · ВИДЕОРАЗБОР" not in html


# ── Forbidden-words guard на сырых данных ────────────────────────────────────


def test_check_forbidden_words_detects_okupaetsya():
    fake = "<html>Этот разрыв окупается за 6 недель</html>"
    assert "окупается" in check_forbidden_words(fake)


def test_check_forbidden_words_empty_on_clean_html():
    clean = "<html>Симптом, который скоро станет диагнозом. Это закладывает потолок роста.</html>"
    assert check_forbidden_words(clean) == []
