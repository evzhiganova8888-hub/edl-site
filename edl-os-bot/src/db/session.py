"""Async SQLAlchemy session factory."""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings


@lru_cache(maxsize=1)
def get_engine():
    return create_async_engine(
        settings.database_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def async_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)
