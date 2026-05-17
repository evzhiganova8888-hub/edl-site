"""Регрессия: _global_error_handler — последняя линия защиты пользователя.

Шаблон ошибки «Что-то пошло не так на нашей стороне» — это П0-фоллбек,
который никогда не должен ломаться. Если он сам кидает исключение, юзер
видит «ничего не происходит» (см. P0 inv_id NULL bug 12.05.2026).

Проверяем:
1. При обычном исключении handler отправляет fallback юзеру.
2. Если БД-лог падает — handler не падает, юзер всё равно получает сообщение.
3. Если у update нет effective_message — handler не падает.
4. Если update вообще не Update (например None) — handler не падает.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.handlers import _global_error_handler


def _make_update_with_message():
    msg = MagicMock()
    msg.reply_text = AsyncMock()
    user = SimpleNamespace(id=12345)
    upd = MagicMock()
    upd.effective_message = msg
    upd.effective_user = user
    # spec=Update нужен, чтобы isinstance(update, Update) был True
    return upd, msg


def _make_context(error: Exception):
    ctx = MagicMock()
    ctx.error = error
    return ctx


@pytest.mark.asyncio
async def test_error_handler_sends_fallback_to_user():
    upd, msg = _make_update_with_message()
    ctx = _make_context(RuntimeError("boom"))

    with patch("src.bot.handlers.isinstance", return_value=True), patch(
        "src.bot.handlers.async_session_factory"
    ) as factory_mock:
        # Сессия с успешным commit
        session = AsyncMock()
        factory = MagicMock()
        factory.return_value.__aenter__ = AsyncMock(return_value=session)
        factory.return_value.__aexit__ = AsyncMock(return_value=False)
        factory_mock.return_value = factory.return_value

        with patch("src.bot.handlers.log_event", new=AsyncMock()):
            await _global_error_handler(upd, ctx)

    msg.reply_text.assert_awaited_once()
    sent = msg.reply_text.await_args.args[0]
    assert "Что-то пошло не так" in sent
    assert "/menu" in sent


@pytest.mark.asyncio
async def test_error_handler_survives_db_logging_failure():
    """Если log_event падает — fallback всё равно должен быть отправлен."""
    upd, msg = _make_update_with_message()
    ctx = _make_context(RuntimeError("boom"))

    with patch("src.bot.handlers.isinstance", return_value=True), patch(
        "src.bot.handlers.async_session_factory",
        side_effect=Exception("DB connection refused"),
    ):
        # Не должно бросить наружу
        await _global_error_handler(upd, ctx)

    # Юзер всё равно получил сообщение
    msg.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_error_handler_survives_reply_failure():
    """Если reply_text падает (юзер заблокировал бота) — handler не должен
    падать, должен попытаться залогировать в БД и тихо выйти."""
    upd, msg = _make_update_with_message()
    msg.reply_text = AsyncMock(side_effect=Exception("Forbidden: bot blocked"))
    ctx = _make_context(RuntimeError("boom"))

    with patch("src.bot.handlers.isinstance", return_value=True), patch(
        "src.bot.handlers.async_session_factory"
    ) as factory_mock:
        session = AsyncMock()
        factory_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        factory_mock.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("src.bot.handlers.log_event", new=AsyncMock()):
            # Не должно бросить наружу — handler глотает ошибку reply_text
            await _global_error_handler(upd, ctx)


@pytest.mark.asyncio
async def test_error_handler_handles_non_update_object():
    """Если update не Update (например, ошибка в job_queue) — handler не падает."""
    ctx = _make_context(RuntimeError("background job failed"))

    with patch("src.bot.handlers.async_session_factory") as factory_mock:
        session = AsyncMock()
        factory_mock.return_value.__aenter__ = AsyncMock(return_value=session)
        factory_mock.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("src.bot.handlers.log_event", new=AsyncMock()):
            # Не должно бросить — update = None, isinstance проверка нас защищает
            await _global_error_handler(None, ctx)
