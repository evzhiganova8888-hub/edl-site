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
        else:
            await query.message.reply_text(
                "Хорошо. Без согласия я не смогу оформить оплату Чекапа, "
                "но FAQ и общие материалы доступны.\n\n"
                f"Команда: {texts.WORKING_HOURS_DISCLAIMER}"
            )
            return

    # Accept: проверяем отложенный intent (юзер кликнул «Купить» до consent).
    # Локальный импорт — избегаем циклической зависимости consent ↔ audit.
    from src.bot.handlers import audit as audit_handler

    pending = context.user_data.pop(audit_handler.PENDING_POST_CONSENT_KEY, None)
    if pending and pending.get("action") == "audit_start_purchase":
        plan = pending.get("plan", audit_handler.PLAN_BASE)
        await query.message.reply_text("Спасибо, согласие зафиксировано. Продолжаем оформление.")
        await audit_handler._begin_purchase(update, context, plan=plan)
        return

    await query.message.reply_text(
        "Спасибо, согласие зафиксировано. Можем продолжать.",
        reply_markup=keyboards.main_menu(),
    )
