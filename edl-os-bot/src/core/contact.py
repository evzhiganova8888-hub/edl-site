"""Валидация ФИО, email, телефона для FSM-сбора контактов."""
from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_PHONE_RE = re.compile(r"^(?:\+7|7|8)[\s\-()]*?\d[\d\s\-()]{9,}$")


def normalize_email(text: str) -> str | None:
    text = (text or "").strip()
    if _EMAIL_RE.match(text):
        return text.lower()
    return None


def normalize_phone(text: str) -> str | None:
    text = (text or "").strip()
    if not _PHONE_RE.match(text):
        return None
    digits = re.sub(r"\D", "", text)
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    return "+" + digits


def normalize_full_name(text: str) -> str | None:
    text = (text or "").strip()
    if len(text) < 4:
        return None
    parts = [p for p in re.split(r"\s+", text) if p]
    if len(parts) < 2:
        return None
    return " ".join(parts)


def normalize_company(text: str) -> str | None:
    text = (text or "").strip()
    if len(text) < 2:
        return None
    return text
