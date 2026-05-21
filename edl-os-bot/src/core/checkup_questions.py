"""Чекап v2.0 — 20 гибридных вопросов (5 на слой = 3 MC + 1 numeric + 1 short-text).

Канон: TZ_checkup_plus_v2.md §4.
Layer codes: '01' Стратегия / '02' Воронка / '03' Операционка / '04' Деньги
(совместимо с Mini-Чекап v2 core/quiz.py).

Старый Чекап v1 был 20 open-text вопросами с ключами `s1_horizon`...`m5_decisions_90`.
Эти ключи помечены в `LEGACY_V1_KEYS` — старые `CheckupAnswer` строки в БД остаются
валидными (миграция 0013 не трогает существующие данные), но новые application'ы
работают только с новыми ключами `c1..c20`.

Также экспортируем `determine_vat_zone()` — используется в PDF-репорте для
анализа short-text ответа `c20_vat_2026_scenario`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Layer = Literal["01", "02", "03", "04"]
AnswerType = Literal["mc", "numeric", "short_text"]

LAYER_LABEL: dict[Layer, str] = {
    "01": "Стратегия",
    "02": "Воронка",
    "03": "Операционка",
    "04": "Деньги",
}

LAYER_EMOJI: dict[Layer, str] = {
    "01": "📍",
    "02": "📈",
    "03": "⚙️",
    "04": "💰",
}

VALID_MC_SCORES: frozenset[int] = frozenset({0, 3, 5, 8, 10})


@dataclass(slots=True, frozen=True)
class CheckupQuestionV2:
    key: str
    layer: Layer
    order: int                            # 1..20
    answer_type: AnswerType
    text: str
    why_we_ask: str
    # MC:
    options: tuple[tuple[str, int], ...] | None = None
    # numeric:
    numeric_min: float | None = None
    numeric_max: float | None = None
    numeric_unit: str | None = None       # '%' | 'ч/нед'
    benchmark_key: str | None = None      # 'margin_pct' / 'conv_pct' / 'founder_time_pct' / 'hours_per_week'
    numeric_guidance: str | None = None
    allow_skip: bool = False              # «не знаю» → answer_skipped=True
    # short-text:
    min_chars: int | None = None
    min_words: int | None = None
    expects: tuple[str, ...] | None = None
    example_good: str | None = None
    # flow:
    section_break_after: bool = False     # True после Q5/Q10/Q15


# Backward-compatible alias — старый код импортирует `CheckupQuestion`.
CheckupQuestion = CheckupQuestionV2


CHECKUP_QUESTIONS: tuple[CheckupQuestionV2, ...] = (
    # ──────── Слой 01 · Стратегия ─────────────────────────────────────────
    CheckupQuestionV2(
        key="c1_strategy_process",
        layer="01",
        order=1,
        answer_type="mc",
        text="Какой у вас процесс стратегии?",
        why_we_ask="Зрелость стратегического процесса = как часто и системно вы возвращаетесь к большим решениям.",
        options=(
            ("Нет стратегии, плывём", 0),
            ("Есть «в голове», не записано", 3),
            ("Записано раз, не пересматриваем", 5),
            ("Пересматриваем раз в год", 8),
            ("Квартальный ритм пересмотра стратегии с командой", 10),
        ),
    ),
    CheckupQuestionV2(
        key="c2_strategy_alternatives",
        layer="01",
        order=2,
        answer_type="mc",
        text="Как принимаете крупные решения (>3 М ₽ или влияющие на >20% выручки)?",
        why_we_ask="Зрелое принятие решений = альтернативы × финансовый эффект × pre-mortem.",
        options=(
            ("На интуиции, без альтернатив", 0),
            ("Думаю сам, обсуждаю с парой людей", 3),
            ("Готовим 2 варианта и выбираем", 5),
            ("3+ варианта, сценарный анализ", 8),
            ("3+ варианта × финансовый эффект × pre-mortem", 10),
        ),
    ),
    CheckupQuestionV2(
        key="c3_strategy_review",
        layer="01",
        order=3,
        answer_type="mc",
        text="Как часто синхронизируете команду по стратегии?",
        why_we_ask="Без ритма синхронизации стратегия живёт только в голове фаундера.",
        options=(
            ("Никогда / неформально", 0),
            ("Раз в полгода-год", 3),
            ("Раз в квартал", 5),
            ("Месячный ритм", 8),
            ("Месячный ритм + персональный goal-setting раз в квартал", 10),
        ),
    ),
    CheckupQuestionV2(
        key="c4_founder_time_strategy_pct",
        layer="01",
        order=4,
        answer_type="numeric",
        text="Какая доля вашего времени уходит на стратегию (не операционку)? Цифра в %",
        why_we_ask="Норма для стадии Команда — около 25%. Меньше 10% — фаундер в операционке; больше 70% — оторван от земли.",
        numeric_min=0,
        numeric_max=100,
        numeric_unit="%",
        benchmark_key="founder_time_pct",
        numeric_guidance="Стратегия = планирование, переговоры по новым направлениям, найм top-tier, инвесторы. Операционка = ежедневные решения, тушение пожаров, контроль.",
        allow_skip=True,
    ),
    CheckupQuestionV2(
        key="c5_strategy_antipattern",
        layer="01",
        order=5,
        answer_type="short_text",
        text="Главный анти-паттерн стратегии + механизм отлова (3–5 предложений)",
        why_we_ask="Анти-паттерн — страховка фокуса. Без неё стратегия размывается тихо.",
        min_chars=120,
        min_words=25,
        expects=("анти-паттерн", "механизм", "проверка"),
        example_good=(
            "Анти-паттерн: соглашаемся на любые проекты от знакомых, размывая фокус. "
            "Ловим: правило «новый клиент — только в нашей вертикали или через тендер». "
            "Проверка: каждую сделку >2 М ₽ выносим на еженедельный sales-review."
        ),
        section_break_after=True,
    ),
    # ──────── Слой 02 · Воронка ───────────────────────────────────────────
    CheckupQuestionV2(
        key="c6_funnel_home",
        layer="02",
        order=6,
        answer_type="mc",
        text="Где живёт ваша воронка?",
        why_we_ask="Если воронка не в одном месте — нельзя считать конверсии и сравнивать каналы.",
        options=(
            ("В голове / в переписках", 0),
            ("Excel/Sheets без структуры", 3),
            ("В CRM, но половина сделок не там", 5),
            ("CRM, дисциплина 80%+, обновление 1–3 дня", 8),
            ("CRM + автосинхрон с каналами + еженедельный обзор", 10),
        ),
    ),
    CheckupQuestionV2(
        key="c7_crm_discipline",
        layer="02",
        order=7,
        answer_type="mc",
        text="Кто обновляет CRM и насколько дисциплинированно?",
        why_we_ask="Дисциплина CRM — критерий зрелости отдела продаж. Без неё конверсии — фикция.",
        options=(
            ("Никто не обновляет", 0),
            ("Я сам когда вспомню", 3),
            ("Менеджеры частично", 5),
            ("Менеджеры дисциплинированно", 8),
            ("Автоматизация (звонки/чаты) → CRM auto-fill + ревью", 10),
        ),
    ),
    CheckupQuestionV2(
        key="c8_funnel_metrics",
        layer="02",
        order=8,
        answer_type="mc",
        text="Какие конверсии вы знаете по этапам воронки?",
        why_we_ask="Без поэтапных конверсий нельзя понять, где конкретно теряются клиенты — на демо, на КП или на этапе оплаты.",
        options=(
            ("Никаких", 0),
            ("Только финальную (лид → договор)", 3),
            ("2–3 этапа: лид → демо → договор", 5),
            ("Все этапы по сегментам", 8),
            ("Все этапы × сегменты × менеджер + alerts", 10),
        ),
    ),
    CheckupQuestionV2(
        key="c9_lead_to_deal_pct",
        layer="02",
        order=9,
        answer_type="numeric",
        text="Конверсия из квалифицированной заявки в договор за последние 3 месяца, %",
        why_we_ask="Главный показатель здоровья воронки. Сравним с бенчмарком по вашему сегменту и стадии.",
        numeric_min=0,
        numeric_max=100,
        numeric_unit="%",
        benchmark_key="conv_pct",
        numeric_guidance="Договоры подписанные / квалифицированные заявки (не общие лиды). Если не знаете точно — лучше прикинуть, чем ставить 0.",
        allow_skip=True,
    ),
    CheckupQuestionV2(
        key="c10_main_channel_blocker",
        layer="02",
        order=10,
        answer_type="short_text",
        text="Главный канал привлечения + что мешает его удвоить (3–5 предложений)",
        why_we_ask="Понимание блокера — половина роста. Часто блокер находится не в канале, а в процессах поддержки канала.",
        min_chars=120,
        min_words=25,
        expects=("канал", "объём", "блокирует"),
        example_good=(
            "Главный канал — сарафан от существующих клиентов (40% сделок). "
            "Чтобы удвоить, нужен системный механизм просьбы о реферале — сейчас просим интуитивно. "
            "Блокирует: нет процесса и нет мотивации клиенту рекомендовать. Также нет CRM-поля «откуда узнал»."
        ),
        section_break_after=True,
    ),
    # ──────── Слой 03 · Операционка ───────────────────────────────────────
    CheckupQuestionV2(
        key="c11_regulations",
        layer="03",
        order=11,
        answer_type="mc",
        text="Что у вас с регламентами повторяющихся процессов?",
        why_we_ask="Регламент = безотказная передача знаний при найме и отпусках. Без него каждое увольнение — катастрофа.",
        options=(
            ("Регламентов нет, всё устно", 0),
            ("Есть пара документов, но устарели", 3),
            ("Ключевые процессы описаны, обновляем редко", 5),
            ("Регламенты живые, владельцы, ревизия раз в полгода", 8),
            ("Регламенты + чек-листы + автоматизация", 10),
        ),
    ),
    CheckupQuestionV2(
        key="c12_rhythm",
        layer="03",
        order=12,
        answer_type="mc",
        text="Какой у вас рабочий ритм?",
        why_we_ask="Ритм — нервная система компании. Без daily/weekly/monthly теряется координация и срываются дедлайны.",
        options=(
            ("Ритма нет", 0),
            ("Встречаемся когда горит", 3),
            ("Недельная планёрка", 5),
            ("Daily + weekly + monthly с метриками", 8),
            ("Полный ритм + ретро + квартальные strategy sessions", 10),
        ),
    ),
    CheckupQuestionV2(
        key="c13_bus_factor",
        layer="03",
        order=13,
        answer_type="mc",
        text="Бас-фактор: что встанет, если ключевой человек уйдёт в отпуск на 2 недели?",
        why_we_ask="Бас-фактор показывает реальную автономность бизнеса. Минимум 2 — нужный уровень для масштабирования.",
        options=(
            ("Бизнес встанет", 0),
            ("Я лично всё буду тушить", 3),
            ("Часть процессов встанет, часть пойдёт", 5),
            ("Заместитель на каждой роли, передача за 1 день", 8),
            ("Команда самостоятельна, передача через документацию", 10),
        ),
    ),
    CheckupQuestionV2(
        key="c14_key_people_hours_per_week",
        layer="03",
        order=14,
        answer_type="numeric",
        text="Сколько часов в неделю работают ключевые сотрудники (включая вас)? Усреднённо.",
        why_we_ask="60+ часов = риск выгорания, текучка и потеря know-how. <35 ч может означать недозагрузку.",
        numeric_min=20,
        numeric_max=100,
        numeric_unit="ч/нед",
        benchmark_key="hours_per_week",
        numeric_guidance="Считаем фактические, не контрактные часы. Если у разных людей сильно разные — берите среднее по 3–5 ключевым ролям.",
        allow_skip=True,
    ),
    CheckupQuestionV2(
        key="c15_bottleneck_action",
        layer="03",
        order=15,
        answer_type="short_text",
        text="Узкое горлышко доставки + что с ним делать в ближайшие 90 дней (3–5 предложений)",
        why_we_ask="Узкое горлышко = точка наибольшего рычага. План на 90 дней превращает интуицию в действия.",
        min_chars=120,
        min_words=25,
        expects=("узкое место", "цифры", "план"),
        example_good=(
            "Узкое место — онбординг новых клиентов: занимает 14 дней вместо 3, "
            "потому что менеджер вручную собирает данные из 4 систем. "
            "План: 30 дней — единый формуляр + аккаунт-менеджер; 60 дней — интеграция с 1С; "
            "90 дней — KPI «онбординг ≤ 5 дней» в систему оценки."
        ),
        section_break_after=True,
    ),
    # ──────── Слой 04 · Деньги ────────────────────────────────────────────
    CheckupQuestionV2(
        key="c16_financial_reporting",
        layer="04",
        order=16,
        answer_type="mc",
        text="Финансовая отчётность — что у вас с регулярностью?",
        why_we_ask="Месячный P&L + cash flow на одной странице — минимум для управляемости.",
        options=(
            ("Никакой отчётности", 0),
            ("Бухгалтерия делает квартально, я не смотрю", 3),
            ("Смотрю баланс/P&L раз в месяц", 5),
            ("P&L + cash flow + ДДС каждый месяц", 8),
            ("Полный set + dashboards real-time + еженедельный ревью", 10),
        ),
    ),
    CheckupQuestionV2(
        key="c17_unit_economics",
        layer="04",
        order=17,
        answer_type="mc",
        text="Юнит-экономика — что вы про неё знаете?",
        why_we_ask="Без юнит-экономики масштабирование = умножение убытка.",
        options=(
            ("Не знаю что это", 0),
            ("Знаю термин, не считал", 3),
            ("Считал в Excel когда-то", 5),
            ("Знаю по основным продуктам/сегментам", 8),
            ("Знаю по сегментам × каналам × cohorts, автоматически", 10),
        ),
    ),
    CheckupQuestionV2(
        key="c18_cash_horizon",
        layer="04",
        order=18,
        answer_type="mc",
        text="Кассовое планирование — на какой горизонт?",
        why_we_ask="90 дней + сценарии — стандарт для среднего бизнеса. Меньше = реактивный режим, без подушки на провал.",
        options=(
            ("Не планируем", 0),
            ("На 1–2 недели вперёд", 3),
            ("На 30 дней", 5),
            ("На 90 дней с поступлениями и платежами", 8),
            ("90 дней + сценарии + alert на разрывы", 10),
        ),
    ),
    CheckupQuestionV2(
        key="c19_company_margin_pct",
        layer="04",
        order=19,
        answer_type="numeric",
        text="Маржа компании за прошлый год, %",
        why_we_ask="Главный показатель финансового здоровья. Сравним с бенчмарком по вашему сегменту.",
        numeric_min=-50,
        numeric_max=80,
        numeric_unit="%",
        benchmark_key="margin_pct",
        numeric_guidance="Чистая прибыль / выручка × 100. Если не знаете точно — оценка в пределах 5 п.п. ок, главное не ноль.",
        allow_skip=True,
    ),
    CheckupQuestionV2(
        key="c20_vat_2026_scenario",
        layer="04",
        order=20,
        answer_type="short_text",
        text="НДС-2026 / антидробление — ваша картина и решение (3–5 предложений)",
        why_we_ask="Порог 60 М ₽ в 2027 г. меняет экономику для многих сегментов. Решение принимается за 6–9 месяцев до перехода.",
        min_chars=150,
        min_words=30,
        expects=("влияние", "решение", "эффект"),
        example_good=(
            "Текущая выручка 48 М ₽ — попадаем под порог 60 М в 2027 при росте 25%. "
            "Решение: переводим часть линейки на полную НДС-схему с июля 2026, "
            "чтобы не делать резкого скачка. Финэффект: маржа упадёт с 24% до 19%, "
            "но мы компенсируем повышением цен +8% и оптимизацией ФОТ −300 тыс/мес."
        ),
    ),
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def by_layer() -> dict[Layer, list[CheckupQuestionV2]]:
    out: dict[Layer, list[CheckupQuestionV2]] = {"01": [], "02": [], "03": [], "04": []}
    for q in CHECKUP_QUESTIONS:
        out[q.layer].append(q)
    return out


def by_key() -> dict[str, CheckupQuestionV2]:
    return {q.key: q for q in CHECKUP_QUESTIONS}


def numeric_questions() -> list[CheckupQuestionV2]:
    return [q for q in CHECKUP_QUESTIONS if q.answer_type == "numeric"]


def mc_questions() -> list[CheckupQuestionV2]:
    return [q for q in CHECKUP_QUESTIONS if q.answer_type == "mc"]


def short_text_questions() -> list[CheckupQuestionV2]:
    return [q for q in CHECKUP_QUESTIONS if q.answer_type == "short_text"]


# Старые ключи Чекапа v1 — для распознавания «in-progress на старом flow»
LEGACY_V1_KEYS: frozenset[str] = frozenset({
    "s1_horizon", "s2_bets", "s3_not_doing", "s4_antipatterns", "s5_last_90_days",
    "f1_funnel_home", "f2_stage_conversion", "f3_acv_cycle_cac", "f4_sources_cost", "f5_bottleneck",
    "o1_load", "o2_project_margin", "o3_bottleneck", "o4_decisions", "o5_next_90_days",
    "m1_cashflow", "m2_ebitda", "m3_vat_2026", "m4_reserves", "m5_decisions_90",
})


# ── НДС-зона (используется в PDF-репорте при анализе ответа c20) ──────────────

VAT_ZONE_BELOW = "below_threshold"
VAT_ZONE_APPROACHING = "approaching"
VAT_ZONE_FIRST_TIME = "first_time"
VAT_ZONE_ESTABLISHED = "established"

_VAT_DESCRIPTIONS = {
    VAT_ZONE_BELOW: (
        "Вне зоны НДС-реформы 2026 — пока на УСН без НДС. "
        "Следите за динамикой выручки: порог снижается до 15 млн в 2027 году."
    ),
    VAT_ZONE_APPROACHING: (
        "В зоне риска на горизонте 2–3 лет. "
        "С 2027 порог снижается до 15 млн ₽, с 2028 — до 10 млн ₽. "
        "Подготовьте учётную систему и проконсультируйтесь с бухгалтером заранее."
    ),
    VAT_ZONE_FIRST_TIME: (
        "Впервые в 2026 году попадаете в НДС-учёт. "
        "Это центральный риск-фактор для вашего бизнеса. "
        "Необходимо выбрать ставку (5% без вычетов или 20% с вычетами), "
        "обновить договоры и настроить фискальный учёт до 01.01.2026."
    ),
    VAT_ZONE_ESTABLISHED: (
        "Уже работаете с НДС. Реформа 2026 для вас процедурная, не структурная. "
        "Проверьте договоры с контрагентами на УСН — им теперь нужны СФ."
    ),
}

_VAT_ADVICE = {
    VAT_ZONE_BELOW: "Продолжайте отслеживать выручку. Если приближаетесь к 15 млн — начните подготовку за 6 месяцев.",
    VAT_ZONE_APPROACHING: "Рекомендуем: встреча с бухгалтером в Q3 2026, выбор учётной системы с поддержкой НДС, обновление шаблонов договоров.",
    VAT_ZONE_FIRST_TIME: (
        "🔴 Срочно: (1) определите ставку НДС, (2) обновите договоры, "
        "(3) подключите онлайн-кассу с НДС, (4) уведомите топ-клиентов."
    ),
    VAT_ZONE_ESTABLISHED: "Проверьте контрагентов на УСН — проведите аудит договорной базы на предмет НДС-корректности.",
}


def _extract_revenue_millions(text: str) -> float | None:
    patterns = [
        r"(\d[\d\s]*)\s*млн",
        r"(\d[\d\s]*)\s*m\b",
        r"(\d+)\s*000\s*000",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw = m.group(1).replace(" ", "")
            try:
                return float(raw)
            except ValueError:
                pass
    return None


def determine_vat_zone(answer_text: str) -> dict:
    """Определяет зону риска по НДС-реформе 2026 на основе текста ответа.

    Работает с ответом на c20_vat_2026_scenario (или совместимо со старым m3_vat_2026).
    Возвращает dict с ключами: zone, description, advice.
    """
    t = (answer_text or "").lower()

    rev = _extract_revenue_millions(t)
    if rev is not None:
        if rev < 10:
            zone = VAT_ZONE_BELOW
        elif rev < 20:
            zone = VAT_ZONE_APPROACHING
        elif rev < 60:
            zone = VAT_ZONE_FIRST_TIME
        else:
            zone = VAT_ZONE_ESTABLISHED
        return {"zone": zone, "description": _VAT_DESCRIPTIONS[zone], "advice": _VAT_ADVICE[zone]}

    if any(k in t for k in ("усн с ндс", "осно", "ндс 20%", "ндс 5%", "плательщик ндс", "с ндс")):
        zone = VAT_ZONE_ESTABLISHED
    elif any(k in t for k in ("60", "80", "100", "150", "200", "свыше 60", "больше 60", "> 60")):
        zone = VAT_ZONE_ESTABLISHED
    elif any(k in t for k in ("20", "30", "40", "50", "20-60", "20–60", "30–60")):
        zone = VAT_ZONE_FIRST_TIME
    elif any(k in t for k in ("10", "15", "10-20", "10–20")):
        zone = VAT_ZONE_APPROACHING
    else:
        zone = VAT_ZONE_BELOW

    return {"zone": zone, "description": _VAT_DESCRIPTIONS[zone], "advice": _VAT_ADVICE[zone]}
