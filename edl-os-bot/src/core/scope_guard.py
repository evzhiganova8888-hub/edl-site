"""Safety guard: deterministic off-topic фильтр без LLM.

Алгоритм (whitelist + blacklist, без нейросети):
- whitelist-маркеры → если есть хотя бы 1 → разрешаем LLM.
- blacklist-маркеры → если есть хотя бы 1 → блокируем.
- Ультракороткий запрос (≤3 слов) без whitelist-маркера → блокируем.
"""
from __future__ import annotations

import re

_WHITELIST: tuple[str, ...] = (
    # Слои EDL OS
    "стратег", "воронк", "pipeline", "операционк", "маржа", "маржин",
    "cash", "cashflow", "кэш", "ндс", "усн", "осно", "vat",
    "cycle", "цикл", "cac", "aov", "arr", "mrr", "churn", "retention",
    "загрузк", "онбординг", "onboard", "дроблен", "ebitda",
    "найм", "нанима", "ротац", "кредит", "резерв", "ликвидн",
    # Продукты EDL OS
    "чекап", "checkup", "диагностик", "спринт", "sprint",
    "demo", "демо", "оферт", "возврат", "refund", "тариф",
    # Команда / бренд
    "катя", "иван", "жиганов", "edl", "founder os", "методологи",
    # Сегменты
    "производств", "оптов", "маркетингов", "агентств", "юриди",
    "it-услуг", "b2b saas", "saas", "маркетплейс",
    # Финансы бизнеса (общие)
    "выручк", "revenue", "прибыл", "profit", "бюджет", "fot", "фот",
    "клиент", "сделк", "контракт", "счёт", "invoice", "платёж", "оплат",
    "лид", "воронка", "конверси", "canvass",
    # Операции
    "команд", "роль", "pm", "cto", "cfo", "ceo", "cofo",
    "процесс", "регламент", "kpi", "okr", "метрик",
)

_BLACKLIST: tuple[str, ...] = (
    "погод", "политик", "выборы", "выбор", "война", "войн",
    "знакомств", "отношени", "секс", "крипт", "биткоин", "bitcoin",
    "trading", "трейдинг", "прогноз акц", "forex",
    "программирован", "code review", "написать код", "парсер",
    "иммиграц", "релокац", "виза", "гражданств",
    "ставки", "тотализат", "казино",
)

_MIN_WORDS_THRESHOLD = 3


def is_off_topic(text: str) -> bool:
    """True → запрос вне скоупа EDL OS, нужен canned-ответ без LLM."""
    lowered = text.lower()
    words = lowered.split()

    # Blacklist check первым — жёсткое вето
    for marker in _BLACKLIST:
        if marker in lowered:
            return True

    # Короткий запрос без whitelist-маркеров — скорее всего приветствие/мусор
    if len(words) <= _MIN_WORDS_THRESHOLD:
        for marker in _WHITELIST:
            if marker in lowered:
                return False  # есть маркер → разрешаем
        return True  # коротко и не по теме

    # Длинный запрос — разрешаем если есть хотя бы 1 whitelist-маркер
    for marker in _WHITELIST:
        if marker in lowered:
            return False

    # Маркеров нет — блокируем
    return True
