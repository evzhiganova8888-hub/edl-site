"""Бенчмарки Founder OS Score по сегменту × стадии (SoT §1.6).

Сейчас — захардкоженные приближённые значения.
После 100+ клиентов заменить на чтение из таблицы benchmark_segment_stage.
"""
from __future__ import annotations

from src.core.quiz import Stage

# segment: {stage: mean_score}
BENCHMARK: dict[str, dict[Stage, int]] = {
    "edu":  {"start": 48, "team": 54, "structure": 62, "maturity": 71},
    "mp":   {"start": 45, "team": 58, "structure": 65, "maturity": 72},
    "it":   {"start": 52, "team": 56, "structure": 60, "maturity": 68},
    "prod": {"start": 42, "team": 50, "structure": 58, "maturity": 70},
    "serv": {"start": 46, "team": 52, "structure": 58, "maturity": 66},
    "saas": {"start": 50, "team": 58, "structure": 64, "maturity": 73},
}

# Медиана по всем сегментам (для fallback при segment='other')
_ALL_STAGES_MEDIAN: dict[Stage, int] = {
    "start":     47,
    "team":      55,
    "structure": 61,
    "maturity":  70,
}


def benchmark_for(
    segment: str,
    stage: Stage,
    user_score: int,
) -> tuple[int | None, int | None]:
    """Возвращает (mean, delta) для пары сегмент × стадия.

    delta = user_score − mean (положительный → выше среднего).
    Если сегмент «other» или нет данных — возвращает медиану по всем
    сегментам для этой стадии.
    """
    seg_data = BENCHMARK.get(segment)
    if seg_data:
        mean = seg_data.get(stage)
        if mean is not None:
            return mean, user_score - mean

    # fallback — общая медиана по стадии
    mean = _ALL_STAGES_MEDIAN.get(stage)
    if mean is not None:
        return mean, user_score - mean

    return None, None
