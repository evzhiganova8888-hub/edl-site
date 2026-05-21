"""Score Чекапа v2 (ТЗ §13) — отдельный от Mini Score.

Mini Score = зрелость по self-assessment (12 MC).
Чекап Score = MC + numeric (через бенчмарк) + short-text quality, со stage-весами.

Связь с Mini Score:
- Если есть `user.quiz_score`, в PDF показываем оба + Δ + объяснение.
- Чекап Score обычно ниже Mini Score (планка по цифрам выше) — это норма.
"""
from __future__ import annotations

from typing import Iterable, Literal

from src.core.checkup_benchmarks import lookup_benchmark
from src.core.checkup_questions import (
    CHECKUP_QUESTIONS,
    Layer,
    by_key,
    mc_questions,
    numeric_questions,
    short_text_questions,
)

Stage = Literal["start", "team", "structure", "maturity"]

# Те же веса слоёв, что в Mini-Чекап v2 (core/quiz.py)
STAGE_WEIGHTS: dict[Stage, dict[Layer, float]] = {
    "start":     {"01": 0.35, "02": 0.25, "03": 0.15, "04": 0.25},
    "team":      {"01": 0.30, "02": 0.30, "03": 0.20, "04": 0.20},
    "structure": {"01": 0.25, "02": 0.25, "03": 0.30, "04": 0.20},
    "maturity":  {"01": 0.30, "02": 0.20, "03": 0.30, "04": 0.20},
}


def _numeric_to_score(
    benchmark_key: str | None,
    value: float | None,
    segment: str | None,
    stage: Stage,
    *,
    direction: Literal["higher_better", "lower_better"] = "higher_better",
) -> float:
    """Маппим numeric-ответ в 0..100 относительно бенчмарка.

    higher_better: если value >= mean → 100, value <= mean/2 → 0, линейно между.
    lower_better: используется для hours_per_week (меньше = здоровее, но не <30).
    """
    if value is None or benchmark_key is None:
        return 50.0  # нейтрально

    mean = lookup_benchmark(benchmark_key, segment, stage)
    if mean is None:
        return 50.0

    if direction == "higher_better":
        if value >= mean:
            # Бонус за превышение, но насыщение
            return min(100.0, 70.0 + (value - mean) / mean * 60.0)
        if value <= 0:
            return 0.0
        return max(0.0, value / mean * 70.0)

    # lower_better — для hours_per_week
    if value <= mean:
        return min(100.0, 100.0 - (value / mean) * 30.0)
    # Превышение нормы — штраф
    overshoot = (value - mean) / mean
    return max(0.0, 70.0 - overshoot * 70.0)


def _mc_layer_score(mc_answers: dict[str, int], layer: Layer) -> float:
    """3 MC × 10 max = 30 → 0..100."""
    qs = [q for q in mc_questions() if q.layer == layer]
    if not qs:
        return 0.0
    raw = sum(mc_answers.get(q.key, 0) for q in qs)
    return raw * 100.0 / (10 * len(qs))


def _numeric_layer_score(
    numeric_answers: dict[str, float | None],
    layer: Layer,
    segment: str | None,
    stage: Stage,
) -> float:
    """1 numeric → 0..100 (через бенчмарк)."""
    qs = [q for q in numeric_questions() if q.layer == layer]
    if not qs:
        return 50.0
    q = qs[0]
    val = numeric_answers.get(q.key)
    direction = "lower_better" if q.benchmark_key == "hours_per_week" else "higher_better"
    return _numeric_to_score(q.benchmark_key, val, segment, stage, direction=direction)


def _text_layer_score(text_quality: dict[str, bool], layer: Layer) -> float:
    """1 short-text quality_passed → 100, иначе 50."""
    qs = [q for q in short_text_questions() if q.layer == layer]
    if not qs:
        return 50.0
    q = qs[0]
    return 100.0 if text_quality.get(q.key) else 50.0


def layer_composite(
    layer: Layer,
    mc_answers: dict[str, int],
    numeric_answers: dict[str, float | None],
    text_quality: dict[str, bool],
    segment: str | None,
    stage: Stage,
) -> float:
    """Композит слоя: MC×0.5 + numeric×0.35 + text×0.15."""
    mc = _mc_layer_score(mc_answers, layer)
    num = _numeric_layer_score(numeric_answers, layer, segment, stage)
    txt = _text_layer_score(text_quality, layer)
    return mc * 0.5 + num * 0.35 + txt * 0.15


def total_checkup_score(
    mc_answers: dict[str, int],
    numeric_answers: dict[str, float | None],
    text_quality: dict[str, bool],
    segment: str | None,
    stage: Stage,
) -> tuple[int, dict[Layer, int]]:
    """Возвращает (total_score 0..100, по слоям 0..100)."""
    layer_scores: dict[Layer, float] = {
        L: layer_composite(L, mc_answers, numeric_answers, text_quality, segment, stage)  # type: ignore[arg-type]
        for L in ("01", "02", "03", "04")
    }
    weights = STAGE_WEIGHTS[stage]
    total = sum(layer_scores[L] * weights[L] for L in ("01", "02", "03", "04"))  # type: ignore[index]
    return round(total), {L: round(v) for L, v in layer_scores.items()}


def split_answers(
    answers: Iterable,
) -> tuple[dict[str, int], dict[str, float | None], dict[str, bool]]:
    """Разделяем CheckupAnswer'ы на 3 словаря по типу.

    Args:
        answers: Iterable[CheckupAnswer]
    Returns:
        (mc_answers, numeric_answers, text_quality)
    """
    mc: dict[str, int] = {}
    num: dict[str, float | None] = {}
    txt: dict[str, bool] = {}

    q_by_key = by_key()
    for a in answers:
        q = q_by_key.get(a.question_key)
        if q is None:
            continue
        if q.answer_type == "mc":
            if getattr(a, "answer_score", None) is not None:
                mc[a.question_key] = int(a.answer_score)
        elif q.answer_type == "numeric":
            if getattr(a, "answer_skipped", False):
                num[a.question_key] = None
            elif getattr(a, "answer_numeric", None) is not None:
                num[a.question_key] = float(a.answer_numeric)
            else:
                num[a.question_key] = None
        elif q.answer_type == "short_text":
            txt[a.question_key] = bool(getattr(a, "quality_passed", False))
    return mc, num, txt


def category_label(score: int) -> tuple[str, str]:
    """То же, что в Mini (ТЗ §13.3)."""
    if score <= 40:
        return "Бизнес держится на вас лично", "red"
    if score <= 60:
        return "Есть базовая структура, много пробелов", "orange"
    if score <= 75:
        return "Зрелая инфраструктура, но узкие места видны", "yellow"
    return "Готовая к масштабированию операционная база", "green"
