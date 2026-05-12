"""Валидация входящего user-text (§C.9 ТЗ v3.1).

Применяется ДО любых FSM-проверок и LLM-вызова:
- длина ≤ MAX_USER_TEXT (4000 символов)
- запрещены NUL и control chars (кроме \\n \\r \\t)
- удаляем zero-width и bidirectional override (часто используются в spoof'инге)
"""
from __future__ import annotations

import re

MAX_USER_TEXT = 4000

# Control chars кроме TAB(\x09), LF(\x0A), CR(\x0D)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
# Zero-width, bidi-override, byte-order-mark
_INVISIBLE_RE = re.compile(
    "["
    "​‌‍‎‏"  # ZW + LRM/RLM
    "‪-‮"  # bidi override
    "⁦-⁩"  # isolate overrides
    "﻿"  # BOM
    "]"
)


class InputValidationError(ValueError):
    """Поднимается, когда вход не проходит валидацию (длина / опасные символы)."""


def clean_user_text(text: str | None) -> str:
    """Удаляет опасные символы, нормализует пробелы. НЕ ограничивает длину."""
    if not text:
        return ""
    text = _CONTROL_RE.sub("", text)
    text = _INVISIBLE_RE.sub("", text)
    return text.strip()


def validate_user_text(text: str | None) -> str:
    """Возвращает очищенный текст. Кидает InputValidationError, если длина >MAX."""
    cleaned = clean_user_text(text)
    if len(cleaned) > MAX_USER_TEXT:
        raise InputValidationError(
            f"Сообщение слишком длинное ({len(cleaned)} символов, лимит {MAX_USER_TEXT}). "
            "Перешлите по частям."
        )
    return cleaned
