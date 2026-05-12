"""Запись структурированной обратной связи (beta 12.05-19.05).

Слой над `Feedback` ORM, чтобы handler-ы не лезли в SQLAlchemy напрямую.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Feedback
from src.db.repos import log_event

# Допустимые значения step (исходим из бизнес-карты экранов).
STEPS = {
    "welcome",
    "audit",
    "audit_sample",
    "quiz",
    "offer",
    "payment",
    "ai_reply",
    "refund",
    "privacy",
    "demo",
    "diagnostic",
    "sprint_waitlist",
    "other",
}

# Категории — выбираем эмодзи под бизнес-смысл, не путать с bug_report (👾 = баг).
CATEGORIES = {
    "bug": "👾 Баг",
    "missing": "🤔 Не хватает",
    "idea": "💡 Идея",
    "praise": "👍 Понравилось",
}


async def record_feedback(
    session: AsyncSession,
    *,
    user_id: int | None,
    step: str,
    category: str,
    comment: str | None = None,
    severity: str | None = None,
) -> int:
    """Записывает Feedback + событие. Возвращает id записи (после flush)."""
    if step not in STEPS:
        step = "other"
    if category not in CATEGORIES:
        category = "missing"
    row = Feedback(
        user_id=user_id,
        step=step,
        category=category,
        severity=severity,
        comment=(comment or None),
    )
    session.add(row)
    await session.flush()
    await log_event(
        session,
        user_id=user_id,
        event="feedback_submitted",
        payload={
            "feedback_id": row.id,
            "step": step,
            "category": category,
            "has_comment": bool(comment),
        },
    )
    return row.id
