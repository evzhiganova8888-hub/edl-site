"""Авторизация: статический whitelist + session admin через access key."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.models import AdminSession


def require_admin(x_telegram_user_id: str | None = Header(default=None)) -> int:
    """FastAPI dependency — проверяет X-Telegram-User-Id против ADMIN_USER_IDS."""
    if not x_telegram_user_id or not x_telegram_user_id.isdigit():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing X-Telegram-User-Id")
    user_id = int(x_telegram_user_id)
    if user_id not in settings.admin_user_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not an admin")
    return user_id


def is_admin(telegram_user_id: int) -> bool:
    """Синхронная проверка только по ADMIN_USER_IDS (для UI-guard без сессии)."""
    return telegram_user_id in settings.admin_user_ids


async def is_admin_active(session: AsyncSession, telegram_user_id: int) -> bool:
    """Проверка прав: статический список ИЛИ активная AdminSession."""
    if telegram_user_id in settings.admin_user_ids:
        return True
    now = datetime.now(timezone.utc)
    stmt = (
        select(AdminSession)
        .where(AdminSession.telegram_id == telegram_user_id)
        .where(AdminSession.expires_at > now)
        .where(AdminSession.revoked_at.is_(None))
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    return row is not None
