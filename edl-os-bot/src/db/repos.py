"""Repository helpers — узкий слой над моделями."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    Application,
    CheckupAnswer,
    Event,
    MessageLog,
    PDAccessLog,
    QuizSubmission,
    User,
)


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


# ── Чекап v2 helpers ──────────────────────────────────────────────────────────

async def get_checkup_answers(
    session: AsyncSession, application_id: uuid.UUID
) -> list[CheckupAnswer]:
    result = await session.execute(
        select(CheckupAnswer)
        .where(CheckupAnswer.application_id == application_id)
        .order_by(CheckupAnswer.answered_at.asc())
    )
    return list(result.scalars().all())


async def delete_checkup_answers(
    session: AsyncSession, application_id: uuid.UUID
) -> int:
    """Удаляет все ответы по application — для force-restart старого Чекапа на v2.

    Возвращает количество удалённых.
    """
    rows = await get_checkup_answers(session, application_id)
    for r in rows:
        await session.delete(r)
    return len(rows)


async def upsert_checkup_answer(
    session: AsyncSession,
    *,
    application_id: uuid.UUID,
    user_id: int,
    question_key: str,
    layer: str,
    text: str,
    word_count: int,
    answer_type: str,
    quality_passed: bool = False,
    quality_notes: str | None = None,
    answer_score: int | None = None,
    answer_numeric: float | None = None,
    answer_skipped: bool = False,
) -> CheckupAnswer:
    """Upsert ответа по (application_id, question_key)."""
    existing = await session.execute(
        select(CheckupAnswer).where(
            CheckupAnswer.application_id == application_id,
            CheckupAnswer.question_key == question_key,
        )
    )
    row = existing.scalar_one_or_none()
    if row:
        row.text = text
        row.word_count = word_count
        row.answer_type = answer_type
        row.quality_passed = quality_passed
        row.quality_notes = quality_notes
        row.answer_score = answer_score
        row.answer_numeric = answer_numeric
        row.answer_skipped = answer_skipped
        return row
    row = CheckupAnswer(
        application_id=application_id,
        user_id=user_id,
        question_key=question_key,
        layer=layer,
        text=text,
        word_count=word_count,
        answer_type=answer_type,
        quality_passed=quality_passed,
        quality_notes=quality_notes,
        answer_score=answer_score,
        answer_numeric=answer_numeric,
        answer_skipped=answer_skipped,
    )
    session.add(row)
    await session.flush()
    return row


async def load_mini_context(
    session: AsyncSession, user: User
) -> dict[str, Any] | None:
    """Возвращает Mini-Чекап контекст для skip-логики и intro Чекапа.

    Ищет последний QuizSubmission юзера. Возвращает dict с полями:
    {score, stage, segment, layer_scores, growth_points, weakest_layers}
    или None если Mini не проходился.
    """
    if not user.quiz_completed_at and not user.quiz_score:
        return None
    result = await session.execute(
        select(QuizSubmission)
        .where(QuizSubmission.user_id == user.id)
        .order_by(QuizSubmission.created_at.desc())
        .limit(1)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        # Юзер прошёл Mini, но QuizSubmission не сохранён (старый бот) — частичный
        return {
            "score": user.quiz_score,
            "stage": user.quiz_stage,
            "segment": user.segment,
            "layer_scores": None,
            "growth_points": None,
            "weakest_layers": None,
        }
    layer_scores = sub.layer_scores or {}
    weakest_layers = sorted(
        layer_scores.items(), key=lambda x: x[1]
    )[:2] if isinstance(layer_scores, dict) else []
    return {
        "score": sub.score,
        "stage": sub.stage,
        "segment": sub.segment,
        "layer_scores": layer_scores,
        "growth_points": sub.growth_points or [],
        "weakest_layers": [l for l, _ in weakest_layers],
    }
