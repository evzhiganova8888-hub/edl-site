"""Чекап v2 Score: формула MC×0.5 + numeric×0.35 + text×0.15 со stage-весами (TZ §13)."""
import pytest

from src.core.checkup_benchmarks import lookup_benchmark
from src.core.checkup_questions import mc_questions, numeric_questions, short_text_questions
from src.core.checkup_score import (
    STAGE_WEIGHTS,
    category_label,
    layer_composite,
    total_checkup_score,
)


def test_stage_weights_sum_to_one():
    for stage, weights in STAGE_WEIGHTS.items():
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-9, f"Stage {stage}: sum={total}"


def test_zero_answers_score():
    mc = {q.key: 0 for q in mc_questions()}
    num = {q.key: 0.0 for q in numeric_questions()}
    txt = {q.key: False for q in short_text_questions()}
    score, layers = total_checkup_score(mc, num, txt, "edu", "team")
    # Минимальный score — не 0, потому что short_text=False даёт floor 50
    # и lower_better numeric (hours_per_week) с value=0 даёт высокий score
    assert 0 < score < 30


def test_perfect_answers_score():
    mc = {q.key: 10 for q in mc_questions()}
    # numeric: значения близкие к бенчмарку (для SaaS Maturity)
    num = {
        q.key: lookup_benchmark(q.benchmark_key, "saas", "maturity")
        for q in numeric_questions()
    }
    txt = {q.key: True for q in short_text_questions()}
    score, layers = total_checkup_score(mc, num, txt, "saas", "maturity")
    # Maximum для perfect = ~95+
    assert score >= 80, f"Perfect should be >= 80, got {score}"


def test_stage_relative_scoring():
    """При одинаковых ответах stage влияет только при разных layer scores.

    Если все слои равны (один и тот же composite), result одинаков из-за sum(w)=1.
    Тут проверяем что разные стадии действительно дают разные scores для
    несбалансированных слоёв.
    """
    mc = {q.key: 10 if q.layer == "03" else 0 for q in mc_questions()}
    num = {q.key: None for q in numeric_questions()}
    txt = {q.key: False for q in short_text_questions()}

    score_start, _ = total_checkup_score(mc, num, txt, "edu", "start")
    score_structure, _ = total_checkup_score(mc, num, txt, "edu", "structure")

    # На стадии Structure вес операционки 0.30 vs 0.15 на Start —
    # та же сильная операционка даёт больший Score на Structure.
    assert score_structure > score_start, (
        f"Strong ops should score higher on structure ({score_structure}) than on start ({score_start})"
    )


def test_skipped_numeric_neutral():
    mc = {q.key: 5 for q in mc_questions()}
    num_with = {q.key: lookup_benchmark(q.benchmark_key, "edu", "team") for q in numeric_questions()}
    num_skipped = {q.key: None for q in numeric_questions()}
    txt = {q.key: True for q in short_text_questions()}
    s_with, _ = total_checkup_score(mc, num_with, txt, "edu", "team")
    s_skipped, _ = total_checkup_score(mc, num_skipped, txt, "edu", "team")
    # skipped numeric → нейтральные 50, чем-то ниже отвечающего на бенчмарк
    assert s_skipped <= s_with


def test_category_label_aligns_with_mini():
    """Те же диапазоны, что в Mini-Чекап."""
    assert category_label(0)[1] == "red"
    assert category_label(40)[1] == "red"
    assert category_label(41)[1] == "orange"
    assert category_label(60)[1] == "orange"
    assert category_label(61)[1] == "yellow"
    assert category_label(75)[1] == "yellow"
    assert category_label(76)[1] == "green"
    assert category_label(100)[1] == "green"


def test_layer_composite_weights():
    """MC×0.5 + numeric×0.35 + text×0.15 — это формула композита одного слоя."""
    # MC=10 (= 100), numeric точно на бенчмарке (= 70), text passed (=100)
    mc = {q.key: 10 for q in mc_questions() if q.layer == "01"}
    num = {q.key: lookup_benchmark(q.benchmark_key, "edu", "team") for q in numeric_questions() if q.layer == "01"}
    txt = {q.key: True for q in short_text_questions() if q.layer == "01"}
    score = layer_composite("01", mc, num, txt, "edu", "team")
    # Expected: 100*0.5 + 70*0.35 + 100*0.15 = 50 + 24.5 + 15 = 89.5
    assert 85 <= score <= 95
