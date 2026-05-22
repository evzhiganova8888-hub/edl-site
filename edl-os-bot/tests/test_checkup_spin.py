"""SPIN-Чекап FSM — smoke-тесты на чистые функции.

Полные интеграционные тесты с DB/TG моками — следующая сессия. Здесь
проверяем:
- тексты-вставки берут правильные meta из архетипа;
- progress-bar формулы;
- state-keys не мутируют между версиями (важно для CLAUDE.md контракта).
"""
from __future__ import annotations

import pytest

from src.bot.handlers import checkup_spin
from src.bot.handlers.checkup_spin import (
    KEY_SPIN_APP_ID,
    KEY_SPIN_Q_IDX,
    KEY_SPIN_STATE,
    STATE_AWAIT_ANSWER,
    STATE_AWAIT_START,
    _INSERT_TEXTS,
    _generate_report_id,
    _plan_of,
)
from src.core.checkup_archetypes import ARCHETYPE_META


def test_fsm_keys_are_stable():
    """Контракт state keys — если меняем, нужно мигрировать context.user_data
    у всех активных пользователей. Поэтому жёстко фиксируем имена."""
    assert KEY_SPIN_APP_ID == "spin_app_id"
    assert KEY_SPIN_Q_IDX == "spin_q_idx"
    assert KEY_SPIN_STATE == "spin_state"


def test_states_named_consistently():
    assert STATE_AWAIT_START == "await_start"
    assert STATE_AWAIT_ANSWER == "await_answer"


# ── _INSERT_TEXTS ────────────────────────────────────────────────────────────


def test_three_insert_texts_at_correct_indices():
    """ТЗ §3.4: 3 вставки между блоками после Q1.4 (idx 4), Q2.4 (8), Q3.4 (12)."""
    assert set(_INSERT_TEXTS.keys()) == {4, 8, 12}


@pytest.mark.parametrize(
    "archetype",
    ["anna_command", "anna_structure", "dmitri_structure", "artem_command"],
)
def test_inserts_render_with_archetype_meta(archetype):
    """Каждая вставка должна без ошибок собрать текст для любого архетипа."""
    meta = ARCHETYPE_META[archetype]
    for idx, fn in _INSERT_TEXTS.items():
        text = fn(archetype, meta)
        assert text
        assert len(text) > 100  # не пустая заглушка
        # genitive сегмента должен встретиться в тексте
        assert meta["segment_label_genitive"] in text


def test_inserts_do_not_contain_personal_attribution():
    """Решение 21.05.2026 — никакой персонификации в Plus-вставках."""
    forbidden = ["Катя", "Катерин", "от Екатерины", "Екатерин"]
    for archetype, meta in ARCHETYPE_META.items():
        for fn in _INSERT_TEXTS.values():
            text = fn(archetype, meta)
            for f in forbidden:
                assert f not in text, (
                    f"insert for {archetype} mentions {f!r}: {text[:200]}"
                )


# ── _plan_of ─────────────────────────────────────────────────────────────────


def test_plan_of_none_returns_basic():
    assert _plan_of(None) == "basic"


def test_plan_of_no_payload_returns_basic():
    class FakeApp:
        payload = None
    assert _plan_of(FakeApp()) == "basic"


def test_plan_of_plus_payload():
    class FakeApp:
        payload = {"plan": "plus"}
    assert _plan_of(FakeApp()) == "plus"


def test_plan_of_base_payload():
    class FakeApp:
        payload = {"plan": "base"}
    assert _plan_of(FakeApp()) == "basic"


# ── _generate_report_id ──────────────────────────────────────────────────────


def test_report_id_uses_inv_id_if_present():
    from datetime import datetime, timezone
    class FakeApp:
        inv_id = 42
    rid = _generate_report_id(FakeApp())
    year = datetime.now(timezone.utc).year
    assert rid == f"EDL-CHK-{year}-0042"


def test_report_id_falls_back_to_random_hex_when_no_inv_id():
    class FakeApp:
        pass  # no inv_id attr
    rid = _generate_report_id(FakeApp())
    parts = rid.split("-")
    assert parts[0] == "EDL"
    assert parts[1] == "CHK"
    assert len(parts[3]) == 4  # 4 hex символа


# ── Импорты не падают ────────────────────────────────────────────────────────


def test_module_exports_expected_api():
    """Контракт публичного API для wire-up в bot.handlers.__init__."""
    assert hasattr(checkup_spin, "start_spin_checkup")
    assert hasattr(checkup_spin, "handle_spin_callback")
    assert hasattr(checkup_spin, "handle_spin_text")
