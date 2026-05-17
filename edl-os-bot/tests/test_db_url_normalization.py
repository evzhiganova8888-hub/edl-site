"""Регрессия: get_engine() должен использовать normalized_database_url.

Railway передаёт DATABASE_URL=postgresql://..., а SQLAlchemy async engine
требует postgresql+asyncpg://. Свойство Settings.normalized_database_url
делает эту замену. До фикса 17.05.2026 get_engine() читал raw database_url,
из-за чего на Railway мог упасть с `No module named 'psycopg2'`.
"""
from __future__ import annotations


def test_normalized_database_url_adds_asyncpg():
    from src.core.config import Settings

    s = Settings(database_url="postgresql://user:pass@host:5432/db")
    assert s.normalized_database_url == "postgresql+asyncpg://user:pass@host:5432/db"


def test_normalized_database_url_idempotent():
    from src.core.config import Settings

    s = Settings(database_url="postgresql+asyncpg://user:pass@host:5432/db")
    assert s.normalized_database_url == "postgresql+asyncpg://user:pass@host:5432/db"


def test_normalized_database_url_passthrough_sqlite():
    from src.core.config import Settings

    s = Settings(database_url="sqlite+aiosqlite:///:memory:")
    assert s.normalized_database_url == "sqlite+aiosqlite:///:memory:"


def test_get_engine_uses_normalized_url(monkeypatch):
    """Главная регрессия: session.get_engine() должен вызывать normalized_database_url,
    а не raw database_url. Иначе Railway postgresql:// уронит engine creation.
    """
    import src.db.session as session_mod
    from src.core.config import settings

    captured: dict = {}

    def fake_create_async_engine(url, **kwargs):
        captured["url"] = url
        return object()  # заглушка движка

    monkeypatch.setattr(session_mod, "create_async_engine", fake_create_async_engine)
    session_mod.get_engine.cache_clear()

    monkeypatch.setattr(
        type(settings),
        "database_url",
        "postgresql://railway:secret@db.railway.internal:5432/edl",
        raising=False,
    )
    monkeypatch.setattr(
        type(settings),
        "normalized_database_url",
        property(
            lambda self: "postgresql+asyncpg://railway:secret@db.railway.internal:5432/edl"
        ),
        raising=False,
    )

    try:
        session_mod.get_engine()
        assert captured["url"].startswith("postgresql+asyncpg://"), (
            f"get_engine should use normalized URL, got {captured['url']!r}"
        )
    finally:
        session_mod.get_engine.cache_clear()
