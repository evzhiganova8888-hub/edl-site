"""16 SPIN-вопросов Чекапа Plus v2.0 — структура и маркеры (ТЗ §3.3, §3.6)."""
from __future__ import annotations

import pytest

from src.core.checkup_spin_questions import (
    LAYER_LABELS,
    LAYER_SUBTITLES,
    LAYER_NUMBERS,
    SPIN_BY_ID,
    SPIN_QUESTIONS,
    get_question,
    get_question_by_index,
    is_decline_answer,
    questions_for_layer,
    total_questions,
)


def test_exactly_16_questions():
    """ТЗ §3.1: 16 SPIN-вопросов = 4 слоя × 4."""
    assert total_questions() == 16
    assert len(SPIN_QUESTIONS) == 16


def test_four_per_layer():
    for layer in ("strategy", "funnel", "operations", "money"):
        qs = questions_for_layer(layer)  # type: ignore[arg-type]
        assert len(qs) == 4, f"{layer} has {len(qs)} questions, expected 4"


def test_unique_ids():
    ids = [q.id for q in SPIN_QUESTIONS]
    assert len(ids) == len(set(ids))


def test_id_format_QX_Y():
    import re
    for q in SPIN_QUESTIONS:
        assert re.fullmatch(r"Q[1-4]\.[1-4]", q.id), f"bad id {q.id}"


def test_ids_match_layer_and_order():
    """Q1.1 — strategy/1, Q2.3 — funnel/3, etc."""
    layer_to_digit = {"strategy": "1", "funnel": "2", "operations": "3", "money": "4"}
    for q in SPIN_QUESTIONS:
        expected_layer_digit = layer_to_digit[q.layer]
        expected_id = f"Q{expected_layer_digit}.{q.order_in_layer}"
        assert q.id == expected_id


def test_global_number_1_to_16():
    numbers = sorted(q.number for q in SPIN_QUESTIONS)
    assert numbers == list(range(1, 17))


def test_each_question_has_situation_and_problem():
    for q in SPIN_QUESTIONS:
        assert q.situation, f"{q.id} missing situation"
        assert q.problem, f"{q.id} missing problem"
        # Situation — короткий контекст 1-2 предложения
        assert len(q.situation) > 30
        # Problem — конкретный запрос: либо «?», либо императивный глагол
        # «Назовите/Опишите/Расскажите/Сколько/Какой/Какая…».
        assert "?" in q.problem or q.problem.split()[0].lower() in {
            "назовите", "опишите", "расскажите", "какой", "какая", "сколько",
            "какие", "перечислите", "приведите", "главное", "кому",
        }, f"{q.id} problem doesn't look like a request"


def test_layer_labels_complete():
    for layer in ("strategy", "funnel", "operations", "money"):
        assert layer in LAYER_LABELS
        assert layer in LAYER_SUBTITLES
        assert layer in LAYER_NUMBERS


def test_layer_numbers_01_to_04():
    assert LAYER_NUMBERS["strategy"] == "01"
    assert LAYER_NUMBERS["funnel"] == "02"
    assert LAYER_NUMBERS["operations"] == "03"
    assert LAYER_NUMBERS["money"] == "04"


# ── Lookups ──────────────────────────────────────────────────────────────────


def test_lookup_by_id():
    q = get_question("Q1.1")
    assert q is not None
    assert q.layer == "strategy"
    assert q.order_in_layer == 1


def test_lookup_by_id_unknown():
    assert get_question("Q9.9") is None


def test_lookup_by_index():
    first = get_question_by_index(0)
    assert first is not None
    assert first.id == "Q1.1"
    last = get_question_by_index(15)
    assert last is not None
    assert last.id == "Q4.4"
    assert get_question_by_index(16) is None
    assert get_question_by_index(-1) is None


def test_spin_by_id_dict_has_all_questions():
    assert len(SPIN_BY_ID) == 16
    for q in SPIN_QUESTIONS:
        assert SPIN_BY_ID[q.id] is q


# ── Q4.4 — НДС блок (ТЗ §3.3 §4) ─────────────────────────────────────────────


def test_q44_mentions_vat_2026():
    q44 = SPIN_BY_ID["Q4.4"]
    text = (q44.situation + " " + q44.problem).lower()
    assert "ндс" in text
    assert "2026" in text or "425-фз" in text


# ── Decline markers (ТЗ §3.6) ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "answer,expected_marker",
    [
        ("не знаю", "не знаю"),
        ("Не знаю", "не знаю"),
        ("  не знаю ответа  ", "не знаю"),
        ("не считаем", "не считаем"),
        ("не отслеживаем", "не отслеживаем"),
        ("не релевантно нашему бизнесу", "не релевантно"),
        ("не хочу раскрывать", "не хочу раскрывать"),
    ],
)
def test_decline_markers_recognized(answer, expected_marker):
    is_decline, marker = is_decline_answer(answer)
    assert is_decline is True
    assert marker == expected_marker


def test_long_answers_not_treated_as_decline():
    """Длинный ответ — даже если начинается с маркера — не decline."""
    long = "не знаю точно, но могу прикинуть: цикл сделки примерно 31 день, " \
        "конверсия около 22%, CAC 8400 ₽. По P&L закрываемся к 17 числу."
    is_decline, _ = is_decline_answer(long)
    assert is_decline is False


def test_substantive_answer_not_decline():
    is_decline, _ = is_decline_answer("31 день средний цикл сделки")
    assert is_decline is False
