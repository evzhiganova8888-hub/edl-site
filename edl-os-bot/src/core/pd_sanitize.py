"""Фильтр ПД перед отправкой в LLM (§2.2 ТЗ).

LLM (Anthropic) получает только обезличенный текст. Это гарантирует, что
использование Anthropic не нарушает 152-ФЗ — мы не передаём ПД за рубеж.
"""
from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+7|7|8)[\s\-()]?\d{3}[\s\-()]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
)
_INN_RE = re.compile(r"\b\d{10,12}\b")
_CARD_RE = re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b")
_TG_USERNAME_RE = re.compile(r"@[A-Za-z0-9_]{4,32}")


def sanitize(text: str) -> str:
    """Заменяет email/телефоны/ИНН/номера карт/TG-username на плейсхолдеры."""
    if not text:
        return text
    text = _CARD_RE.sub("[card]", text)
    text = _EMAIL_RE.sub("[email]", text)
    text = _PHONE_RE.sub("[phone]", text)
    text = _INN_RE.sub("[inn]", text)
    text = _TG_USERNAME_RE.sub("[tg_user]", text)
    return text


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
