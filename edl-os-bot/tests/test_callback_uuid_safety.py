"""Регрессия: malformed UUID в callback_data не должен валить handler.

До фикса 17.05.2026 callback `refund:request:<broken-uuid>` или
`checkup:start:<broken-uuid>` вызывал ValueError из UUID(...) → попадал в
_global_error_handler → пользователь видел «Что-то пошло не так на нашей
стороне» вместо тихого отката в меню.

Сценарий редкий (мы сами генерим callback_data), но возможен при:
- устаревшей клавиатуре в чате после миграции/деплоя;
- кастомном Telegram-клиенте, шлющем произвольный callback_data;
- замаскированной атаке через bot inline_keyboard.

Этот тест защищает от регрессии.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_safe_uuid_returns_none_for_garbage():
    from src.bot.handlers.checkup import _safe_uuid

    assert _safe_uuid("not-a-uuid") is None
    assert _safe_uuid("") is None
    assert _safe_uuid(None) is None
    assert _safe_uuid("12345") is None
    assert _safe_uuid("../../../etc/passwd") is None


def test_safe_uuid_parses_valid_uuid():
    from uuid import UUID

    from src.bot.handlers.checkup import _safe_uuid

    valid = "550e8400-e29b-41d4-a716-446655440000"
    assert _safe_uuid(valid) == UUID(valid)


@pytest.mark.asyncio
async def test_refund_callback_handles_malformed_uuid():
    """refund:request:<garbage> → handler возвращает REFUND_NO_ACTIVE,
    а не падает с ValueError → _global_error_handler.
    """
    from src.bot.handlers import refund

    query = MagicMock()
    query.data = "refund:request:not-a-uuid"
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.reply_text = AsyncMock()

    upd = MagicMock()
    upd.callback_query = query
    upd.effective_user = MagicMock(id=12345)

    ctx = MagicMock()

    await refund.handle_refund_callback(upd, ctx)

    # Главное: вызов не упал, юзер получил безопасное сообщение.
    query.message.reply_text.assert_awaited_once()
    sent = query.message.reply_text.await_args.args[0]
    # REFUND_NO_ACTIVE содержит сообщение «нет активных»
    assert "активн" in sent.lower() or "возврат" in sent.lower()


@pytest.mark.asyncio
async def test_checkup_callback_handles_malformed_uuid():
    """checkup:start:<garbage> → handler возвращается тихо (return),
    а не падает с ValueError.
    """
    from src.bot.handlers import checkup

    query = MagicMock()
    query.data = "checkup:start:not-a-uuid"
    query.answer = AsyncMock()

    upd = MagicMock()
    upd.callback_query = query

    ctx = MagicMock()
    ctx.user_data = {}

    # Не должно бросить — _safe_uuid → None → early return
    await checkup.handle_checkup_callback(upd, ctx)


@pytest.mark.asyncio
async def test_checkup_callback_handles_missing_uuid():
    """checkup:start (без UUID payload) → handler возвращается тихо."""
    from src.bot.handlers import checkup

    query = MagicMock()
    query.data = "checkup:start"
    query.answer = AsyncMock()

    upd = MagicMock()
    upd.callback_query = query

    ctx = MagicMock()
    ctx.user_data = {}

    await checkup.handle_checkup_callback(upd, ctx)
