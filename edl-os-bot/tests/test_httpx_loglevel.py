"""Регрессия: httpx и httpcore loggers не должны логировать BOT_TOKEN.

Контекст 17.05.2026: PTB ходит к Telegram через httpx. При loglevel=INFO
httpx логирует каждый запрос с полным URL вида
`POST https://api.telegram.org/bot<TOKEN>/sendMessage`. BOT_TOKEN целиком
оказывается в Railway logs. Любой скриншот логов (или их экспорт в чат
с инженером) = утечка bot-токена → возможность подделки сообщений.

Этот тест защищает от регрессии: если кто-то снова допишет
`logging.basicConfig(level=INFO)` для всех loggers, BOT_TOKEN опять
утечёт. Тест проверяет, что httpx и httpcore приглушены до WARNING
после импорта main.
"""
from __future__ import annotations

import logging
from pathlib import Path

MAIN_PY = Path(__file__).resolve().parent.parent / "src" / "main.py"


def test_main_py_sets_httpx_logger_to_warning():
    """В main.py должна быть строка, поднимающая httpx logger до WARNING."""
    text = MAIN_PY.read_text(encoding="utf-8")
    assert 'logging.getLogger("httpx").setLevel(logging.WARNING)' in text, (
        "main.py must silence httpx INFO logs — they leak the full Telegram "
        "API URL (including BOT_TOKEN) to Railway logs."
    )


def test_main_py_sets_httpcore_logger_to_warning():
    """httpcore — нижний слой httpx, тоже логирует URL на DEBUG/INFO."""
    text = MAIN_PY.read_text(encoding="utf-8")
    assert 'logging.getLogger("httpcore").setLevel(logging.WARNING)' in text, (
        "main.py must silence httpcore INFO logs too (lower-level HTTP "
        "transport that can leak the same URL)."
    )


def test_loggers_actually_silenced_after_import():
    """Семантическая проверка: после import src.main эффективный уровень
    httpx logger должен быть >= WARNING.
    """
    import src.main  # noqa: F401 — importing triggers the basicConfig

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING
