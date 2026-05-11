"""Feature flags — runtime-toggle через БД (§10 ТЗ v3).

Fallback на env-переменную если БД недоступна (миграция ещё не применена и т.п.).
Кэш простой in-memory с TTL 60 секунд.
"""
from __future__ import annotations

import time
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.models import FeatureFlag

FLAG_VITACONSULT_PUBLIC: Final[str] = "vitaconsult_public"

_CACHE: dict[str, tuple[bool, float]] = {}
_TTL_SECONDS = 60.0


async def get_flag(session: AsyncSession, key: str, *, default: bool = False) -> bool:
    """Читает флаг из БД, кэширует на 60 секунд."""
    cached = _CACHE.get(key)
    if cached and time.monotonic() - cached[1] < _TTL_SECONDS:
        return cached[0]

    try:
        result = await session.execute(select(FeatureFlag).where(FeatureFlag.key == key))
        flag = result.scalar_one_or_none()
        value = bool(flag.enabled) if flag else default
    except Exception:
        # БД может быть не готова — fallback на env
        value = _env_fallback(key, default)

    _CACHE[key] = (value, time.monotonic())
    return value


async def set_flag(
    session: AsyncSession,
    key: str,
    *,
    enabled: bool,
    actor: str,
) -> None:
    """Обновляет флаг + сбрасывает кэш."""
    result = await session.execute(select(FeatureFlag).where(FeatureFlag.key == key))
    flag = result.scalar_one_or_none()
    if flag is None:
        flag = FeatureFlag(key=key, enabled=enabled, updated_by=actor)
        session.add(flag)
    else:
        flag.enabled = enabled
        flag.updated_by = actor
    _CACHE.pop(key, None)


def invalidate_cache(key: str | None = None) -> None:
    if key is None:
        _CACHE.clear()
    else:
        _CACHE.pop(key, None)


def _env_fallback(key: str, default: bool) -> bool:
    if key == FLAG_VITACONSULT_PUBLIC:
        return bool(settings.vitaconsult_public)
    return default
