"""21-й уточняющий вопрос: 3 ключевые метрики бизнеса клиента.

Не часть основных 20 вопросов Founder OS — финальный штрих перед PDF,
чтобы собрать 3 сценария (Sniper / Combo / Full Stack) под ВАШИ метрики,
а не под средние по отрасли.

Используется в checkup.py:_ask_priorities и checkup_report для генерации
сценариев.
"""
from __future__ import annotations

import re


PROMPT_TEXT = (
    "Спасибо за развёрнутые ответы. Один уточняющий момент перед "
    "формированием PDF.\n\n"
    "Назовите *3 метрики вашего бизнеса*, по которым вы судите о его здоровье. "
    "В порядке приоритета.\n\n"
    "Например: выручка / CAC / retention / маржа / NPS / utilization / runway. "
    "Можно своими словами.\n\n"
    "Это даст собрать сценарии под ВАШИ цифры, а не под средние по отрасли."
)

RETRY_TEXT = (
    "Похоже, я не уловила конкретные метрики. Метрика — это то, что измеряется "
    "числом (выручка в ₽, маржа в %, retention в %, CAC в ₽, NPS, "
    "utilization часов и т.д.).\n\n"
    "Попробуйте ещё раз — 3 главные метрики бизнеса в порядке приоритета. "
    "Если затрудняетесь, я приму как есть и в PDF использую категориальные "
    "сценарии."
)

# Словарь известных метрик. Лежит в одном модуле с парсером — синхронность важна.
_METRIC_KEYWORDS = frozenset(
    {
        # выручка / продажи
        "выручка", "оборот", "доход", "продажи", "revenue", "выручки",
        "арр", "arr", "mrr", "ммр", "gmv", "gross",
        # маржа / прибыль
        "маржа", "маржу", "маржинальность", "прибыль", "ebitda", "ebit",
        "margin", "profit", "налог",
        # юнит-экономика
        "cac", "ltv", "ltv/cac", "ltvcac", "aov", "средний чек", "чек",
        "юнит", "unit", "payback",
        # воронка
        "конверсия", "conversion", "lead", "лид", "лидов", "демо",
        "воронка", "funnel", "win-rate", "win rate", "сделок",
        # удержание / отток
        "retention", "удержание", "churn", "отток", "nps", "csat",
        # cash / денежный поток
        "cash", "runway", "ранвей", "ран-вей", "cashflow", "поток",
        "резерв", "касса", "остаток",
        # operations
        "utilization", "загрузка", "часы", "hours", "загрузки",
        "себестоимость", "cogs",
        # finance/НДС
        "ндс", "vat",
    }
)


def parse_metrics(raw: str) -> list[str]:
    """Расщепляет строку юзера на список метрик.

    Разделители: запятая, точка с запятой, слэш, `→`, `>`, «и», переводы строк.
    Triming + lower + удаление пунктуации по краям.
    Дедуп с сохранением порядка.
    """
    if not raw:
        return []
    # Заменяем разделители на одну запятую
    normalized = re.sub(r"[;/\n→>•·]+", ",", raw)
    # Слово «и» как разделитель только если окружено пробелами
    normalized = re.sub(r"\s+и\s+", ",", normalized, flags=re.IGNORECASE)
    # Нумерованный список «1) ... 2) ... 3) ...» без запятых:
    # вставляем разделитель ПЕРЕД «N)» / «N.» (не в начале строки).
    normalized = re.sub(r"(?<!^)\s+(?=\d+\s*[.)])", ",", normalized)
    parts = [p.strip(" .,!-—") for p in normalized.split(",")]
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        # Игнорируем чистые числа («1)», «2.»)
        if re.fullmatch(r"\d+[.)]?", p):
            continue
        # Удаляем ведущую нумерацию «1) выручка», «2. маржа»
        p = re.sub(r"^\d+\s*[.)]\s*", "", p).strip()
        if not p:
            continue
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def looks_like_metric(token: str) -> bool:
    """Один токен похож на метрику?

    Эвристика: содержит число / валюту / % / совпадает с известной keyword.
    """
    if not token:
        return False
    t = token.lower()
    if any(kw in t for kw in _METRIC_KEYWORDS):
        return True
    # Содержит число с единицей или процент
    if re.search(r"\d+\s*(?:%|₽|руб|млн|тыс|p\.p\.|пп|часов|часы)", t):
        return True
    # Содержит просто число
    if re.search(r"\d{2,}", t):
        return True
    return False


def validate_metrics(metrics: list[str]) -> tuple[str, list[str]]:
    """Валидирует список метрик.

    Возвращает (status, normalized_metrics):
    - status == 'ok' если ≥2 метрики И хотя бы половина похожа на метрики
    - status == 'too_few' если <2
    - status == 'too_many' если >5 (просим выбрать топ-3)
    - status == 'not_metrics' если есть, но не похожи на метрики
    """
    if len(metrics) > 5:
        return "too_many", metrics
    if len(metrics) < 2:
        return "too_few", metrics
    matched = sum(1 for m in metrics if looks_like_metric(m))
    if matched < max(1, len(metrics) // 2):
        return "not_metrics", metrics
    return "ok", metrics[:5]
