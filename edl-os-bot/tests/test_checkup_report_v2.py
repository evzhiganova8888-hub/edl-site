"""PDF v2 (rule-based) — генератор контекста и Jinja2 рендеринг.

Тестируем pure-функции напрямую + полный render_report_v2 на мок-объектах.
WeasyPrint не вызываем (требует системные либы) — только HTML.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.core import checkup_report_v2 as v2


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _answer(question_key: str, layer: str, text: str, quality_passed: bool = True):
    return SimpleNamespace(
        question_key=question_key,
        layer=layer,
        text=text,
        word_count=len(text.split()),
        quality_passed=quality_passed,
    )


# ─── detect_team_size ─────────────────────────────────────────────────────────


def test_detect_team_size_from_horizon():
    answers = [_answer(
        "s1_horizon", "strategy",
        "Через 3 года SaaS, команда 18 человек, ARR 80M ₽.",
    )]
    assert v2.detect_team_size(answers) == 18


def test_detect_team_size_none_if_absent():
    answers = [_answer("s1_horizon", "strategy", "Без цифр про команду.")]
    assert v2.detect_team_size(answers) is None


# ─── role_for_layer ───────────────────────────────────────────────────────────


def test_role_small_team_is_owner():
    assert "Собственник" in v2.role_for_layer("strategy", team_size=4)


def test_role_large_team_is_clevel():
    assert v2.role_for_layer("operations", team_size=40) == "COO"
    assert v2.role_for_layer("finance", team_size=40) == "CFO"


def test_role_mid_team():
    role = v2.role_for_layer("sales", team_size=15)
    assert "Sales" in role or "продаж" in role.lower()


def test_role_unknown_team_size_fallback():
    role = v2.role_for_layer("finance", team_size=None)
    assert "CFO" in role or "финдир" in role.lower()


# ─── detect_tools ─────────────────────────────────────────────────────────────


def test_detect_tools_picks_known_keywords():
    answers = [
        _answer("f1_funnel_home", "sales",
                "Используем amoCRM, ведём лиды через Apollo + LinkedIn"),
        _answer("o4_decisions", "operations", "Все встречи в Notion"),
    ]
    tools = v2.detect_tools(answers)
    assert "amoCRM" in tools["sales"]
    assert "Apollo" in tools["sales"]
    assert "Notion" in tools["operations"]


def test_detect_tools_empty_when_none_named():
    answers = [_answer("f1_funnel_home", "sales", "Всё в голове и таблицах")]
    tools = v2.detect_tools(answers)
    assert tools["sales"] == []


def test_detect_tools_dedupes_globally():
    """Если Notion упомянут в двух слоях — берём первое упоминание."""
    answers = [
        _answer("f1_funnel_home", "sales", "Notion для лидов"),
        _answer("o4_decisions", "operations", "В Notion фиксируем решения"),
    ]
    tools = v2.detect_tools(answers)
    all_mentioned = v2.all_tools(tools)
    assert all_mentioned.count("Notion") == 1


# ─── select_recommendations ───────────────────────────────────────────────────


def test_base_returns_5():
    recs = v2.select_recommendations(
        plan="base", answers=[], tools_by_layer={}, team_size=10
    )
    assert len(recs) == 5


def test_plus_returns_7():
    recs = v2.select_recommendations(
        plan="plus", answers=[], tools_by_layer={}, team_size=10
    )
    assert len(recs) == 7


def test_recommendations_have_required_fields():
    recs = v2.select_recommendations(
        plan="plus", answers=[], tools_by_layer={"sales": ["amoCRM"]},
        team_size=12,
    )
    required = {"title", "layer", "layer_label", "what", "tool", "role",
                "first_step", "impact"}
    for r in recs:
        assert required.issubset(r.keys()), f"Missing fields in {r}"
        assert r["tool"], f"Empty tool in {r['title']}"
        assert r["role"], f"Empty role in {r['title']}"


def test_recommendations_use_client_tools_when_available():
    """Если клиент назвал amoCRM — рекомендация про CRM использует его."""
    recs = v2.select_recommendations(
        plan="plus",
        answers=[],
        tools_by_layer={"sales": ["amoCRM"]},
        team_size=10,
    )
    sales_recs = [r for r in recs if r["layer"] == "sales"]
    # Хотя бы одна sales-рекомендация упоминает amoCRM
    assert any("amoCRM" in r["tool"] for r in sales_recs)


# ─── build_scenarios ──────────────────────────────────────────────────────────


def test_scenarios_use_priority_metrics():
    recs = v2.select_recommendations(
        plan="plus", answers=[], tools_by_layer={}, team_size=10
    )
    scenarios = v2.build_scenarios(
        priority_metrics=["выручка", "маржа", "retention"],
        recommendations=recs,
    )
    assert scenarios["sniper"]["metric"] == "выручка"
    assert scenarios["combo"]["metrics"] == ["выручка", "маржа"]
    assert scenarios["full_stack"]["metrics"] == ["выручка", "маржа", "retention"]


def test_scenarios_combo_has_3_actions():
    recs = v2.select_recommendations(
        plan="plus", answers=[], tools_by_layer={}, team_size=10
    )
    scenarios = v2.build_scenarios(["m1", "m2", "m3"], recs)
    assert len(scenarios["combo"]["actions"]) == 3


def test_full_stack_has_8_actions_min_and_4_layers():
    recs = v2.select_recommendations(
        plan="plus", answers=[], tools_by_layer={}, team_size=10
    )
    scenarios = v2.build_scenarios(["m1", "m2", "m3"], recs)
    assert scenarios["full_stack"]["total_actions"] >= 8
    actions_by_layer = scenarios["full_stack"]["actions_by_layer"]
    # Каждый из 4 слоёв упомянут (label из _LAYER_LABELS)
    assert "Стратегия" in actions_by_layer
    assert "Воронка" in actions_by_layer
    assert "Операционка" in actions_by_layer
    assert "Деньги" in actions_by_layer
    # На каждый слой ≥ 1 действия
    for layer, actions in actions_by_layer.items():
        assert len(actions) >= 1, f"Empty layer {layer}"


def test_scenarios_default_metrics_if_none():
    recs = v2.select_recommendations(
        plan="base", answers=[], tools_by_layer={}, team_size=None
    )
    scenarios = v2.build_scenarios(priority_metrics=[], recommendations=recs)
    # Не падает, использует fallback метрики
    assert scenarios["sniper"]["metric"]
    assert len(scenarios["full_stack"]["metrics"]) == 3


# ─── diagnose_layer ───────────────────────────────────────────────────────────


def test_diagnose_includes_all_three_fields():
    diag = v2.diagnose_layer("strategy", [])
    assert "strong" in diag
    assert "gap" in diag
    assert "risk_90d" in diag
    assert diag["label"] == "Стратегия"


def test_diagnose_detects_strong_when_marker_in_passed_answer():
    answers = [_answer(
        "s2_bets", "strategy",
        "Три главные ставки этого года: 1) Enterprise 2) США 3) Vertical AI.",
        quality_passed=True,
    )]
    diag = v2.diagnose_layer("strategy", answers)
    # «ставк» — strong_marker для strategy → strong-формулировка
    assert "умеете называть конкретные ставки" in diag["strong"] or "основа" in diag["strong"]


# ─── render_report_v2 (full integration) ──────────────────────────────────────


def _fake_app(plan="plus", priority_metrics=None, is_self_demo=False):
    return SimpleNamespace(
        id=uuid4(),
        type="audit",
        status="paid",
        checkup_started_at=datetime.now(timezone.utc),
        checkup_completed_at=datetime.now(timezone.utc),
        payload={
            "plan": plan,
            "priority_metrics": priority_metrics or ["выручка", "маржа", "retention"],
            "is_self_demo": is_self_demo,
        },
    )


def _fake_user(company="ВитаКонсалт"):
    return SimpleNamespace(
        id=1,
        telegram_id=105255440,
        telegram_username="testuser",
        first_name="Лина",
        last_name="Миронович",
        email="test@example.com",
        company_name=company,
    )


def _full_answers():
    return [
        _answer("s1_horizon", "strategy",
                "Через 3 года SaaS, команда 15 человек, ARR 80M ₽.",
                quality_passed=True),
        _answer("s2_bets", "strategy",
                "Три ставки: Enterprise, США, Vertical AI."),
        _answer("s3_not_doing", "strategy", "Не идём в B2C."),
        _answer("s4_antipatterns", "strategy", "Кастомка для одного клиента."),
        _answer("s5_last_90_days", "strategy", "Сдвинули Enterprise релиз."),
        _answer("f1_funnel_home", "sales",
                "amoCRM, owner — Маша. Pipeline-обзор в понедельник."),
        _answer("f2_stage_conversion", "sales", "лиды 800 → демо 120 → 18 договоров."),
        _answer("f3_acv_cycle_cac", "sales", "AOV 280к, цикл 32 дня, CAC 45к."),
        _answer("f4_sources_cost", "sales", "Outbound 40%, inbound 25%, партнёрки 20%."),
        _answer("f5_bottleneck", "sales", "Демо→договор для Enterprise 8% vs SMB 18%."),
        _answer("o1_load", "operations", "Tech-lead 168ч, CEO 200ч."),
        _answer("o2_project_margin", "operations", "Клиент A: 60%, B: 35%, C: 60%."),
        _answer("o3_bottleneck", "operations", "Onboarding на CEO 8ч/клиента."),
        _answer("o4_decisions", "operations",
                "Notion + еженедельный sync понедельник 10:00."),
        _answer("o5_next_90_days", "operations", "Снять CEO с onboarding."),
        _answer("m1_cashflow", "finance", "Cash 4.8М, прогноз 3.9М через 90 дней."),
        _answer("m2_ebitda", "finance",
                "Выручка 78 млн, EBITDA 13.3M, маржа 17%."),
        _answer("m3_vat_2026", "finance", "УСН с НДС 5% выбрали."),
        _answer("m4_reserves", "finance", "Резерв 6М на счёте."),
        _answer("m5_decisions_90", "finance", "Цены +15%, минусовый продукт закрыть."),
    ]


def test_render_report_v2_plus_full():
    html = v2.render_report_v2(
        application=_fake_app(plan="plus"),
        user=_fake_user(),
        answers=_full_answers(),
    )
    # Cover есть
    assert "ВитаКонсалт" in html
    assert "Лина" in html
    # Все 4 слоя в диагнозе
    assert "Стратегия" in html
    assert "Воронка" in html
    assert "Операционка" in html
    assert "Деньги" in html
    # Plus-специфика
    assert "методологические гипотезы" in html
    # Upsell-страница (TZ_checkup_plus_v2.md §8.4 — Диагностика 45 000 ₽)
    assert "Диагност" in html
    assert "45 000" in html
    # 3 сценария
    assert "Sniper" in html
    assert "Combo" in html
    assert "Full Stack" in html
    # Priority metrics
    assert "выручка" in html
    # НДС
    assert "НДС" in html
    # Watermark «ЧЕРНОВИК» снят
    assert "ЧЕРНОВИК" not in html
    # Footer с версией
    assert "v1" in html
    assert "@edl_os_bot" in html


def test_render_report_v2_base_no_disclaimer():
    """Disclaimer о Plus — только для Plus."""
    html = v2.render_report_v2(
        application=_fake_app(plan="base"),
        user=_fake_user(),
        answers=_full_answers(),
    )
    # «методологические гипотезы» — в disclaimer Plus
    assert "методологические гипотезы" not in html
    # Но upsell на Диагностику есть и в Base
    assert "Диагност" in html


def test_render_report_v2_self_demo_marker():
    html = v2.render_report_v2(
        application=_fake_app(plan="plus", is_self_demo=True),
        user=_fake_user(),
        answers=_full_answers(),
    )
    assert "self-demo" in html


def test_render_report_v2_uses_client_tools_in_recs():
    """Если клиент назвал amoCRM в воронке — это попадает в карточки."""
    answers = _full_answers()
    html = v2.render_report_v2(
        application=_fake_app(plan="plus"),
        user=_fake_user(),
        answers=answers,
    )
    # amoCRM упомянут в ответе f1_funnel_home, должен попасть в рекомендации
    assert "amoCRM" in html


def test_render_report_v2_no_priority_metrics():
    """Без priority_metrics — категориальные сценарии, не падает."""
    app = _fake_app(plan="plus")
    app.payload["priority_metrics"] = []
    html = v2.render_report_v2(
        application=app,
        user=_fake_user(),
        answers=_full_answers(),
    )
    assert "категориальные сценарии" in html or "ключевая метрика" in html


def test_render_report_v2_empty_answers_doesnt_crash():
    html = v2.render_report_v2(
        application=_fake_app(plan="base"),
        user=_fake_user(),
        answers=[],
    )
    # Хоть пусто — но cover и upsell должны быть
    assert "ВитаКонсалт" in html
