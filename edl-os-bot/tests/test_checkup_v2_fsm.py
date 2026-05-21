"""Чекап v2: skip-логика и FSM helpers."""
from __future__ import annotations

import pytest

from src.bot.handlers.checkup import (
    _MAX_IMPROVE_TRIES,
    _STATE_AWAIT_ANSWER,
    _STATE_AWAIT_P1,
    _STATE_AWAIT_P2,
    is_in_checkup_fsm,
)
from src.core.checkup_questions import LEGACY_V1_KEYS


# ── is_in_checkup_fsm ─────────────────────────────────────────────────────────


def test_is_in_checkup_fsm_v2_true():
    user_data = {"checkup_v2_state": "await_answer", "checkup_v2_app_id": "abc-uuid"}
    assert is_in_checkup_fsm(user_data) is True


def test_is_in_checkup_fsm_v1_compat_true():
    """Старые v1 FSM keys тоже распознаются (на случай миграции in-flight)."""
    user_data = {"checkup_state": "await_answer", "checkup_app_id": "abc-uuid"}
    assert is_in_checkup_fsm(user_data) is True


def test_is_in_checkup_fsm_false_empty():
    assert is_in_checkup_fsm({}) is False


def test_is_in_checkup_fsm_false_partial_v2():
    """Только state без app_id → не в FSM."""
    assert is_in_checkup_fsm({"checkup_v2_state": "await_answer"}) is False


def test_is_in_checkup_fsm_false_partial_v1():
    assert is_in_checkup_fsm({"checkup_app_id": "abc"}) is False


# ── Legacy keys ──────────────────────────────────────────────────────────────


def test_legacy_v1_keys_present():
    """Известные v1-ключи — для force-restart detection."""
    expected = {
        "s1_horizon", "s2_bets", "s3_not_doing", "s4_antipatterns", "s5_last_90_days",
        "f1_funnel_home", "f2_stage_conversion", "f3_acv_cycle_cac", "f4_sources_cost", "f5_bottleneck",
        "o1_load", "o2_project_margin", "o3_bottleneck", "o4_decisions", "o5_next_90_days",
        "m1_cashflow", "m2_ebitda", "m3_vat_2026", "m4_reserves", "m5_decisions_90",
    }
    assert LEGACY_V1_KEYS == expected


def test_legacy_keys_disjoint_from_v2():
    """Legacy ключи не пересекаются с v2 ключами c1..c20."""
    from src.core.checkup_questions import CHECKUP_QUESTIONS
    v2_keys = {q.key for q in CHECKUP_QUESTIONS}
    assert LEGACY_V1_KEYS & v2_keys == set()


# ── FSM state constants ──────────────────────────────────────────────────────


def test_max_improve_tries_is_2():
    """ТЗ §7.3 — дожим до 2 раз."""
    assert _MAX_IMPROVE_TRIES == 2


def test_fsm_state_constants():
    """Все ключевые состояния FSM существуют (используются в callback handlers)."""
    assert _STATE_AWAIT_P1
    assert _STATE_AWAIT_P2
    assert _STATE_AWAIT_ANSWER
