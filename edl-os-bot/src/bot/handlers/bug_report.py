"""Bug-report handler (§E.1 ТЗ v3.1).

Пользователь жмёт «⚠️ Ответ неверный» под ответом бота → создаём запись
в `bot_errors`, опционально просим комментарий, не блокируя диалог.
Источник данных для Voice-of-Customer ритуала (§E.2).
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.bot import keyboards
from src.db.models import BotError
from src.db.repos import get_or_create_user, log_event
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

_PENDING_KEY = "bugreport_pending_id"


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback `bugreport:msg:<message_log_id>` или `bugreport:skip`."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if data == "bugreport:skip":
        context.user_data.pop(_PENDING_KEY, None)
        await query.message.reply_text("Окей, не записываем. Если что — /menu.")
        return

    if not data.startswith("bugreport:msg:"):
        return

    try:
        message_log_id = int(data.split(":")[2])
    except (IndexError, ValueError):
        logger.warning("Bad bugreport callback: %s", data)
        return

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        err = BotError(
            user_id=user.id,
            message_log_id=message_log_id,
        )
        session.add(err)
        await session.flush()
        bug_id = err.id
        await log_event(
            session,
            user_id=user.id,
            event="bot_error_reported",
            payload={"bot_error_id": bug_id, "message_log_id": message_log_id},
        )
        await session.commit()

    context.user_data[_PENDING_KEY] = bug_id
    await query.message.reply_text(
        "Записал. Иван перепроверит.\n\n"
        "Если хотите — напишите ниже, что именно было не так "
        "(одно сообщение). Это не обязательно.\n"
        "Если срочно — @lvanKhudyakov.",
        reply_markup=keyboards.bug_report_skip_keyboard(),
    )


async def handle_text_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Если ждём комментарий к bug-report — сохраняем и выходим из FSM."""
    bug_id = context.user_data.get(_PENDING_KEY)
    if not bug_id:
        return False

    text = (update.effective_message.text or "").strip()
    context.user_data.pop(_PENDING_KEY, None)

    if not text:
        return True

    factory = async_session_factory()
    async with factory() as session:
        from sqlalchemy import select

        row = (
            await session.execute(select(BotError).where(BotError.id == bug_id))
        ).scalar_one_or_none()
        if row:
            row.user_comment = text[:2000]
            await session.commit()
    await update.effective_message.reply_text("Спасибо, добавил к отчёту.")
    return True
