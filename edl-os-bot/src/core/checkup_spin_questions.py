"""16 SPIN-вопросов Чекапа Plus v2.0 (ТЗ §3.3).

Структура: 4 слоя × 4 SPIN-вопроса = 16 вопросов.
Слои: strategy → funnel → operations → money.

SPIN-методология (Нил Рэкхем, 1988):
- Situation (контекст)
- Problem (где разрыв)
- Implication (цена проблемы в ₽/мес)
- Need-Payoff (масштаб ценности решения)

Каждый вопрос имеет пример хорошего ответа в SPIN-логике, который зрелый
собственник дал бы. Примеры различаются по архетипу (6 MVP, см.
checkup_archetypes.py). Клиент, читая пример, мысленно прикладывает его к
своему бизнесу и обнаруживает свои потери — это и есть продающий
механизм Чекапа.

Главное отличие от старого checkup_questions.py (20 quiz-вопросов
со скорингом 0/25/50/75/100): здесь все ответы — open-text, скоринг
скрытый через Claude Haiku 4.5 в момент генерации PDF.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Layer = Literal["strategy", "funnel", "operations", "money"]
LAYER_LABELS: dict[Layer, str] = {
    "strategy": "СТРАТЕГИЯ",
    "funnel": "ВОРОНКА",
    "operations": "ОПЕРАЦИОНКА",
    "money": "ДЕНЬГИ",
}
LAYER_SUBTITLES: dict[Layer, str] = {
    "strategy": "НАПРАВЛЕНИЕ",
    "funnel": "КЛИЕНТЫ",
    "operations": "ПРОЦЕССЫ",
    "money": "ФИНАНСЫ",
}
LAYER_NUMBERS: dict[Layer, str] = {
    "strategy": "01",
    "funnel": "02",
    "operations": "03",
    "money": "04",
}


@dataclass(frozen=True)
class SpinQuestion:
    """Один SPIN-вопрос. Все 16 хранятся в SPIN_QUESTIONS ниже."""

    id: str                    # "Q1.1" ... "Q4.4"
    layer: Layer
    order_in_layer: int        # 1..4
    situation: str             # курсив, 1-2 строки
    problem: str               # bold, основной вопрос

    @property
    def number(self) -> int:
        """Глобальный номер 1..16."""
        layers_order = ("strategy", "funnel", "operations", "money")
        return layers_order.index(self.layer) * 4 + self.order_in_layer

    @property
    def global_order(self) -> int:
        return self.number


# ── 16 SPIN-вопросов (ТЗ §3.3) ──────────────────────────────────────────────


SPIN_QUESTIONS: tuple[SpinQuestion, ...] = (
    # ── СЛОЙ 01 · СТРАТЕГИЯ ─────────────────────────────────────────────────
    SpinQuestion(
        id="Q1.1",
        layer="strategy",
        order_in_layer=1,
        situation="Стратегия — не документ, а серия еженедельных решений. Хотим увидеть динамику.",
        problem="Что сдвинулось в стратегии за последние 90 дней — какие 1–2 ставки и почему?",
    ),
    SpinQuestion(
        id="Q1.2",
        layer="strategy",
        order_in_layer=2,
        situation="Конкурентная позиция — это не «мы лучше». Это конкретная причина, почему клиент выбирает вас при равных условиях.",
        problem="Назовите 2–3 конкретных причины, почему клиент выбирает вас, а не ближайшего конкурента — в формате, который вы могли бы вписать в бриф маркетингу.",
    ),
    SpinQuestion(
        id="Q1.3",
        layer="strategy",
        order_in_layer=3,
        situation="Сильная стратегия определяется не только тем, кому продают, но и тем, кому осознанно не продают.",
        problem="Кому из обратившихся за последние 3 месяца вы отказали — и по каким критериям? (если не отказывали — это уже ответ)",
    ),
    SpinQuestion(
        id="Q1.4",
        layer="strategy",
        order_in_layer=4,
        situation="Стратегия в голове фаундера и стратегия в действиях команды — это часто две разные стратегии.",
        problem="Если попросить трёх ключевых членов команды описать миссию компании в одном предложении — насколько совпадут их формулировки с вашей?",
    ),
    # ── СЛОЙ 02 · ВОРОНКА ───────────────────────────────────────────────────
    SpinQuestion(
        id="Q2.1",
        layer="funnel",
        order_in_layer=1,
        situation="В воронке самая дорогая метрика не CAC и не LTV, а время от первого касания до решения.",
        problem="Какой средний цикл от первого касания до оплаты у вас, и где в этом цикле клиент дольше всего «зависает»?",
    ),
    SpinQuestion(
        id="Q2.2",
        layer="funnel",
        order_in_layer=2,
        situation="ICP-фильтр — это не отказ от лидов. Это перенаправление нецелевых клиентов в правильное место без затрат времени отдела продаж.",
        problem="Какие 2–3 вопроса вы задаёте на этапе заявки для отсечения нецелевых лидов до отдела продаж? Или все лиды попадают на менеджеров одинаково?",
    ),
    SpinQuestion(
        id="Q2.3",
        layer="funnel",
        order_in_layer=3,
        situation="Если 75%+ лидов из одного канала — это не воронка, это однонитка.",
        problem="На какие 3 главных канала привлечения вы опираетесь — и какой процент лидов даёт каждый? Что будет с воронкой, если самый большой канал просядет на 30%?",
    ),
    SpinQuestion(
        id="Q2.4",
        layer="funnel",
        order_in_layer=4,
        situation="Информация о клиенте, собранная в воронке, часто не доходит до продуктовой команды.",
        problem="Какие 3 вещи о новом клиенте вы узнаёте на этапе продажи, и какие из них доходят до того, кто будет его обслуживать, до первого контакта?",
    ),
    # ── СЛОЙ 03 · ОПЕРАЦИОНКА ──────────────────────────────────────────────
    SpinQuestion(
        id="Q3.1",
        layer="operations",
        order_in_layer=1,
        situation="Узкое место, которое можно посчитать в деньгах — это уже не «надо переделать», а проект с экономикой.",
        problem="Главное узкое место в операционке прямо сейчас — и сколько оно вам стоит в ₽/мес (можно оценочно).",
    ),
    SpinQuestion(
        id="Q3.2",
        layer="operations",
        order_in_layer=2,
        situation="Делегирование без возврата — это когда вы передали решение, и оно реально приняло без вас.",
        problem="Какой процент операционных решений принимается командой без возврата к вам — и насколько вас устраивает эта цифра для текущей стадии?",
    ),
    SpinQuestion(
        id="Q3.3",
        layer="operations",
        order_in_layer=3,
        situation="Ритм командных встреч — это не календарь. Это структура, в которой данные регулярно проверяются.",
        problem="Какой у вас регулярный ритм встреч в команде, и какие данные обязательно сводятся к каждой встрече?",
    ),
    SpinQuestion(
        id="Q3.4",
        layer="operations",
        order_in_layer=4,
        situation="Онбординг нового сотрудника на стадии Команда — это либо системный процесс с чек-листом, либо личное время фаундера. Третьего не дано.",
        problem="Опишите процесс онбординга последнего нового сотрудника — сколько времени и чьего на это ушло?",
    ),
    # ── СЛОЙ 04 · ДЕНЬГИ ───────────────────────────────────────────────────
    SpinQuestion(
        id="Q4.1",
        layer="money",
        order_in_layer=1,
        situation="Маржа по компании — это среднее по больнице. Маржа по продукту вскрывает, какой продукт тянет, а какой топит.",
        problem="Какая маржа по каждому из ваших продуктов отдельно — и какой продукт самый рентабельный, какой убыточный?",
    ),
    SpinQuestion(
        id="Q4.2",
        layer="money",
        order_in_layer=2,
        situation="Финансовые решения, принятые на устаревшем P&L — это решения на ощущениях.",
        problem="К какому числу следующего месяца у вас закрыт P&L предыдущего, и как часто маркетинговый бюджет утверждается до закрытия?",
    ),
    SpinQuestion(
        id="Q4.3",
        layer="money",
        order_in_layer=3,
        situation="Runway — это не сколько денег на счету, а сколько месяцев бизнес проживёт при текущих расходах.",
        problem="Сколько месяцев runway у вас сейчас при текущих расходах и нулевой новой выручке?",
    ),
    SpinQuestion(
        id="Q4.4",
        layer="money",
        order_in_layer=4,
        situation="С 1 января 2026 порог УСН для НДС снижен с 60М ₽ до 20М ₽ (закон №425-ФЗ). Для большинства сегментов это критично.",
        problem="Какая у вас выручка 2025 года и какой план на НДС-2026 (порог 20М/60М): остаётесь УСН с НДС, переходите на ОСНО, или планируете остаться ниже порога?",
    ),
)


# ── Лукапы ──────────────────────────────────────────────────────────────────


SPIN_BY_ID: dict[str, SpinQuestion] = {q.id: q for q in SPIN_QUESTIONS}


def get_question(qid: str) -> SpinQuestion | None:
    return SPIN_BY_ID.get(qid)


def get_question_by_index(idx: int) -> SpinQuestion | None:
    """Index 0..15."""
    if 0 <= idx < len(SPIN_QUESTIONS):
        return SPIN_QUESTIONS[idx]
    return None


def total_questions() -> int:
    return len(SPIN_QUESTIONS)


def questions_for_layer(layer: Layer) -> tuple[SpinQuestion, ...]:
    return tuple(q for q in SPIN_QUESTIONS if q.layer == layer)


# ── Маркеры причин «не знаю / не считаем» (ТЗ §3.6) ─────────────────────────


DECLINE_MARKERS: tuple[str, ...] = (
    "не знаю",
    "не знаем",
    "не считаем",
    "не отслеживаем",
    "не релевантно",
    "не хочу раскрывать",
    "пропустить",
    "skip",
)


def is_decline_answer(text: str) -> tuple[bool, str | None]:
    """Возвращает (True, marker) если ответ — осознанный не-ответ.

    ТЗ §3.6: «не знаю» / «не считаем» — валидный ответ с флагом is_decline=true.
    Попадает в PDF как сигнал, но НЕ как пропуск.
    """
    lowered = text.lower().strip()
    # Принимаем как decline только короткие ответы целиком из markers
    if len(lowered) > 80:
        return False, None
    for marker in DECLINE_MARKERS:
        if lowered == marker or lowered.startswith(marker):
            return True, marker
    return False, None
