"""Авторизация админки — Telegram user_id из ADMIN_USER_IDS."""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from src.core.config import settings


def require_admin(x_telegram_user_id: str | None = Header(default=None)) -> int:
    """Принимает заголовок X-Telegram-User-Id, сверяет с ADMIN_USER_IDS.

    Это упрощённая авторизация для MVP. В Спринте 4 — заменим на полноценный
    Telegram OAuth flow с подписью initData.
    """
    if not x_telegram_user_id or not x_telegram_user_id.isdigit():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing X-Telegram-User-Id")
    user_id = int(x_telegram_user_id)
    if user_id not in settings.admin_user_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not an admin")
    return user_id


def is_admin(telegram_user_id: int) -> bool:
    return telegram_user_id in settings.admin_user_ids
