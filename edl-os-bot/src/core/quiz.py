"""Mini-Чекап v2.0 — 2 предварительных + 12 основных вопросов по 4 слоям.

Score = взвешенное среднее 4 слоёв с весами по стадии роста (stage-relative readiness).
Заменяет старый /quiz (12 вопросов, равные веса, без бенчмарка).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Layer = Literal["01", "02", "03", "04"]
Stage = Literal["start", "team", "structure", "maturity"]


@dataclass(slots=True, frozen=True)
class MiniQuestion:
    key: str
    layer: Layer
    order: int
    text: str
    options: tuple[tuple[str, int], ...]


@dataclass(slots=True, frozen=True)
class GrowthPoint:
    layer: Layer
    layer_label: str
    question_key: str
    short: str
    action: str


@dataclass(slots=True, frozen=True)
class MiniCheckupResult:
    score: int
    category: str
    category_color: Literal["red", "orange", "yellow", "green"]
    stage: Stage
    stage_label: str
    stage_confidence: Literal["high", "low"]
    segment: str
    segment_label: str
    layer_scores: dict[Layer, int]
    benchmark_mean: int | None
    benchmark_delta: int | None
    growth_points: tuple[GrowthPoint, GrowthPoint, GrowthPoint]
    cta_primary: Literal["audit", "audit_plus", "diagnostic_waitlist"]
    cta_secondary: Literal["audit", "audit_plus", "demo"]


# P2 option → stage (с confidence)
STAGE_FROM_P2: dict[str, Stage] = {
    "start":              "start",
    "team":               "team",
    "structure":          "structure",
    "maturity":           "maturity",
    "outlier_small_team": "team",      # default confidence=low
    "outlier_big_team":   "structure", # default confidence=low
}

STAGE_WEIGHTS: dict[Stage, dict[Layer, float]] = {
    "start":     {"01": 0.35, "02": 0.25, "03": 0.15, "04": 0.25},
    "team":      {"01": 0.30, "02": 0.30, "03": 0.20, "04": 0.20},
    "structure": {"01": 0.25, "02": 0.25, "03": 0.30, "04": 0.20},
    "maturity":  {"01": 0.30, "02": 0.20, "03": 0.30, "04": 0.20},
}

STAGE_LABEL: dict[Stage, str] = {
    "start":     "Старт",
    "team":      "Команда",
    "structure": "Структура",
    "maturity":  "Зрелость",
}

STAGE_DESC: dict[Stage, str] = {
    "start":     "1–10 чел · до 15 М ₽",
    "team":      "10–25 чел · 15–60 М ₽",
    "structure": "25–50 чел · 60–200 М ₽",
    "maturity":  "50+ чел · 200 М+ ₽",
}

SEGMENT_LABEL: dict[str, str] = {
    "edu":   "онлайн-школ",
    "mp":    "маркетплейсов",
    "it":    "IT-агентств",
    "prod":  "производств/опта",
    "serv":  "услуг",
    "saas":  "B2B SaaS",
    "other": "вашего сегмента",
}

SEGMENT_DISPLAY: dict[str, str] = {
    "edu":   "Онлайн-школа / EdTech",
    "mp":    "Маркетплейс / e-commerce",
    "it":    "IT / digital-агентство",
    "prod":  "Производство / опт / B2B-поставки",
    "serv":  "Услуги (консалтинг, юр-, бух-, медицина)",
    "saas":  "B2B SaaS / подписочный продукт",
    "other": "Другое",
}

LAYER_LABEL: dict[Layer, str] = {
    "01": "Стратегия",
    "02": "Воронка",
    "03": "Операционка",
    "04": "Деньги",
}

VALID_SCORES: frozenset[int] = frozenset({0, 3, 5, 8, 10})

QUIZ_QUESTIONS: tuple[MiniQuestion, ...] = (
    # ── Слой 01 · Стратегия ────────────────────────────────────────────────
    MiniQuestion(
        key="s1_horizon_3y",
        layer="01",
        order=1,
        text="1/12 · У вас есть 3-летняя картина: продукт, выручка, команда?",
        options=(
            ("Не думал так далеко", 0),
            ("Есть смутный образ", 3),
            ("Есть 1–2 ставки, без цифр", 5),
            ("3 ставки и метрики по ним", 8),
            ("Записано, согласовано, ежеквартально пересматриваю", 10),
        ),
    ),
    MiniQuestion(
        key="s2_year_focus",
        layer="01",
        order=2,
        text="2/12 · Фокус года — есть и понятен команде?",
        options=(
            ("Фокуса нет, делаем всё подряд", 0),
            ("Фокус знаю я, команда — не очень", 3),
            ("Озвучивал, но без документа", 5),
            ("Один документ, синхрон раз в квартал", 8),
            ("Каждый сотрудник назовёт фокус года", 10),
        ),
    ),
    MiniQuestion(
        key="s3_not_doing",
        layer="01",
        order=3,
        text="3/12 · Понимаете, что НЕ делать в этом году?",
        options=(
            ("Беремся за всё, что приходит", 0),
            ("Иногда отказываю, без правила", 3),
            ("Есть негласные критерии", 5),
            ("Есть явный список «не делаем»", 8),
            ("Список — часть стратегии, команда сверяется", 10),
        ),
    ),
    # ── Слой 02 · Воронка ──────────────────────────────────────────────────
    MiniQuestion(
        key="f1_pipeline_home",
        layer="02",
        order=4,
        text="4/12 · Где живёт ваша воронка продаж?",
        options=(
            ("В голове / в переписках", 0),
            ("Excel/Sheets, обновляю редко", 3),
            ("CRM, дисциплина средняя", 5),
            ("CRM + регулярный обзор", 8),
            ("CRM + автосводка + конверсии по этапам", 10),
        ),
    ),
    MiniQuestion(
        key="f2_conv_demo_deal",
        layer="02",
        order=5,
        text="5/12 · Конверсия из заявки в договор — знаете?",
        options=(
            ("Не считаю", 0),
            ("Примерно на глаз", 3),
            ("Общую знаю", 5),
            ("Знаю по сегментам", 8),
            ("Знаю по сегментам и по продавцу", 10),
        ),
    ),
    MiniQuestion(
        key="f3_deal_cycle",
        layer="02",
        order=6,
        text="6/12 · Средний цикл сделки в днях?",
        options=(
            ("Не знаю", 0),
            ("Обычно столько-то", 3),
            ("Считал руками", 5),
            ("Знаю и трекаю", 8),
            ("Знаю и вижу, где застревает", 10),
        ),
    ),
    # ── Слой 03 · Операционка ──────────────────────────────────────────────
    MiniQuestion(
        key="o1_team_load",
        layer="03",
        order=7,
        text="7/12 · Загрузка команды — что у вас с этим?",
        options=(
            ("Не считаю, все «вроде заняты»", 0),
            ("На глаз", 3),
            ("Раз в пару месяцев", 5),
            ("Регулярная сводка по часам", 8),
            ("Загрузка считается автоматически, узкие места заранее", 10),
        ),
    ),
    MiniQuestion(
        key="o2_bottleneck",
        layer="03",
        order=8,
        text="8/12 · Узкое горлышко в доставке — известно?",
        options=(
            ("Не знаю", 0),
            ("Догадываюсь", 3),
            ("Знаю, не системно", 5),
            ("Работаю с ним", 8),
            ("Решено, узкое место сместилось дальше", 10),
        ),
    ),
    MiniQuestion(
        key="o3_rhythm",
        layer="03",
        order=9,
        text="9/12 · Есть ли у бизнеса недельный/месячный ритм встреч и сводок?",
        options=(
            ("Ритма нет", 0),
            ("Встречаемся когда горит", 3),
            ("Недельная планёрка", 5),
            ("Недельный + месячный ритм с метриками", 8),
            ("Daily/weekly/monthly синхронизованы, сводки автоматически", 10),
        ),
    ),
    # ── Слой 04 · Деньги ───────────────────────────────────────────────────
    MiniQuestion(
        key="m1_company_margin",
        layer="04",
        order=10,
        text="10/12 · Маржа по компании в целом — знаете цифру?",
        options=(
            ("Нет", 0),
            ("Очень примерно", 3),
            ("Раз в квартал", 5),
            ("Каждый месяц", 8),
            ("Каждый месяц + понимаю, что её двигает", 10),
        ),
    ),
    MiniQuestion(
        key="m2_cash_30d",
        layer="04",
        order=11,
        text="11/12 · Cash на 30 дней вперёд — видите?",
        options=(
            ("Нет", 0),
            ("Считаю руками когда тревожно", 3),
            ("Sheets, обновляю раз в месяц", 5),
            ("Сводка регулярно", 8),
            ("Cash на 90 дней с поступлениями/платежами на одном экране", 10),
        ),
    ),
    MiniQuestion(
        key="m3_vat_2026",
        layer="04",
        order=12,
        text="12/12 · НДС-2026 / антидробление — есть понятная картина?",
        options=(
            ("Тревожно, не понимаю", 0),
            ("Слышал, не считал", 3),
            ("Считал с бухгалтером", 5),
            ("Есть финансовая модель сценариев", 8),
            ("Решение принято, действуем по плану", 10),
        ),
    ),
)


def stage_detection(p2_option: str) -> tuple[Stage, Literal["high", "low"]]:
    """Определяем стадию и уверенность из выбора P2."""
    if p2_option in ("start", "team", "structure", "maturity"):
        return p2_option, "high"  # type: ignore[return-value]
    stage = STAGE_FROM_P2.get(p2_option, "team")
    return stage, "low"  # type: ignore[return-value]


def layer_score_0_100(answers: dict[str, int], layer: Layer) -> float:
    """3 вопроса × 10 max = 30 → шкалируем к 0..100."""
    qs = [q for q in QUIZ_QUESTIONS if q.layer == layer]
    raw = sum(answers.get(q.key, 0) for q in qs)
    return raw * 100 / (10 * len(qs))


def total_score(answers: dict[str, int], stage: Stage) -> int:
    """Взвешенная сумма layer-scores по весам стадии → 0..100."""
    weights = STAGE_WEIGHTS[stage]
    s = sum(
        layer_score_0_100(answers, L) * weights[L]  # type: ignore[arg-type]
        for L in ("01", "02", "03", "04")
    )
    return round(s)


def category_label(score: int) -> tuple[str, Literal["red", "orange", "yellow", "green"]]:
    if score <= 40:
        return "Бизнес держится на вас лично", "red"
    if score <= 60:
        return "Есть базовая структура, много пробелов", "orange"
    if score <= 75:
        return "Зрелая инфраструктура, но узкие места видны", "yellow"
    return "Готовая к масштабированию операционная база", "green"


def layer_color(score: int) -> str:
    if score >= 75:
        return "🟢"
    if score >= 50:
        return "🟡"
    return "🔴"


def cta_for_score(
    score: int,
) -> tuple[
    Literal["audit", "audit_plus", "diagnostic_waitlist"],
    Literal["audit", "audit_plus", "demo"],
]:
    if score <= 40:
        return "audit", "demo"
    if score <= 70:
        return "audit_plus", "audit"
    return "diagnostic_waitlist", "audit_plus"


def top3_growth_points(answers: dict[str, int], stage: Stage) -> list[GrowthPoint]:
    from src.core.growth_hints import hint_for

    layer_sc = {
        L: layer_score_0_100(answers, L)  # type: ignore[arg-type]
        for L in ("01", "02", "03", "04")
    }
    # Weakest 3 layers first
    sorted_layers = sorted(layer_sc.items(), key=lambda x: x[1])[:3]

    points: list[GrowthPoint] = []
    for layer, _ in sorted_layers:
        layer_qs = [q for q in QUIZ_QUESTIONS if q.layer == layer]
        worst_q = min(layer_qs, key=lambda q: answers.get(q.key, 0))
        ans_score = answers.get(worst_q.key, 0)
        short, action = hint_for(worst_q.key, ans_score)
        points.append(
            GrowthPoint(
                layer=layer,  # type: ignore[arg-type]
                layer_label=LAYER_LABEL[layer],  # type: ignore[index]
                question_key=worst_q.key,
                short=short,
                action=action,
            )
        )
    return points


def build_result(
    answers: dict[str, int],
    stage: Stage,
    segment: str,
    stage_confidence: Literal["high", "low"] = "high",
) -> MiniCheckupResult:
    from src.core.benchmarks import benchmark_for

    score = total_score(answers, stage)
    cat_text, cat_color = category_label(score)
    ls = {
        L: round(layer_score_0_100(answers, L))  # type: ignore[misc]
        for L in ("01", "02", "03", "04")
    }
    bm_mean, bm_delta = benchmark_for(segment, stage, score)
    gp = top3_growth_points(answers, stage)
    cta_p, cta_s = cta_for_score(score)

    return MiniCheckupResult(
        score=score,
        category=cat_text,
        category_color=cat_color,
        stage=stage,
        stage_label=STAGE_LABEL[stage],
        stage_confidence=stage_confidence,
        segment=segment,
        segment_label=SEGMENT_LABEL.get(segment, "вашего сегмента"),
        layer_scores=ls,  # type: ignore[arg-type]
        benchmark_mean=bm_mean,
        benchmark_delta=bm_delta,
        growth_points=tuple(gp),  # type: ignore[arg-type]
        cta_primary=cta_p,
        cta_secondary=cta_s,
    )
