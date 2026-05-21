"""Repository helpers — узкий слой над моделями."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Application, Event, MessageLog, PDAccessLog, QuizSubmission, User


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    *,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> tuple[User, bool]:
    """Return (user, created)."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is not None:
        return user, False

    user = User(
        telegram_id=telegram_id,
        telegram_username=username,
        first_name=first_name,
        last_name=last_name,
    )
    session.add(user)
    await session.flush()
    return user, True


async def log_event(
    session: AsyncSession,
    *,
    user_id: int | None,
    event: str,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(Event(user_id=user_id, event=event, payload=payload or {}))


async def log_message(
    session: AsyncSession,
    *,
    user_id: int | None,
    direction: str,
    text: str | None,
    llm_tokens: int | None = None,
    sticker_sent: bool = False,
    vat_topic_mentioned: bool = False,
    intent_detected: str | None = None,
) -> MessageLog:
    """Сохраняет сообщение в БД. Возвращает запись с id (после flush)."""
    row = MessageLog(
        user_id=user_id,
        direction=direction,
        text=text,
        llm_tokens=llm_tokens,
        sticker_sent=sticker_sent,
        vat_topic_mentioned=vat_topic_mentioned,
        intent_detected=intent_detected,
    )
    session.add(row)
    await session.flush()  # нужен id для bug-report (§E.3 v3.1)
    return row


async def log_pd_access(
    session: AsyncSession,
    *,
    actor: str,
    user_id: int | None,
    action: str,
    fields: list[str] | None = None,
) -> None:
    session.add(
        PDAccessLog(actor=actor, user_id=user_id, action=action, fields=fields)
    )


async def record_consent_pd(session: AsyncSession, user: User, version: str) -> None:
    user.consent_pd_given_at = datetime.now(timezone.utc)
    user.consent_pd_version = version


async def mark_quiz_completed(
    session: AsyncSession,
    *,
    user: User,
    score: int,
    stage: str,
    segment: str,
    layer_scores: dict[str, Any],
    answers: dict[str, Any],
    growth_points: list[dict[str, Any]],
    source: str = "bot",
    duration_sec: int | None = None,
    widget_session_id: uuid.UUID | None = None,
    consent_marketing: bool = False,
    email: str | None = None,
    outlier_flag: str | None = None,
    stage_confidence: str = "high",
) -> QuizSubmission:
    """Сохраняет результат Mini-Чекапа и обновляет users."""
    user.quiz_score = score
    user.quiz_stage = stage
    user.quiz_completed_at = datetime.now(timezone.utc)

    submission = QuizSubmission(
        user_id=user.id,
        source=source,
        widget_session_id=widget_session_id,
        segment=segment,
        stage=stage,
        stage_confidence=stage_confidence,
        outlier_flag=outlier_flag,
        score=score,
        layer_scores=layer_scores,
        answers=answers,
        growth_points=growth_points,
        duration_sec=duration_sec,
        consent_marketing_at_submit=consent_marketing,
        email=email,
    )
    session.add(submission)
    await session.flush()
    return submission


async def get_quiz_submission(
    session: AsyncSession, quiz_session_id: uuid.UUID
) -> QuizSubmission | None:
    result = await session.execute(
        select(QuizSubmission).where(QuizSubmission.id == quiz_session_id)
    )
    return result.scalar_one_or_none()


async def create_application(
    session: AsyncSession,
    *,
    user: User,
    type: str,
    source: str | None = None,
    cta_location: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Application:
    app = Application(
        user_id=user.id,
        type=type,
        source=source,
        cta_location=cta_location,
        payload=payload or {},
    )
    session.add(app)
    await session.flush()
    return app
