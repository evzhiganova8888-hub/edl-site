"""PDF v2 — rule-based генератор клиентского отчёта Чекапа.

Итерация 1 (до 21.05.2026): без LLM. Категориальные шаблоны рекомендаций
+ извлечение упомянутых клиентом инструментов и размера команды +
персонализация 3 сценариев под priority_metrics.

Итерация 2 (до 25.05.2026): подменим diagnosis_text + recommendations +
scenarios на LLM-output (через JSON-schema), сохранив этот rule-based слой
как fallback при сбое LLM.

Структура итогового HTML:
- Cover (заголовок, компания, дата, тариф)
- Executive Summary (1 стр)
- Диагноз по 4 слоям: «Что сильно / Где разрыв / Риск 90 дней»
- 5 (Base) / 7 (Plus) рекомендаций — карточки с обязательными полями
- 3 сценария (Sniper / Combo / Full Stack) на основе priority_metrics
- НДС-флажок (если релевантно)
- Disclaimer (только Plus): отличие от Диагностики
- Upsell-страница: «Что входит в Диагностику, чего нет здесь»
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.core.checkup_questions import by_key, determine_vat_zone
from src.core.config import settings
from src.db.models import Application, CheckupAnswer, User


_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


# ─── Размер команды → роль ────────────────────────────────────────────────────


_TEAM_SIZE_RE = re.compile(
    r"(?:команда|сотрудник|штат|людей|человек|чел\.?)[^\d]{0,15}(\d{1,3})|"
    r"(\d{1,3})\s*(?:сотрудник|человек|чел\.?|людей|в\s+команде)",
    re.IGNORECASE,
)


def detect_team_size(answers: Iterable[CheckupAnswer]) -> int | None:
    """Парсит размер команды из ответа на s1_horizon (или любой текст)."""
    for a in answers:
        if a.question_key != "s1_horizon":
            continue
        m = _TEAM_SIZE_RE.search(a.text or "")
        if m:
            try:
                size = int(m.group(1) or m.group(2))
                if 1 <= size <= 5000:
                    return size
            except (TypeError, ValueError):
                continue
    return None


def role_for_layer(layer: str, team_size: int | None) -> str:
    """Подбирает роль ответственного по слою и размеру команды.

    < 10 чел  → собственник тащит сам, помощник по фин.
    10–25     → отдельные руководители направлений
    25–50     → C-level
    """
    if team_size is None:
        return {
            "strategy": "Собственник",
            "sales": "Руководитель продаж",
            "operations": "Руководитель операционки",
            "finance": "Внешний CFO / финдиректор",
        }.get(layer, "Собственник")

    if team_size < 10:
        return {
            "strategy": "Собственник (вы лично)",
            "sales": "Собственник + первый sales-помощник",
            "operations": "Собственник + операционный ассистент",
            "finance": "Собственник + бухгалтер на аутсорсе",
        }.get(layer, "Собственник")

    if team_size < 25:
        return {
            "strategy": "Собственник",
            "sales": "Head of Sales (или старший менеджер)",
            "operations": "Operations lead / COO-функция",
            "finance": "Финансовый менеджер / внешний CFO",
        }.get(layer, "Собственник")

    return {
        "strategy": "CEO / собственник",
        "sales": "CRO / Head of Sales",
        "operations": "COO",
        "finance": "CFO",
    }.get(layer, "CEO")


# ─── Извлечение инструментов клиента ──────────────────────────────────────────


_KNOWN_TOOLS = {
    # CRM
    "amocrm": "amoCRM",
    "amo crm": "amoCRM",
    "amo-crm": "amoCRM",
    "битрикс": "Битрикс24",
    "bitrix": "Битрикс24",
    "hubspot": "HubSpot",
    "pipedrive": "Pipedrive",
    "salesforce": "Salesforce",
    # Учётка / финансы
    "1с": "1С",
    "1c": "1С",
    "контур": "Контур",
    "моёдело": "Моё дело",
    "мое дело": "Моё дело",
    "точка": "Точка-банк",
    "тинькоф": "Т-Банк (Тинькофф)",
    "тинькофф": "Т-Банк (Тинькофф)",
    "сбер": "СберБанк",
    # EdTech / геткурс
    "геткурс": "GetCourse",
    "getcourse": "GetCourse",
    # Документация / задачи
    "notion": "Notion",
    "ноушн": "Notion",
    "trello": "Trello",
    "jira": "Jira",
    "asana": "Asana",
    "monday": "Monday",
    "yougile": "YouGile",
    "weeek": "Weeek",
    # Календари / связь
    "calendly": "Calendly",
    "zoom": "Zoom",
    "google meet": "Google Meet",
    "telegram": "Telegram",
    # Аналитика / трекинг часов
    "toggl": "Toggl",
    "amplitude": "Amplitude",
    "yandex metrica": "Яндекс.Метрика",
    "яндекс метрика": "Яндекс.Метрика",
    "google analytics": "Google Analytics",
    # Маркетинг
    "apollo": "Apollo",
    "linkedin": "LinkedIn",
    "yandex direct": "Яндекс.Директ",
    "яндекс директ": "Яндекс.Директ",
}


def detect_tools(answers: Iterable[CheckupAnswer]) -> dict[str, list[str]]:
    """Возвращает упомянутые клиентом инструменты, сгруппированные по слою."""
    by_layer: dict[str, list[str]] = {
        "strategy": [], "sales": [], "operations": [], "finance": []
    }
    seen_global: set[str] = set()
    for a in answers:
        text = (a.text or "").lower()
        for key, display in _KNOWN_TOOLS.items():
            if key in text and display not in seen_global:
                # Привязка к слою: где упомянули — там и копим
                by_layer.setdefault(a.layer, []).append(display)
                seen_global.add(display)
    return by_layer


def all_tools(tools_by_layer: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    for vals in tools_by_layer.values():
        out.extend(vals)
    return out


# ─── Категориальные рекомендации ──────────────────────────────────────────────


# Каждый шаблон содержит slot'ы, заполняемые из контекста клиента:
# {tool}, {role}, {team_size}, {revenue_hint}
RECOMMENDATIONS: list[dict] = [
    {
        "key": "strategy_bets_in_writing",
        "layer": "strategy",
        "title": "Зафиксируйте 3 ставки года в одном документе",
        "what": (
            "Сейчас стратегия живёт в голове и в обсуждениях. Соберите 3 главные "
            "ставки года, каждую — с метрикой успеха и горизонтом. Это превратит "
            "стратегию в недельные решения, а не в годовой документ."
        ),
        "tool_default": "Notion (страница «Three bets {year}»)",
        "first_step": (
            "В течение недели — записать 3 ставки в одну страницу. Каждая ставка: "
            "цель → метрика → срок → кто отвечает."
        ),
        "impact": "Снимает риск «движение есть, вектор размылся» к 90 дням.",
    },
    {
        "key": "strategy_not_doing_list",
        "layer": "strategy",
        "title": "Соберите список «что мы НЕ делаем в этом году»",
        "what": (
            "Без явных «не-целей» команда тихо разрастается в сторону: появляются "
            "проекты, на которые никто формально не подписывался. Список из 5+ "
            "пунктов с обоснованием закрывает эту дыру."
        ),
        "tool_default": "Notion (или приложить к Three bets)",
        "first_step": (
            "Сегодня — выписать 5 искушений: новые рынки/сегменты/услуги, на которые "
            "не идём. Рядом — почему."
        ),
        "impact": "Защищает фокус от размывания. Освобождает 15–25% времени основателя.",
    },
    {
        "key": "sales_funnel_in_system",
        "layer": "sales",
        "title": "Перенесите воронку в CRM, если она ещё в голове/таблицах",
        "what": (
            "Воронка в голове = воронки нет. Нужен инструмент, в котором каждый "
            "лид имеет owner'а, этап и регулярный апдейт. Без этого решения по "
            "росту принимаются по интуиции."
        ),
        "tool_default": "amoCRM / Битрикс24 / HubSpot (выбор по бюджету и интеграциям)",
        "first_step": (
            "На этой неделе — выбрать CRM и завести 10 текущих сделок руками. "
            "Регулярный pipeline-обзор раз в неделю."
        ),
        "impact": (
            "Снимает риск потерянных сделок и даёт базу для расчёта конверсии "
            "и CAC по каналам."
        ),
    },
    {
        "key": "sales_top_segment",
        "layer": "sales",
        "title": "Назначьте ICP-сегмент №1 и сфокусируйте маркетинг",
        "what": (
            "Когда лиды идут изо всех сегментов, средняя конверсия маскирует, "
            "что один сегмент даёт LTV/CAC × 3, а другой — × 0.5. Зафиксируйте "
            "топ-сегмент и сфокусируйте контент/каналы."
        ),
        "tool_default": "1 страница ICP в Notion + лейбл в CRM",
        "first_step": (
            "Возьмите 10 последних закрытых сделок, выпишите общие признаки топ-3 "
            "клиентов по марже. Это и есть ICP."
        ),
        "impact": "Поднимает средний LTV/CAC за счёт переориентации каналов.",
    },
    {
        "key": "operations_ceo_unblock",
        "layer": "operations",
        "title": "Снимите собственника с операционных bottleneck'ов",
        "what": (
            "Если на собственнике висят {hint}часть операционных решений — компания "
            "не вырастет шире его лимита. Соберите 3 главных места, где «без меня "
            "не работает», и распишите план передачи."
        ),
        "tool_default": "Шаблон «передачи функции» — Notion + Loom-видео для команды",
        "first_step": (
            "Сегодня — выписать 3 функции, где вы единственный носитель экспертизы. "
            "На неделю — один loom-видео-объясн на каждую."
        ),
        "impact": "Освобождает 10–20 часов в месяц собственника на стратегию.",
    },
    {
        "key": "operations_margin_per_project",
        "layer": "operations",
        "title": "Внедрите маржу-по-проектам, не только среднюю",
        "what": (
            "Среднее по портфелю врёт. Должна быть таблица 3 главных проектов: "
            "выручка / прямые косты / маржа % / часы команды. Без этого решения "
            "о ценах и фокусе делаются по ощущениям."
        ),
        "tool_default": "Google Sheets / 1С (если уже подключено) + Toggl для часов",
        "first_step": (
            "На этой неделе — заполнить таблицу для 3 проектов за прошлый месяц. "
            "Раз в неделю — обновление."
        ),
        "impact": "Видны минусовые проекты, которые можно закрыть/пересогласовать.",
    },
    {
        "key": "finance_cash_90d",
        "layer": "finance",
        "title": "Считайте cash на 90 дней вперёд раз в неделю",
        "what": (
            "Cash-flow ≥90 дней — базовая страховка собственника. Без него "
            "финансовые решения сводятся к «есть ли деньги сегодня». Нужна "
            "простая модель: остаток + поступления + платежи = прогноз."
        ),
        "tool_default": "Google Sheets (1 файл, обновляется в понедельник 9:00)",
        "first_step": (
            "Сегодня — собрать шаблон cash-flow на 13 недель. Раз в неделю — "
            "сверка с банком."
        ),
        "impact": "Снимает риск кассового разрыва. База для решений по найму и инвестициям.",
    },
    {
        "key": "finance_vat_2026",
        "layer": "finance",
        "title": "Зафиксируйте сценарий по НДС-2026 до конца II квартала",
        "what": (
            "Переходное окно на УСН с НДС / ОСНО решается один раз и влияет на цены "
            "весь следующий год. Откладывать = терять переговорную силу с клиентами "
            "и подрядчиками."
        ),
        "tool_default": "Консультация с бухгалтером + 1 страница «наш сценарий» в Notion",
        "first_step": (
            "На этой неделе — встреча с бухгалтером, выбрать ставку (5% без вычетов "
            "или 20% с вычетами) на основе текущих расходов."
        ),
        "impact": "Закрывает критический риск 2026 года, даёт основу для пересмотра цен.",
    },
]


def select_recommendations(
    plan: str,
    answers: list[CheckupAnswer],
    tools_by_layer: dict[str, list[str]],
    team_size: int | None,
) -> list[dict]:
    """Выбирает 5 (Base) / 7 (Plus) рекомендаций.

    Простая логика приоритизации: сначала по слоям, где quality_passed=False
    или where text='[пропущено]' (там пробелы), потом по умолчанию.
    """
    limit = 7 if plan == "plus" else 5
    # Считаем «слабость» слоя по доле непройденных
    weakness: dict[str, int] = {"strategy": 0, "sales": 0, "operations": 0, "finance": 0}
    for a in answers:
        if not a.quality_passed or a.text == "[пропущено]":
            weakness[a.layer] = weakness.get(a.layer, 0) + 1

    def score(rec: dict) -> int:
        return -weakness.get(rec["layer"], 0)

    sorted_recs = sorted(RECOMMENDATIONS, key=score)
    out: list[dict] = []
    for rec in sorted_recs[:limit]:
        layer = rec["layer"]
        client_tools = tools_by_layer.get(layer, [])
        tool = (
            ", ".join(client_tools)
            if client_tools
            else rec["tool_default"]
        )
        # «у вас на основателе висит большая часть» — для context-hint
        hint = ""
        if team_size and team_size < 10 and rec["key"] == "operations_ceo_unblock":
            hint = "(при команде <10 — почти все) "
        out.append({
            "title": rec["title"],
            "layer": layer,
            "layer_label": _LAYER_LABELS[layer],
            "what": rec["what"].format(hint=hint),
            "tool": tool,
            "role": role_for_layer(layer, team_size),
            "first_step": rec["first_step"],
            "impact": rec["impact"],
        })
    return out


_LAYER_LABELS = {
    "strategy": "Стратегия",
    "sales": "Воронка",
    "operations": "Операционка",
    "finance": "Деньги",
    # v2: новые коды (TZ_checkup_plus_v2.md §3.2)
    "01": "Стратегия",
    "02": "Воронка",
    "03": "Операционка",
    "04": "Деньги",
}

# Маппинг новых кодов в старые для backward-compat в шаблоне/логике
_LAYER_V2_TO_V1 = {"01": "strategy", "02": "sales", "03": "operations", "04": "finance"}


def _canonical_layer(code: str | None) -> str:
    """Приводит код слоя к old-style (strategy/sales/operations/finance)."""
    if code in _LAYER_V2_TO_V1:
        return _LAYER_V2_TO_V1[code]
    return code or "strategy"


# ─── Диагноз по 4 слоям ───────────────────────────────────────────────────────


_DIAGNOSIS_TEMPLATES = {
    "strategy": {
        "strong_marker": "ставк",  # упоминание ставок в s2_bets
        "strong": (
            "Видно, что вы умеете называть конкретные ставки и держать горизонт. "
            "Это основа: команда понимает, куда мы идём."
        ),
        "weak": (
            "Стратегия пока живёт в голове или в формате «всё важно». Команда "
            "видит движение, но не вектор."
        ),
        "gap": (
            "Главный разрыв: ставки не превращены в недельные решения и "
            "не имеют явной метрики успеха."
        ),
        "risk_90d": (
            "За 90 дней без этого: вы потратите квартал на тушение пожаров и "
            "обнаружите в конце, что 1–2 ставки фактически «не сдвинулись» — "
            "никто не вёл их еженедельно."
        ),
    },
    "sales": {
        "strong_marker": "crm",
        "strong": (
            "Воронка живёт в инструменте, конверсии измеряются, есть понимание "
            "сегментов. Это решает 50% сейлз-задач."
        ),
        "weak": (
            "Воронка пока в голове / в Excel / в Telegram-чате. Решения «куда "
            "вложить маркетинг» принимаются по ощущениям, а не по данным."
        ),
        "gap": (
            "Главный разрыв: нет регулярной сверки конверсий по этапам и нет "
            "ICP-фокуса — лиды идут изо всех сегментов одинаково."
        ),
        "risk_90d": (
            "За 90 дней без этого: бюджет маркетинга уйдёт ровным слоем по "
            "каналам, без понимания, какой действительно даёт LTV/CAC > 3."
        ),
    },
    "operations": {
        "strong_marker": "playbook",
        "strong": (
            "Операционка частично передана: есть playbook'и, есть owner'ы "
            "ключевых функций, регулярные синки."
        ),
        "weak": (
            "Большая часть операционки — на собственнике. Это потолок роста: "
            "компания не вырастет шире лимита внимания CEO."
        ),
        "gap": (
            "Главный разрыв: нет таблицы маржи-по-проектам и нет 1–2 главных "
            "функций, которые можно передать на этом квартале."
        ),
        "risk_90d": (
            "За 90 дней без этого: один-два минусовых проекта продолжат тянуть "
            "маржу, и вы потратите кварт на «спасение клиента», вместо роста."
        ),
    },
    "finance": {
        "strong_marker": "ebitda",
        "strong": (
            "Финансы под контролем: EBITDA считается, cash-планирование есть, "
            "налоговый режим выбран осознанно."
        ),
        "weak": (
            "Финансовые решения принимаются по остатку на счёте «сегодня». "
            "Cash-flow на 90 дней и EBITDA — нерегулярные понятия."
        ),
        "gap": (
            "Главный разрыв: нет недельной сверки cash на 13 недель вперёд "
            "и не зафиксирован сценарий по НДС-2026."
        ),
        "risk_90d": (
            "За 90 дней без этого: риск кассового разрыва в Q3 (особенно если "
            "затянутся 1–2 крупных платежа) + не успеете обновить договоры "
            "под новый налоговый режим к 1.01.2027."
        ),
    },
}


def diagnose_layer(layer: str, answers: list[CheckupAnswer]) -> dict:
    """Простая rule-based диагностика слоя."""
    tpl = _DIAGNOSIS_TEMPLATES[layer]
    layer_answers = [a for a in answers if a.layer == layer]
    is_strong = any(
        tpl["strong_marker"].lower() in (a.text or "").lower()
        and a.quality_passed
        for a in layer_answers
    )
    return {
        "label": _LAYER_LABELS[layer],
        "strong": tpl["strong"] if is_strong else tpl["weak"],
        "gap": tpl["gap"],
        "risk_90d": tpl["risk_90d"],
        "quality_passed": sum(1 for a in layer_answers if a.quality_passed),
        "quality_total": len(layer_answers),
    }


# ─── 3 сценария ───────────────────────────────────────────────────────────────


def build_scenarios(
    priority_metrics: list[str],
    recommendations: list[dict],
) -> dict:
    """Sniper / Combo / Full Stack.

    Метрики берутся из ответа клиента на 21-й вопрос. Если не назвал —
    используем «продажи», «маржа», «cash» как дефолт.
    """
    metrics = priority_metrics or ["ключевая метрика", "вторая метрика", "третья метрика"]
    m1 = metrics[0] if len(metrics) >= 1 else "ключевая метрика"
    m2 = metrics[1] if len(metrics) >= 2 else "вторая метрика"
    m3 = metrics[2] if len(metrics) >= 3 else "третья метрика"

    # Sniper: одна сильнейшая рекомендация
    sniper_rec = recommendations[0] if recommendations else None
    # Combo: 3 рекомендации
    combo_recs = recommendations[:3]
    # Full Stack: до 8 рекомендаций + добивка из остальных по слоям
    full_recs = recommendations[:7] if len(recommendations) >= 7 else recommendations
    # Чтобы строго 8 — добавляем «общую» рекомендацию по 4-му слою, если 7
    fillers = [
        {"layer": "strategy", "action": "Еженедельный 30-мин стратег-обзор в одиночку"},
        {"layer": "sales", "action": "Pipeline-обзор раз в неделю с CRM на экране"},
        {"layer": "operations", "action": "Loom-видео-объясн на 1 функцию в неделю"},
        {"layer": "finance", "action": "Cash-flow на 13 недель — обновление в понедельник"},
    ]
    full_actions_by_layer: dict[str, list[str]] = {
        "strategy": [], "sales": [], "operations": [], "finance": []
    }
    for r in full_recs:
        full_actions_by_layer[r["layer"]].append(r["title"])
    # Добиваем до 8, чтобы было ≥1 на каждый слой
    for f in fillers:
        if not full_actions_by_layer[f["layer"]]:
            full_actions_by_layer[f["layer"]].append(f["action"])
    # Считаем общее
    total_actions = sum(len(v) for v in full_actions_by_layer.values())
    # Если ещё меньше 8, добавляем недостающие из fillers по очереди
    if total_actions < 8:
        for f in fillers:
            if total_actions >= 8:
                break
            if f["action"] not in full_actions_by_layer[f["layer"]]:
                full_actions_by_layer[f["layer"]].append(f["action"])
                total_actions += 1

    return {
        "sniper": {
            "metric": m1,
            "action": sniper_rec["title"] if sniper_rec else "—",
            "first_step": sniper_rec["first_step"] if sniper_rec else "—",
            "impact": sniper_rec["impact"] if sniper_rec else "—",
            "horizon_weeks": 4,
        },
        "combo": {
            "metrics": [m1, m2],
            "actions": [r["title"] for r in combo_recs],
            "horizon_weeks": 8,
        },
        "full_stack": {
            "metrics": [m1, m2, m3],
            "actions_by_layer": {
                _LAYER_LABELS[k]: v for k, v in full_actions_by_layer.items()
            },
            "total_actions": sum(len(v) for v in full_actions_by_layer.values()),
            "horizon_weeks": 12,
        },
    }


# ─── Executive summary (rule-based) ───────────────────────────────────────────


def executive_summary(
    answers: list[CheckupAnswer],
    layer_diagnosis: list[dict],
    recommendations: list[dict],
) -> str:
    """3-4 предложения: главная боль + диагноз + ключевая рекомендация."""
    # Узкое место в воронке
    bottleneck_sales = next(
        (a for a in answers if a.question_key == "f5_bottleneck"), None
    )
    bottleneck_ops = next(
        (a for a in answers if a.question_key == "o3_bottleneck"), None
    )
    pain_lines: list[str] = []
    if bottleneck_sales and bottleneck_sales.quality_passed:
        pain_lines.append(
            f"В воронке вы сами обозначили узкое место: «{_clip(bottleneck_sales.text, 140)}»."
        )
    if bottleneck_ops and bottleneck_ops.quality_passed:
        pain_lines.append(
            f"В операционке: «{_clip(bottleneck_ops.text, 140)}»."
        )
    pain_block = " ".join(pain_lines) if pain_lines else (
        "По ответам видно, что вы держите бизнес на интуиции и оперативных решениях, "
        "но не на регулярной системе из метрик и сверок."
    )

    # Слабейший слой
    weakest = min(layer_diagnosis, key=lambda d: d["quality_passed"])
    weakest_line = (
        f"Самая хрупкая зона по методологии — *{weakest['label']}*: "
        f"{weakest['gap']}"
    )

    top_rec = recommendations[0]["title"] if recommendations else "—"
    rec_line = f"Главный рычаг на ближайший квартал: *{top_rec}*."

    return f"{pain_block}\n\n{weakest_line}\n\n{rec_line}"


def _clip(s: str, n: int) -> str:
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


# ─── Главный entry-point ──────────────────────────────────────────────────────


def render_report_v2(
    *,
    application: Application,
    user: User,
    answers: list[CheckupAnswer],
) -> str:
    """Рендерит HTML-отчёт v2 (клиентский, не черновик)."""
    plan = "base"
    priority_metrics: list[str] = []
    is_self_demo = False
    if application.payload:
        plan = application.payload.get("plan", "base")
        priority_metrics = list(application.payload.get("priority_metrics") or [])
        is_self_demo = bool(application.payload.get("is_self_demo"))

    full_name = " ".join(filter(None, [user.last_name, user.first_name])) or "—"
    company = user.company_name or "—"

    team_size = detect_team_size(answers)
    tools_by_layer = detect_tools(answers)
    layer_diagnosis = [
        diagnose_layer(layer, answers)
        for layer in ("strategy", "sales", "operations", "finance")
    ]
    recommendations = select_recommendations(
        plan=plan,
        answers=answers,
        tools_by_layer=tools_by_layer,
        team_size=team_size,
    )
    scenarios = build_scenarios(priority_metrics, recommendations)
    summary = executive_summary(answers, layer_diagnosis, recommendations)

    vat_section = _vat_section_dict(answers)

    # Сырые ответы — компактная таблица в конце (для самопроверки клиента)
    questions_map = by_key()
    raw_answers = []
    for a in sorted(
        answers,
        key=lambda x: questions_map[x.question_key].order if x.question_key in questions_map else 99,
    ):
        q = questions_map.get(a.question_key)
        if q is None:
            continue
        raw_answers.append({
            "order": q.order,
            "layer": _LAYER_LABELS.get(q.layer, q.layer),
            "question": q.text,
            "answer": _clip(a.text or "", 600),
            "quality_passed": a.quality_passed,
            "skipped": a.text == "[пропущено]",
        })

    # ── Чекап v2 augmentation: 3 agent teasers + новая цена Диагностики 45 000 ──
    from src.core.checkup_pdf_blocks import (
        build_three_teasers,
        diagnostic_cta_block,
        extract_numeric_values,
        DIAGNOSTIC_PRICE_RUB,
    )
    from src.core.checkup_score import split_answers, total_checkup_score
    from src.core.checkup_video_script import get_video_script

    # Видны ли v2-ответы? (если хотя бы один answer_type='mc'/'numeric')
    has_v2_answers = any(
        getattr(a, "answer_type", None) in ("mc", "numeric") for a in answers
    )

    teasers: list[dict] = []
    cta_block: dict | None = None
    checkup_v2_score: int | None = None
    v2_layer_scores: dict[str, int] = {}
    plus_video_script: dict | None = None

    if has_v2_answers:
        mc, num, txt = split_answers(answers)
        segment_v2 = user.segment or "other"
        stage_v2 = user.quiz_stage or "team"
        try:
            checkup_v2_score, v2_layer_scores = total_checkup_score(
                mc, num, txt, segment_v2, stage_v2
            )
        except Exception:
            checkup_v2_score, v2_layer_scores = None, {}

        nums = extract_numeric_values(answers)
        seg_display = {
            "edu": "онлайн-школа", "mp": "маркетплейс", "it": "IT-агентство",
            "prod": "производство/опт", "serv": "услуги", "saas": "B2B SaaS",
            "other": "ваш сегмент",
        }.get(segment_v2, segment_v2)

        try:
            teasers = build_three_teasers(
                v2_layer_scores or {"01": 50, "02": 50, "03": 50, "04": 50},
                margin_pct=nums.get("margin_pct"),
                conv_pct=nums.get("conv_pct"),
                hours_per_week=nums.get("hours_per_week"),
                segment_display=seg_display,
            )
        except Exception:
            teasers = []

        weakest = None
        if v2_layer_scores:
            weakest = min(v2_layer_scores.items(), key=lambda x: x[1])[0]
        try:
            cta_block = diagnostic_cta_block(
                checkup_v2_score or 50, weakest_layer=weakest
            )
        except Exception:
            cta_block = None

        if plan == "plus":
            try:
                plus_video_script = get_video_script(segment_v2, stage_v2)
            except Exception:
                plus_video_script = None

    ctx = {
        "company": company,
        "full_name": full_name,
        "plan": plan,
        "plan_label": "Plus" if plan == "plus" else "Базовый",
        "is_plus": plan == "plus",
        "is_self_demo": is_self_demo,
        "generated_at": datetime.now(timezone.utc).strftime("%d.%m.%Y"),
        "summary": summary,
        "layer_diagnosis": layer_diagnosis,
        "recommendations": recommendations,
        "scenarios": scenarios,
        "vat_section": vat_section,
        "raw_answers": raw_answers,
        "team_size": team_size,
        "client_tools": all_tools(tools_by_layer),
        "priority_metrics": priority_metrics,
        "offer_url": settings.offer_checkup_url,
        "diagnostic_price_rub": f"{DIAGNOSTIC_PRICE_RUB:,}".replace(",", " "),  # 45 000
        "version": "v2" if has_v2_answers else "v1",
        # Чекап v2 блоки (TZ_checkup_plus_v2.md §8.3, §8.4)
        "teasers": teasers,
        "cta_block": cta_block,
        "checkup_v2_score": checkup_v2_score,
        "v2_layer_scores": v2_layer_scores,
        "mini_quiz_score": getattr(user, "quiz_score", None),
        "plus_video_script": plus_video_script,
        "has_v2_answers": has_v2_answers,
    }

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    try:
        template = env.get_template("checkup_report_v2.html")
        return template.render(**ctx)
    except Exception:
        # Fallback на старый минимальный HTML — лучше отдать что-то клиенту,
        # чем 500. Алерт Кате в этом случае пишется отдельно в Celery task.
        from src.core.checkup_report import _minimal_html
        return _minimal_html({
            "company": company, "full_name": full_name, "plan": plan,
            "plan_label": ctx["plan_label"],
            "generated_at": ctx["generated_at"],
            "answers_by_layer": {
                "strategy": [], "sales": [], "operations": [], "finance": []
            },
            "quality_summary": {"total": len(answers),
                                "passed": sum(1 for a in answers if a.quality_passed),
                                "failed": sum(1 for a in answers if not a.quality_passed)},
            "offer_url": settings.offer_checkup_url,
        })


def _vat_section_dict(answers: list[CheckupAnswer]) -> dict | None:
    """Структурированная информация по НДС-секции (для шаблона).

    Работает с v1 ключами (m2_ebitda, m3_vat_2026) и v2 ключом (c20_vat_2026_scenario).
    """
    revenue_answer = next(
        (a for a in answers if a.question_key in (
            "m2_ebitda", "m3_vat_2026", "c20_vat_2026_scenario"
        )),
        None,
    )
    if not revenue_answer:
        return None
    info = determine_vat_zone(revenue_answer.text)
    zone_color = {
        "below_threshold": "#22c55e",
        "approaching": "#f59e0b",
        "first_time": "#ef4444",
        "established": "#6b7280",
    }.get(info["zone"], "#6b7280")
    return {
        "zone": info["zone"],
        "color": zone_color,
        "description": info["description"],
        "advice": info["advice"],
    }
