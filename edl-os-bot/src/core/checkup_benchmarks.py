"""Бенчмарки numeric-метрик Чекапа по сегменту × стадии (ТЗ §11.3 + §4.2).

Для каждого numeric-вопроса (`benchmark_key`) — медиана по сегменту и стадии.
Используется в боте сразу после ответа («ваша 21%, средняя по сегменту — 22%»)
и в PDF.

Сейчас — захардкоженные приближения. После 100+ Чекапов в проде —
заменить на чтение из таблицы checkup_benchmarks (агрегация из БД).
"""
from __future__ import annotations

from typing import Literal

Stage = Literal["start", "team", "structure", "maturity"]

# benchmark_key → segment → stage → mean
# Если segment='other' или нет данных — фолбэк на медиану по стадии (см. _ALL_STAGES).
BENCHMARK: dict[str, dict[str, dict[Stage, float]]] = {
    "margin_pct": {
        "edu":  {"start": 12, "team": 18, "structure": 22, "maturity": 25},
        "mp":   {"start": 4,  "team": 7,  "structure": 9,  "maturity": 11},
        "it":   {"start": 15, "team": 22, "structure": 26, "maturity": 28},
        "prod": {"start": 5,  "team": 10, "structure": 13, "maturity": 15},
        "serv": {"start": 14, "team": 20, "structure": 23, "maturity": 25},
        "saas": {"start": 18, "team": 28, "structure": 35, "maturity": 40},
    },
    "conv_pct": {
        # Конверсия квалифицированная заявка → договор, %
        "edu":  {"start": 8,  "team": 12, "structure": 15, "maturity": 18},
        "mp":   {"start": 2,  "team": 3,  "structure": 4,  "maturity": 5},
        "it":   {"start": 15, "team": 22, "structure": 28, "maturity": 32},
        "prod": {"start": 10, "team": 14, "structure": 18, "maturity": 22},
        "serv": {"start": 20, "team": 28, "structure": 34, "maturity": 40},
        "saas": {"start": 5,  "team": 8,  "structure": 12, "maturity": 16},
    },
    "founder_time_pct": {
        # Доля времени фаундера на стратегию, %
        "edu":  {"start": 15, "team": 25, "structure": 40, "maturity": 55},
        "mp":   {"start": 15, "team": 25, "structure": 40, "maturity": 55},
        "it":   {"start": 15, "team": 25, "structure": 40, "maturity": 55},
        "prod": {"start": 15, "team": 25, "structure": 40, "maturity": 55},
        "serv": {"start": 15, "team": 25, "structure": 40, "maturity": 55},
        "saas": {"start": 15, "team": 25, "structure": 40, "maturity": 55},
    },
    "hours_per_week": {
        # Часов/неделю у ключевых сотрудников
        "edu":  {"start": 55, "team": 50, "structure": 48, "maturity": 45},
        "mp":   {"start": 55, "team": 50, "structure": 48, "maturity": 45},
        "it":   {"start": 55, "team": 50, "structure": 48, "maturity": 45},
        "prod": {"start": 55, "team": 50, "structure": 48, "maturity": 45},
        "serv": {"start": 55, "team": 50, "structure": 48, "maturity": 45},
        "saas": {"start": 55, "team": 50, "structure": 48, "maturity": 45},
    },
}

# Медианы по стадии (для segment='other' или отсутствующего segment)
_ALL_STAGES: dict[str, dict[Stage, float]] = {
    "margin_pct":       {"start": 10, "team": 16, "structure": 21, "maturity": 24},
    "conv_pct":         {"start": 10, "team": 14, "structure": 19, "maturity": 22},
    "founder_time_pct": {"start": 15, "team": 25, "structure": 40, "maturity": 55},
    "hours_per_week":   {"start": 55, "team": 50, "structure": 48, "maturity": 45},
}


def lookup_benchmark(
    benchmark_key: str,
    segment: str | None,
    stage: Stage | None,
) -> float | None:
    """Возвращает среднюю по сегменту × стадии. None если не нашли."""
    if not stage:
        return None
    seg_data = BENCHMARK.get(benchmark_key, {})
    if segment and segment in seg_data:
        return seg_data[segment].get(stage)
    fallback = _ALL_STAGES.get(benchmark_key, {})
    return fallback.get(stage)


def compare_to_benchmark(value: float, mean: float, unit: str = "") -> str:
    """Человекочитаемое сравнение значения с бенчмарком."""
    delta = value - mean
    abs_delta = abs(delta)
    if abs_delta < 2:
        return f"Вы на уровне среднего ({mean}{unit})."
    if delta > 0:
        return f"Вы на {abs_delta:.0f} {unit} выше среднего ({mean}{unit})."
    return f"Вы на {abs_delta:.0f} {unit} ниже среднего ({mean}{unit})."


def is_concerning(benchmark_key: str, value: float) -> tuple[bool, str | None]:
    """Возвращает (is_concerning, message) для красных флагов."""
    if benchmark_key == "founder_time_pct":
        if value <= 5:
            return True, "Фаундер почти полностью в операционке — это типовая ловушка стадии Команда."
        if value >= 75:
            return True, "Фаундер почти не в операционке — есть риск оторванности от реальности команды."
    elif benchmark_key == "hours_per_week":
        if value >= 60:
            return True, "60+ часов/неделю у ключевых — высокий риск выгорания и текучки."
        if value <= 30:
            return True, "30 ч/нед или меньше — стоит проверить, нет ли скрытой недозагрузки."
    elif benchmark_key == "margin_pct":
        if value <= 0:
            return True, "Маржа в минусе — приоритет №1 на ближайшие 90 дней."
    return False, None
