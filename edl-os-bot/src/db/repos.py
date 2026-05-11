"""Repository helpers — узкий слой над моделями."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Application, Event, MessageLog, PDAccessLog, User


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
) -> None:
    session.add(
        MessageLog(
            user_id=user_id,
            direction=direction,
            text=text,
            llm_tokens=llm_tokens,
            sticker_sent=sticker_sent,
            vat_topic_mentioned=vat_topic_mentioned,
            intent_detected=intent_detected,
        )
    )


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
