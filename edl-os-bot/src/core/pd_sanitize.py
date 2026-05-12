"""Фильтр ПД и секретов перед отправкой в LLM (§2.2 ТЗ v3 + §C.8 v3.1).

LLM (Anthropic) получает только обезличенный текст. Это гарантирует, что
использование Anthropic не нарушает 152-ФЗ — ПД не уходят за рубеж.
Дополнительно: блокируем утечку API-ключей и токенов через сообщения.
"""
from __future__ import annotations

import re
from typing import Dict, Tuple

# ПД-паттерны (152-ФЗ scope)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+7|7|8)[\s\-()]?\d{3}[\s\-()]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
)
_INN_RE = re.compile(r"\b\d{10,12}\b")
_CARD_RE = re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b")
_TG_USERNAME_RE = re.compile(r"@[A-Za-z0-9_]{4,32}")
# «Меня зовут Иван Петров», «я — Анна Сидорова»
_NAME_INTRO_RE = re.compile(
    r"(?:меня зовут|я\s+[\-—–]\s*)\s*([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)"
)

# Секреты — высший приоритет, фильтруем ДО ПД
_TG_BOT_TOKEN_RE = re.compile(r"\b\d{8,10}:[A-Za-z0-9_\-]{35}\b")
_ANTHROPIC_KEY_RE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")
_OPENAI_KEY_RE = re.compile(r"sk-[A-Za-z0-9]{20,}")
_GITHUB_PAT_RE = re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}\b")

# Порядок важен: секреты → карты → email/phone → TG → ИНН (длинные числа) → имя
_PATTERNS: Tuple[Tuple[re.Pattern, str], ...] = (
    (_TG_BOT_TOKEN_RE, "[telegram_token_redacted]"),
    (_ANTHROPIC_KEY_RE, "[anthropic_key_redacted]"),
    (_GITHUB_PAT_RE, "[github_pat_redacted]"),
    (_OPENAI_KEY_RE, "[openai_key_redacted]"),
    (_CARD_RE, "[card]"),
    (_EMAIL_RE, "[email]"),
    (_PHONE_RE, "[phone]"),
    (_TG_USERNAME_RE, "[tg_user]"),
    (_INN_RE, "[inn]"),
    (_NAME_INTRO_RE, "[name]"),
)


def sanitize(text: str) -> str:
    """Заменяет email/телефоны/ИНН/карты/TG/секреты/имена-самопредставления."""
    if not text:
        return text
    for pat, marker in _PATTERNS:
        text = pat.sub(marker, text)
    return text


def sanitize_with_stats(text: str) -> Tuple[str, Dict[str, int]]:
    """Возвращает (очищенный_текст, {pattern_name: count}).

    Используется для логирования в `events` с типом `pd_redacted`
    (без самих ПД, только метаданные).
    """
    if not text:
        return text, {}
    stats: Dict[str, int] = {}
    for pat, marker in _PATTERNS:
        matches = pat.findall(text)
        if matches:
            stats[marker.strip("[]")] = len(matches)
            text = pat.sub(marker, text)
    return text, stats


def contains_pd(text: str) -> bool:
    """Быстрая проверка для логирования."""
    if not text:
        return False
    return bool(
        _EMAIL_RE.search(text)
        or _PHONE_RE.search(text)
        or _CARD_RE.search(text)
        or _INN_RE.search(text)
    )


def contains_secret(text: str) -> bool:
    """Сработали ли паттерны секретов (токены / API ключи)."""
    if not text:
        return False
    return bool(
        _TG_BOT_TOKEN_RE.search(text)
        or _ANTHROPIC_KEY_RE.search(text)
        or _OPENAI_KEY_RE.search(text)
        or _GITHUB_PAT_RE.search(text)
    )
