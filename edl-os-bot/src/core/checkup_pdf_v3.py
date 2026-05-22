"""PDF v3 — финальный шаблон Екатерины + Claude Haiku 4.5 (ТЗ Plus v2.0 §5).

Pipeline:
1. Сбор данных (ответы клиента + архетип + метаданные).
2. Claude Haiku 4.5 → JSON data dict по контракту.
3. Pydantic-валидация.
4. Jinja2 render `templates/edl_chekap_template.html`.
5. WeasyPrint → PDF.

Если Claude failed (timeout / невалидный JSON / rate limit) — fallback
на `ARCHETYPE_FALLBACKS[archetype]` (заранее заготовленные данные для
архетипа). Клиент в любом случае получает PDF в ~3 минуты.

Feature flag `CHECKUP_PDF_V3_ENABLED` контролирует включение:
по умолчанию выключен, в проде включается через FeatureFlag в БД.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Template
from pydantic import BaseModel, Field, ValidationError

from src.core.checkup_archetypes import (
    ARCHETYPE_META,
    ArchetypeKey,
    get_archetype_for_user,
    get_benchmark_avg,
    get_stage_weights,
)
from src.core.checkup_spin_questions import SPIN_QUESTIONS, LAYER_LABELS
from src.core.config import settings
from src.core.llm import get_client

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "edl_chekap_template.html"
SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "checkup_pdf_data_generator.md"

CLAUDE_MAX_TOKENS = 8000
CLAUDE_RETRIES = 3
CLAUDE_RETRY_BACKOFF_SECS = (1, 3, 9)

# Запрещённые слова — финальная проверка перед рендером (ТЗ §1.2)
FORBIDDEN_WORDS_IN_PDF: tuple[str, ...] = (
    "окупается",
    "окупаемость",
    "грандиозн",
    "революционн",
    "купите",
    "закажите",
    "лучший в россии",
    "без вопросов, без условий",
    "no-questions-asked",
    "эксклюзивная методология",
)


# ── Pydantic-схема валидации (минимальная — структурная) ─────────────────────


class ScoreData(BaseModel):
    total: int = Field(ge=0, le=100)
    benchmark_avg: int = Field(ge=0, le=100)
    delta_vs_benchmark_pct: int
    stage_readiness_pct: int = Field(ge=0, le=100)


class LayerMetric(BaseModel):
    name: str
    value: str
    status: str  # "green" | "yellow" | "red"


class LayerConnection(BaseModel):
    label: str
    status: str


class LayerData(BaseModel):
    key: str
    number: str
    title: str
    subtitle: str
    score: int = Field(ge=0, le=100)
    diagnosis: str
    metrics: list[LayerMetric]
    connections: list[LayerConnection]
    key_insight: str | None = None


class ExecutiveSummaryItem(BaseModel):
    eyebrow: str
    title: str
    layer_impact: str = ""  # ТЗ §6.3, может быть пустой строкой если LLM не заполнил
    description: str
    money_impact_rub: int | None = None


class CheckupDataSchema(BaseModel):
    """Минимальная валидация data dict. Жёстко проверяем критичные поля."""

    plan: str
    company: dict[str, Any]
    report: dict[str, Any]
    score: ScoreData
    executive_summary: list[ExecutiveSummaryItem]
    founder_vision: dict[str, Any]
    layers: list[LayerData]
    connections_analysis: dict[str, Any]
    cost_analysis: dict[str, Any]
    recommendations: list[dict[str, Any]]
    next_step: dict[str, Any]
    guarantee: dict[str, Any] | None = None
    legal_footer: list[str] = []
    # Plus-only — могут отсутствовать в Base
    deep_dive_layer: dict[str, Any] | None = None
    deep_dive_connection: dict[str, Any] | None = None
    extended_benchmark: dict[str, Any] | None = None
    personal_comment: dict[str, Any] | None = None


# ── Главный API ──────────────────────────────────────────────────────────────


async def build_pdf_data(
    *,
    plan: str,
    company_legal_name: str,
    segment: str | None,
    stage: str | None,
    spin_answers: dict[str, str],
    report_id: str,
    answers_count: int = 16,
) -> dict[str, Any]:
    """Сгенерировать data dict через Claude. Если не получится — fallback.

    `spin_answers` — словарь {Q1.1: "ответ", ..., Q4.4: "ответ"}.
    Если хотя бы один ответ отсутствует — поле заполняется placeholder'ом
    «(ответ не получен)»; в реальном flow FSM гарантирует наличие всех 16.
    """
    archetype = get_archetype_for_user(segment, stage)
    benchmark_avg = get_benchmark_avg(segment, stage)
    meta = ARCHETYPE_META[archetype]

    user_message = _build_user_message(
        plan=plan,
        company_legal_name=company_legal_name,
        archetype=archetype,
        segment=segment,
        stage=stage,
        spin_answers=spin_answers,
        report_id=report_id,
        benchmark_avg=benchmark_avg,
        meta=meta,
    )

    data: dict[str, Any] | None = None
    last_error: str | None = None
    for attempt in range(CLAUDE_RETRIES):
        try:
            data = await _call_claude(user_message)
            break
        except Exception as e:
            last_error = repr(e)
            logger.warning(
                "checkup_pdf_v3.claude_attempt_failed attempt=%d error=%s",
                attempt + 1,
                last_error,
            )
            if attempt + 1 < CLAUDE_RETRIES:
                await asyncio.sleep(CLAUDE_RETRY_BACKOFF_SECS[attempt])

    if data is None:
        logger.error(
            "checkup_pdf_v3.fallback_used archetype=%s last_error=%s",
            archetype,
            last_error,
        )
        data = build_fallback_data(
            archetype=archetype,
            plan=plan,
            company_legal_name=company_legal_name,
            report_id=report_id,
            benchmark_avg=benchmark_avg,
            answers_count=answers_count,
            meta=meta,
        )

    # Обязательная статика — добавляем независимо от ответа Claude
    data["plan"] = plan
    data.setdefault("report", {})
    data["report"]["plan"] = plan
    data["report"].setdefault("report_id", report_id)
    data["report"].setdefault("answers_count", answers_count)
    data["report"].setdefault("date", datetime.now(timezone.utc).strftime("%d.%m.%Y"))

    _ensure_static_blocks(data, plan=plan)

    # Структурная валидация (если что-то критичное сломано — fallback)
    try:
        CheckupDataSchema(**data)
    except ValidationError as e:
        logger.error(
            "checkup_pdf_v3.schema_invalid archetype=%s errors=%s",
            archetype,
            e.errors()[:3],
        )
        data = build_fallback_data(
            archetype=archetype,
            plan=plan,
            company_legal_name=company_legal_name,
            report_id=report_id,
            benchmark_avg=benchmark_avg,
            answers_count=answers_count,
            meta=meta,
        )
        _ensure_static_blocks(data, plan=plan)

    return data


def render_pdf_html(data: dict[str, Any]) -> str:
    """Рендер шаблона Jinja2. Не вызывает WeasyPrint."""
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    template = Template(template_text)
    return template.render(**data)


def render_pdf_bytes(data: dict[str, Any]) -> bytes:
    """Полный pipeline до WeasyPrint. Возвращает байты PDF."""
    from weasyprint import HTML  # импорт здесь — модуль тяжёлый и опц.

    html_str = render_pdf_html(data)
    return HTML(string=html_str, base_url=str(TEMPLATE_PATH.parent)).write_pdf()


def check_forbidden_words(html: str) -> list[str]:
    """Финальный qa-guard: проверяем что в PDF не просочились маркетинговые
    слова из ТЗ §1.2. Возвращает список найденных нарушений (пустой если OK).
    """
    lowered = html.lower()
    return [w for w in FORBIDDEN_WORDS_IN_PDF if w in lowered]


# ── Claude integration ───────────────────────────────────────────────────────


def _build_user_message(
    *,
    plan: str,
    company_legal_name: str,
    archetype: ArchetypeKey,
    segment: str | None,
    stage: str | None,
    spin_answers: dict[str, str],
    report_id: str,
    benchmark_avg: int,
    meta: dict[str, str],
) -> str:
    lines = [
        f"Архетип: {archetype}",
        f"Сегмент: {segment or 'other'} ({meta['segment_label']})",
        f"Стадия текущая: {stage or 'Команда'} → следующая: {meta['stage_next']}",
        f"Plan: {plan}",
        f"Юр.название клиента: {company_legal_name}",
        f"report_id: {report_id}",
        f"benchmark_avg (для score.benchmark_avg): {benchmark_avg}",
        f"segment_label: {meta['segment_label']}",
        f"segment_label_genitive: {meta['segment_label_genitive']}",
        "",
        "16 ответов клиента на SPIN-вопросы:",
        "",
    ]
    for q in SPIN_QUESTIONS:
        ans = spin_answers.get(q.id) or "(ответ не получен)"
        lines.append(f"### {q.id} — {q.problem}")
        lines.append(ans)
        lines.append("")
    lines.append(
        "Сгенерируй data dict для Jinja2-шаблона edl_chekap_template.html "
        "по контракту. ТОЛЬКО валидный JSON, без preamble и markdown."
    )
    return "\n".join(lines)


async def _call_claude(user_message: str) -> dict[str, Any]:
    """Вызов Claude Haiku 4.5 через тот же клиент, что и LLM dialog.

    Использует proxyapi.ru если задан `ANTHROPIC_BASE_URL`, иначе
    обычный Anthropic endpoint. Возвращает распарсенный JSON.
    """
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

    response = await get_client().messages.create(
        model=settings.anthropic_model,
        max_tokens=CLAUDE_MAX_TOKENS,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_message}],
    )

    text_blocks = [
        b.text for b in response.content if getattr(b, "type", None) == "text"
    ]
    raw = "".join(text_blocks).strip()
    if not raw:
        raise ValueError("Claude returned empty response")
    return _extract_json(raw)


_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*([\s\S]*?)\s*```$", re.MULTILINE)


def _extract_json(text: str) -> dict[str, Any]:
    """Защита от случайного markdown-обрамления вокруг JSON."""
    text = text.strip()
    m = _JSON_FENCE_RE.match(text)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


# ── Гарантия + юр-футер + next_step как dataclass (вставляются после Claude) ─


def _ensure_static_blocks(data: dict[str, Any], *, plan: str) -> None:
    """Добавляет/перезаписывает блоки, которые всегда статичны."""
    data["guarantee"] = {
        "icon_number": "14",
        "title": "14-дневная гарантия возврата",
        "body": [
            "Если в течение 14 календарных дней с момента получения этого отчёта "
            "вы решите, что разбор не дал применимого результата — направьте "
            "команду /refund в боте @edl_os_bot."
        ],
        "conditions": [
            "Гарантия — условная. Возврат оформляется при выполнении ОБОИХ условий одновременно:",
            "(1) ваши ответы в Чекапе соответствуют рубрике качества (минимум слов и хотя бы одна цифра на каждый вопрос);",
            "(2) ни одну из 5 (Base) / 7 (Plus) рекомендаций отчёта вы не можете реализовать в вашей компании.",
            "Возврат денежных средств осуществляется в полном объёме на платёжный инструмент, использованный при оплате, в срок до 3 (трёх) рабочих дней.",
            "Контекст для реалистичности рекомендаций собирается во время самого Чекапа.",
        ],
        "legal_basis": (
            "Гарантия предоставляется в соответствии со ст. 32 Закона РФ "
            "«О защите прав потребителей» с учётом условий применимости, "
            "изложенных выше."
        ),
    }
    data["legal_footer"] = [
        "1. Характер отчёта. Настоящий документ является диагностической "
        "оценкой бизнеса на основе ответов клиента в анкете и индустриальных "
        "бенчмарков. Не является финансовым, налоговым, юридическим или "
        "инвестиционным заключением.",
        "2. Точность оценок. Числовые оценки потерь (₽/мес) рассчитаны по "
        "индустриальным паттернам и имеют характер порядка величины. Точные "
        "цифры по вашему бизнесу могут быть получены только при подключении "
        "к источникам данных — это услуга «Диагностика».",
        "3. Защита персональных данных (152-ФЗ). Данные, переданные клиентом "
        "в бот @edl_os_bot, обрабатываются ИП «Жиганова Екатерина Викторовна» "
        "(ИНН 027507994838) в соответствии с Политикой обработки персональных "
        "данных. Срок хранения PDF-отчёта — 365 календарных дней. Запрос на "
        "удаление — командой /delete_my_data в боте.",
        "4. Авторские права. Методология EDL OS (4 слоя, скоринг, лестница "
        "продуктов) является объектом авторского права. Воспроизведение или "
        "коммерческое использование методологии без письменного согласия не "
        "допускается.",
        "5. Товарный знак. «EDL OS» и «Electric Tangerine» — товарные знаки "
        "в процессе регистрации в Роспатенте.",
    ]
    next_step = data.setdefault("next_step", {})
    next_step.setdefault("ticket_name", "Диагностика")
    next_step.setdefault("ticket_price", "45 000 ₽")
    if plan == "plus":
        next_step.setdefault("coupon_price", "36 000 ₽")
    else:
        next_step.pop("coupon_price", None)
    next_step.setdefault("duration", "2 недели подключения + 90 минут разговора")
    next_step.setdefault("contact_telegram", "@lvanKhudyakov")
    next_step.setdefault("contact_name", "Иван Худяков")
    next_step.setdefault("calendly_url", "elephantdreams.ru/diagnostika")

    # Plus signature — всегда команда EDL OS (требование 21.05.2026)
    if plan == "plus" and isinstance(data.get("personal_comment"), dict):
        data["personal_comment"]["signature_name"] = "Команда EDL OS"


# ── Fallback dataset (генерируется из архетипа без Claude) ───────────────────


def build_fallback_data(
    *,
    archetype: ArchetypeKey,
    plan: str,
    company_legal_name: str,
    report_id: str,
    benchmark_avg: int,
    answers_count: int,
    meta: dict[str, str],
) -> dict[str, Any]:
    """Минимально-валидный data dict из архетипа. Используется когда Claude
    fail'нулся. Структура полная — рендер не падает, но цифры
    обобщённые, а не подобранные по ответам клиента.
    """
    # stage_weights использует ключ 'ops' (короткий) — мапим на наш слой
    stage_weights = get_stage_weights(meta["stage_current"])
    base_scores = {"strategy": 60, "funnel": 55, "operations": 58, "money": 65}
    weight_to_layer = {"strategy": "strategy", "funnel": "funnel", "ops": "operations", "money": "money"}
    total_score = round(
        sum(base_scores[weight_to_layer[wk]] * wv for wk, wv in stage_weights.items())
    )

    layers_payload = [
        {
            "key": "strategy",
            "number": "01",
            "title": "СТРАТЕГИЯ",
            "subtitle": "НАПРАВЛЕНИЕ",
            "score": base_scores["strategy"],
            "diagnosis": (
                "Стратегия есть в голове фаундера, но не переведена в "
                "операционные документы команды. Сегмент клиента описан, "
                "но конкурентная позиция размыта."
            ),
            "metrics": [
                {"name": "Сегмент клиента сформулирован", "value": "Частично", "status": "yellow"},
                {"name": "Ценностное предложение протестировано", "value": "Да", "status": "green"},
                {"name": "Конкурентная позиция дифференцирована", "value": "Размыта", "status": "red"},
                {"name": "Целевые показатели на 12 месяцев", "value": "Частично", "status": "yellow"},
                {"name": "Инициативы привязаны к ресурсам", "value": "Нет", "status": "red"},
            ],
            "connections": [
                {"label": "→ Воронка", "status": "red"},
                {"label": "→ Операционка", "status": "yellow"},
                {"label": "→ Деньги", "status": "yellow"},
            ],
            "key_insight": (
                "Сильная стратегия для себя, слабая стратегия для команды. "
                "Самое дешёвое улучшение — одна страница с ICP, конкурентами "
                "и тремя «не делаем»."
            ),
        },
        {
            "key": "funnel",
            "number": "02",
            "title": "ВОРОНКА",
            "subtitle": "КЛИЕНТЫ",
            "score": base_scores["funnel"],
            "diagnosis": (
                "Верх воронки работает на широкое позиционирование, "
                "низ — на узкий ICP. Несоответствие создаёт нагрузку на отдел "
                "продаж и удлиняет цикл сделки."
            ),
            "metrics": [
                {"name": "Конверсия лид → разговор", "value": "≈22%", "status": "yellow"},
                {"name": "CAC", "value": "≈8 400 ₽", "status": "yellow"},
                {"name": "Цикл сделки", "value": "≈31 день", "status": "red"},
                {"name": "Каналы диверсифицированы", "value": "Да", "status": "green"},
                {"name": "ICP-фильтр на входе", "value": "Нет", "status": "red"},
            ],
            "connections": [
                {"label": "→ Стратегия", "status": "red"},
                {"label": "→ Операционка", "status": "yellow"},
                {"label": "→ Деньги", "status": "yellow"},
            ],
        },
        {
            "key": "operations",
            "number": "03",
            "title": "ОПЕРАЦИОНКА",
            "subtitle": "ПРОЦЕССЫ",
            "score": base_scores["operations"],
            "diagnosis": (
                "Операционка стоит на личном контроле фаундера. На текущем "
                "размере команды это создаёт потолок роста — следующие найма "
                "обнажат это как структурную проблему."
            ),
            "metrics": [
                {"name": "Онбординг формализован", "value": "Нет", "status": "red"},
                {"name": "Ключевые процессы описаны", "value": "Частично", "status": "yellow"},
                {"name": "Регулярная отчётность", "value": "Да", "status": "green"},
                {"name": "Решения по данным", "value": "Частично", "status": "yellow"},
                {"name": "Делегирование без возврата", "value": "≈30%", "status": "red"},
            ],
            "connections": [
                {"label": "→ Стратегия", "status": "yellow"},
                {"label": "→ Воронка", "status": "yellow"},
                {"label": "→ Деньги", "status": "green"},
            ],
        },
        {
            "key": "money",
            "number": "04",
            "title": "ДЕНЬГИ",
            "subtitle": "ФИНАНСЫ",
            "score": base_scores["money"],
            "diagnosis": (
                "Финансы — самый сильный слой. Юнит-экономика положительная, "
                "маржа стабильная. Главный недостаток — скорость отчётности."
            ),
            "metrics": [
                {"name": "P&L в срок (до 5 числа)", "value": "+17 дней", "status": "red"},
                {"name": "Юнит-экономика положительная", "value": "Да", "status": "green"},
                {"name": "Маржа стабильна", "value": "Да", "status": "green"},
                {"name": "Резерв (мес)", "value": "≈2.4", "status": "yellow"},
                {"name": "Бюджет привязан к стратегии", "value": "Частично", "status": "yellow"},
            ],
            "connections": [
                {"label": "→ Стратегия", "status": "yellow"},
                {"label": "→ Воронка", "status": "green"},
                {"label": "→ Операционка", "status": "green"},
            ],
        },
    ]

    cost_breakdown = [
        {
            "source": "Стратегия ↔ Воронка · бюджет на нерелевантные лиды",
            "amount_rub": 184_000,
            "share_pct": 74,
        },
        {
            "source": "Операционка · онбординг без системы",
            "amount_rub": 42_000,
            "share_pct": 17,
        },
        {
            "source": "Деньги ↔ Стратегия · решения на устаревших данных",
            "amount_rub": 21_000,
            "share_pct": 9,
        },
    ]
    total_leak = sum(item["amount_rub"] for item in cost_breakdown)

    recommendations_full = [
        {
            "priority": 1,
            "layer_label": "СТРАТЕГИЯ",
            "horizon_days": 7,
            "title": "Зафиксировать одно определение ICP на полстраницы и передать в маркетинг",
            "description": (
                "Сядьте на 90 минут и напишите ICP в формате: возраст / контекст / "
                "триггер / 3 «не наш клиент». Передайте маркетингу и проверьте, "
                "что следующая партия креативов написана под этот документ."
            ),
            "expected_impact": "Снижение расхода на нерелевантные лиды на 12–18% за 30 дней",
        },
        {
            "priority": 2,
            "layer_label": "ОПЕРАЦИОНКА",
            "horizon_days": 14,
            "title": "Написать onboarding-checklist для новых сотрудников на 1 страницу",
            "description": (
                "Простой список: что нужно знать к концу 1-го дня, 1-й недели, "
                "1-го месяца. Снимает до 4 часов времени фаундера с каждого "
                "нового найма."
            ),
            "expected_impact": "Освободит ~12 часов фаундера за следующие 3 найма",
        },
        {
            "priority": 3,
            "layer_label": "ДЕНЬГИ",
            "horizon_days": 21,
            "title": "Сократить срок закрытия P&L до 7 дней",
            "description": (
                "Договориться с бухгалтером на промежуточный отчёт к 7 числу "
                "без сверки до копейки. Это даёт решения по бюджету следующего "
                "месяца на актуальных данных."
            ),
            "expected_impact": "Маркетинговый бюджет на свежих данных, не устаревших",
        },
        {
            "priority": 4,
            "layer_label": "СТРАТЕГИЯ",
            "horizon_days": 30,
            "title": "Провести 60-минутную сверку команды с визией",
            "description": (
                "Собрать ключевых сотрудников и попросить каждого письменно "
                "ответить на вопрос «куда мы ведём бизнес в горизонте 24 месяцев». "
                "Сравнить ответы. Зафиксировать одну формулировку."
            ),
            "expected_impact": "Совпадение версий команды с вашей — основа делегирования",
        },
        {
            "priority": 5,
            "layer_label": "ВОРОНКА",
            "horizon_days": 30,
            "title": "Внедрить ICP-фильтр на этапе заявки, до отдела продаж",
            "description": (
                "2–3 простых вопроса в форме заявки, по которым автоматически "
                "отсеиваются явные нецелевые лиды."
            ),
            "expected_impact": "Рост конверсии лид → разговор на 5–8 п.п.",
        },
        {
            "priority": 6,
            "layer_label": "ОПЕРАЦИОНКА",
            "horizon_days": 30,
            "title": "Делегировать 3 типа решений без возврата к фаундеру",
            "description": (
                "Выберите 3 типа решений, которые сейчас проходят через вас. "
                "Опишите критерии. Передайте конкретному человеку. Проверьте "
                "через 4 недели, что не возвращаются."
            ),
            "expected_impact": "Снижение нагрузки фаундера на 4–6 часов в неделю",
        },
        {
            "priority": 7,
            "layer_label": "ДЕНЬГИ",
            "horizon_days": 30,
            "title": "Завести юнит-экономику по каждому продукту отдельно",
            "description": (
                "Не общую маржу, а маржу по каждому продукту/направлению. "
                "Вскроет, какой продукт тянет портфель, какой убыточен."
            ),
            "expected_impact": "Решение о приоритизации продуктов на основе данных",
        },
    ]
    recommendations = recommendations_full[: (7 if plan == "plus" else 5)]

    executive_summary = [
        {
            "eyebrow": "СВЯЗЬ 01 → 02 · СТРАТЕГИЯ → ВОРОНКА",
            "title": "Стратегия задаёт узкий ICP — Воронка работает на широкий",
            "layer_impact": "Слой Стратегия ослабляет слой Воронка",
            "description": (
                "ICP в стратегии не доходит до маркетинговых креативов. "
                "Маркетинг привлекает широкую аудиторию, отдел продаж "
                "теряет нерелевантных лидов после первых касаний."
            ),
            "money_impact_rub": 184_000,
        },
        {
            "eyebrow": "СВЯЗЬ 03 → 02 · ОПЕРАЦИОНКА ↔ ВОРОНКА",
            "title": "Команда растёт быстрее, чем процессы",
            "layer_impact": "Слой Операционка не подкрепляет слой Воронка",
            "description": (
                "Онбординг новых сотрудников не формализован. Информация о "
                "клиенте из воронки не доходит до продуктовой команды."
            ),
            "money_impact_rub": 42_000,
        },
        {
            "eyebrow": "СВЯЗЬ 04 → 01 · ДЕНЬГИ → СТРАТЕГИЯ",
            "title": "Финансовая отчётность не возвращается в стратегию",
            "layer_impact": "Слой Деньги не возвращает сигнал в Стратегию",
            "description": (
                "P&L закрывается с опозданием. Стратегические решения о "
                "бюджете принимаются без точной маржи по предыдущим "
                "продуктам."
            ),
            "money_impact_rub": 21_000,
        },
    ]
    if plan == "plus":
        executive_summary.append({
            "eyebrow": "ФАУНДЕР · ВИЖНАР",
            "title": "Видение сформулировано, но команда читает его иначе",
            "layer_impact": "Слой Фаундер слабо транслируется в Слой Операционка",
            "description": (
                "Из ключевых сотрудников 0 формулируют миссию словами, "
                "близкими к вашей версии. Это значит, что 60% операционных "
                "решений принимаются на личных версиях видения."
            ),
            "money_impact_rub": None,
        })

    data: dict[str, Any] = {
        "plan": plan,
        "company": {
            "legal_name": company_legal_name,
            "segment_label": meta["segment_label"],
            "segment_label_genitive": meta["segment_label_genitive"],
            "stage_current": meta["stage_current"],
            "stage_next": meta["stage_next"],
        },
        "report": {
            "plan": plan,
            "date": datetime.now(timezone.utc).strftime("%d.%m.%Y"),
            "report_id": report_id,
            "answers_count": answers_count,
        },
        "score": {
            "total": total_score,
            "benchmark_avg": benchmark_avg,
            "delta_vs_benchmark_pct": round(
                (total_score - benchmark_avg) / benchmark_avg * 100
            )
            if benchmark_avg
            else 0,
            "stage_readiness_pct": min(100, max(0, total_score)),
        },
        "executive_summary": executive_summary,
        "founder_vision": {
            "score": 70,
            "status_badge": "yellow",
            "title": "Видение есть, но команда читает его иначе",
            "diagnosis": (
                "Вы видите бизнес как конкретный продукт для конкретного "
                "сегмента. При опросе команда формулирует миссию по-разному. "
                "Это значит, что часть операционных решений принимается на "
                "личных версиях видения, а не на вашей."
            ),
            "observations": [
                "Долгосрочная цель зафиксирована, но не транслируется в "
                "квартальные цели команды.",
                "Решения о новых продуктах принимаются без проверки на "
                "соответствие визии.",
                "Регулярного «момента сверки» команды с визией нет.",
                "Это работает на текущем масштабе, но станет узким местом "
                "после 15+ человек.",
            ],
        },
        "layers": layers_payload,
        "connections_analysis": {
            "edges": {
                "founder_to_strategy": "yellow",
                "founder_to_funnel": "red",
                "founder_to_ops": "yellow",
                "founder_to_money": "green",
                "strategy_to_funnel": "red",
                "strategy_to_ops": "yellow",
                "strategy_to_money": "yellow",
                "funnel_to_ops": "yellow",
                "funnel_to_money": "green",
                "ops_to_money": "green",
            },
            "critical_list": [
                {
                    "label": "Стратегия → Воронка",
                    "description": (
                        "ICP не доходит до настройки маркетинга. Команда "
                        "привлекает широкую аудиторию. Это создаёт нагрузку "
                        "на отдел продаж и удлиняет цикл сделки."
                    ),
                    "money_impact_rub": 184_000,
                },
                {
                    "label": "Воронка → Операционка",
                    "description": (
                        "Информация о клиенте, собранная в воронке, не "
                        "передаётся в продукт."
                    ),
                    "money_impact_rub": 42_000,
                },
                {
                    "label": "Деньги → Стратегия",
                    "description": (
                        "Финансовые результаты по продуктам не возвращаются "
                        "в стратегию."
                    ),
                    "money_impact_rub": 21_000,
                },
            ],
        },
        "cost_analysis": {
            "total_monthly_leak_rub": total_leak,
            "annual_leak_rub": total_leak * 12,
            "breakdown": cost_breakdown,
        },
        "recommendations": recommendations,
    }

    if plan == "plus":
        data["deep_dive_layer"] = {
            "title": "Воронка под микроскопом: где живут устранимые потери",
            "lede": (
                "Воронка — слой с самым низким Score. Разберём, почему "
                "именно — и где в ней утечка, которая стоит вам устранимых "
                "сумм в ₽/мес."
            ),
            "sections": [
                {
                    "heading": "Симптом: длинный цикл сделки",
                    "body": (
                        "Цикл сделки примерно в 2 раза дольше верхнего "
                        "квартиля сегмента. Внутри — большой кусок «тишины», "
                        "когда лид не двигается. Это главная зона улучшений."
                    ),
                },
                {
                    "heading": "Причина: ICP не доходит до маркетинга",
                    "body": (
                        "В стратегии описан узкий сегмент. В рекламных "
                        "креативах — широкое позиционирование. В лендинге — "
                        "ещё шире. Это три разных адресата."
                    ),
                },
                {
                    "heading": "Что чинит это в практике",
                    "body": (
                        "Документ-мост на 1 страницу: ICP, value prop, "
                        "anti-ICP. Закрепить как часть договора с маркетингом."
                    ),
                },
            ],
            "data_points": [
                {"value": "~31", "label": "ДНЕЙ цикл сделки", "meta": "Верхний квартиль: 12–14 дней"},
                {"value": "~22%", "label": "конверсия лид → разговор", "meta": "Средний по сегменту: 28%"},
                {"value": "~8 400 ₽", "label": "CAC текущий", "meta": "Цель квартала: 6 500 ₽"},
            ],
        }
        data["deep_dive_connection"] = {
            "title": "Связь Стратегия → Воронка: где именно она рвётся",
            "lede": (
                "Это самая дорогая разорванная связь в системе. Большая "
                "часть устранимых потерь идёт именно через неё."
            ),
            "what_transfers": (
                "По этой связи должно передаваться три вещи: (1) ICP — кому "
                "продаём, (2) ценностное предложение — что мы для них делаем "
                "уникального, (3) anti-ICP — кого мы отсеиваем сразу."
            ),
            "where_lost": (
                "Между формулировкой стратегии и формулировкой брифа "
                "маркетингу. Конкретность теряется уже на первом шаге."
            ),
            "cost_explanation": (
                "При текущем маркетинговом бюджете часть лидов не "
                "соответствует ICP. Эти лиды доходят до отдела продаж и "
                "впитывают ресурсы наравне с целевыми до момента отсева."
            ),
            "alternatives": {
                "intro": (
                    "Этот разрыв чинят тремя путями. Выбор зависит от того, "
                    "какой ресурс у вас в дефиците: время, деньги или "
                    "экспертиза."
                ),
                "path_1_own": {
                    "name": "СВОИМИ СИЛАМИ",
                    "what_to_do": (
                        "Написать документ-мост на 1 страницу — ICP, value "
                        "prop, anti-ICP в той форме, в которой их можно "
                        "скопировать в бриф подрядчику."
                    ),
                    "founder_time_hours": "4–6 часов",
                    "cost_rub": "0 ₽",
                    "time_to_result": "2–4 недели",
                },
                "path_2_hiring": {
                    "name": "НАЁМ СПЕЦИАЛИСТА",
                    "what_to_do": (
                        "Пригласить маркетингового стратега уровня middle+ "
                        "на проект 4–6 недель. Брифинг → research конкурентов "
                        "→ ICP в формате jobs-to-be-done."
                    ),
                    "founder_time_hours": "6–8 часов",
                    "cost_rub": "80–180к ₽ за проект",
                    "time_to_result": "4–6 недель",
                },
                "path_3_agents": {
                    "name": "ЧЕРЕЗ НАШИХ AI-АГЕНТОВ НА СПРИНТЕ",
                    "what_to_do": (
                        "Настраиваем агента, который читает ваши ответы "
                        "клиентам в CRM, формулирует ICP в трёх форматах и "
                        "проверяет соответствие каждого нового креатива."
                    ),
                    "founder_time_hours": "3–4 часа",
                    "cost_rub": "входит в Спринт 250–480к ₽",
                    "time_to_result": "2 недели от старта Спринта",
                },
                "outro": (
                    "Какой путь выбрать — зависит от вашего ограничения: "
                    "если в дефиците время, путь 2 или 3; если деньги — "
                    "путь 1; если важна повторяемость и масштабирование — "
                    "путь 3."
                ),
            },
        }
        data["extended_benchmark"] = {
            "comparison": [
                {"metric": "Score общий", "you": str(total_score), "avg": str(benchmark_avg), "top_quartile": str(min(100, benchmark_avg + 20)), "gap_label": f"{total_score - (benchmark_avg + 20):+d}"},
                {"metric": "Конверсия лид → разговор", "you": "22%", "avg": "28%", "top_quartile": "34%", "gap_label": "−12 п.п."},
                {"metric": "Цикл сделки (дни)", "you": "31", "avg": "21", "top_quartile": "13", "gap_label": "+18 дн."},
                {"metric": "CAC (₽)", "you": "8 400", "avg": "7 200", "top_quartile": "5 400", "gap_label": "+3 000"},
                {"metric": "Срок закрытия P&L (дни)", "you": "22", "avg": "12", "top_quartile": "5", "gap_label": "+17 дн."},
                {"metric": "Делегирование без возврата", "you": "30%", "avg": "55%", "top_quartile": "78%", "gap_label": "−48 п.п."},
            ],
            "sources": [
                "Открытые бенчмарки EdTech RU, Q1 2026.",
                "Smart Ranking «Топ-100 EdTech компаний России 2025», публичная часть отчёта.",
                "Внутренние данные EDL OS по выборке клиентов на стадиях Команда / Структура.",
            ],
        }
        data["personal_comment"] = {
            "title": "Что мы увидели персонально в вашем кейсе",
            "intro_text": (
                "В 15-минутном видеоразборе команда EDL OS разбирает три "
                "вещи, которые в этот отчёт не вместились. Что бы мы "
                "сделали на вашем месте в первую неделю — с учётом стадии "
                "и сегмента. Какой из пунктов рекомендаций считаем самым "
                "недооценённым. На что обратить внимание, если решите "
                "идти самостоятельно."
            ),
            "quote": (
                "Мы смотрим в ваши данные глазами команды, выстраивавшей "
                "корпоративный операционный слой в нескольких быстрорастущих "
                "компаниях. Те разрывы, которые видим у вас — мы видели "
                "и в других. Половина решений — это вопросы дисциплины, "
                "не системы."
            ),
            "video_url": "edl.os/video/{}".format(report_id),
            "signature_name": "Команда EDL OS",
        }

    return data
