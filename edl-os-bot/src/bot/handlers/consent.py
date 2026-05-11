"""Согласие на обработку ПД (152-ФЗ, §13 ТЗ v3)."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from src.bot import keyboards, texts
from src.core import consent as consent_core
from src.db.repos import get_or_create_user
from src.db.session import async_session_factory


async def request_consent(update: Update) -> None:
    """Показать запрос согласия. Вызывается перед сбором ПД."""
    await update.effective_message.reply_text(
        consent_core.consent_text(),
        reply_markup=keyboards.consent_keyboard(),
    )


async def handle_consent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    decision = (query.data or "").split(":", 1)[1] if ":" in (query.data or "") else "decline"

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        if decision == "accept":
            await consent_core.give_consent(session, user)
            await session.commit()
            await query.message.reply_text(
                "Спасибо, согласие зафиксировано. Можем продолжать.",
                reply_markup=keyboards.main_menu(),
            )
        else:
            await query.message.reply_text(
                "Хорошо. Без согласия я не смогу собрать данные для звонка или "
                "оплаты, но FAQ и общие материалы доступны.\n\n"
                f"Команда: {texts.WORKING_HOURS_DISCLAIMER}"
            )
