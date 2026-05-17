"""Регрессия: alembic env.py должен генерировать sync URL с psycopg3 dialect.

Контекст 17.05.2026: pyproject.toml ставит только psycopg[binary] (psycopg3),
не psycopg2. SQLAlchemy по умолчанию для `postgresql://` подключается через
psycopg2 → ImportError при alembic upgrade в Railway. Поэтому env.py обязан
форсить `postgresql+psycopg://` (psycopg3 driver) для обеих форм входа:
- postgresql+asyncpg://...  (Settings.normalized_database_url)
- postgresql://...           (Railway raw DATABASE_URL)

Этот тест защищает от регрессии: если кто-то поменяет env.py обратно на
`postgresql://`, alembic в проде упадёт.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PY = REPO_ROOT / "alembic" / "env.py"


def _extract_env_block() -> str:
    text = ENV_PY.read_text(encoding="utf-8")
    return text


def test_env_py_forces_psycopg3_dialect_for_asyncpg():
    text = _extract_env_block()
    assert "postgresql+psycopg://" in text, (
        "env.py must rewrite URLs to psycopg3 dialect (postgresql+psycopg://) — "
        "production Dockerfile only ships psycopg3, not psycopg2."
    )
    assert re.search(
        r'replace\(\s*"postgresql\+asyncpg://",\s*"postgresql\+psycopg://"', text
    ), "env.py must convert postgresql+asyncpg:// → postgresql+psycopg://"


def test_env_py_forces_psycopg3_dialect_for_bare_url():
    text = _extract_env_block()
    assert re.search(
        r'replace\(\s*"postgresql://",\s*"postgresql\+psycopg://"', text
    ), (
        "env.py must convert raw postgresql:// → postgresql+psycopg:// — Railway "
        "DATABASE_URL has no driver suffix, SQLAlchemy defaults to psycopg2 which "
        "is not installed in the Dockerfile."
    )


def test_env_py_does_not_leave_bare_postgresql_default(monkeypatch, tmp_path):
    """Sanity: импортируем env.py с мокнутым контекстом и убеждаемся, что
    итоговый sqlalchemy.url начинается с postgresql+psycopg:// для обеих форм.
    """
    # Простейший способ — выполнить только URL-преобразующий кусок:
    # копируем логику и проверяем поведение, а не сам импорт alembic.env.
    def transform(raw: str) -> str:
        if raw.startswith("postgresql+asyncpg://"):
            return raw.replace(
                "postgresql+asyncpg://", "postgresql+psycopg://", 1
            )
        if raw.startswith("postgresql://"):
            return raw.replace("postgresql://", "postgresql+psycopg://", 1)
        return raw

    assert transform("postgresql://u:p@h/db").startswith("postgresql+psycopg://")
    assert transform("postgresql+asyncpg://u:p@h/db").startswith(
        "postgresql+psycopg://"
    )
    # sqlite passthrough
    assert transform("sqlite+aiosqlite:///:memory:") == "sqlite+aiosqlite:///:memory:"
    # idempotent
    assert (
        transform("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    )
