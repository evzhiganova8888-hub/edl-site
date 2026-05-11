"""/admin команда для команды EDL (Катя, Иван) — сводка + toggle.

Доступ — только telegram_id из ADMIN_USER_IDS.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.admin.auth import is_admin
from src.core.flags import FLAG_VITACONSULT_PUBLIC, get_flag, set_flag
from src.db.models import Application, Event, Payment
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.effective_message.reply_text(
            "Эта команда — только для команды EDL. Если что-то ищете — /menu."
        )
        return

    factory = async_session_factory()
    since = datetime.now(timezone.utc) - timedelta(days=30)
    async with factory() as session:
        new_apps = await session.scalar(
            select(func.count(Application.id)).where(Application.created_at >= since)
        )
        paid = await session.scalar(
            select(func.count(Application.id))
            .where(Application.payment_succeeded_at >= since)
        )
        revenue_kop = await session.scalar(
            select(func.sum(Payment.amount_kopecks))
            .where(Payment.status == "succeeded")
            .where(Payment.paid_at >= since)
        ) or 0
        starts = await session.scalar(
            select(func.count(Event.id))
            .where(Event.event == "bot_start")
            .where(Event.occurred_at >= since)
        )
        vitaconsult = await get_flag(session, FLAG_VITACONSULT_PUBLIC, default=False)

    text = (
        "📊 Админка · последние 30 дней\n\n"
        f"Старты /start: {starts or 0}\n"
        f"Новые заявки: {new_apps or 0}\n"
        f"Оплаты: {paid or 0}\n"
        f"Выручка: {revenue_kop / 100:,.0f} ₽\n\n"
        f"VITACONSULT_PUBLIC: {'✅ включено' if vitaconsult else '❌ выключено'}"
    )
    toggle_label = (
        "🔒 Выключить VITACONSULT" if vitaconsult else "🔓 Включить VITACONSULT"
    )
    markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(toggle_label, callback_data="admin:toggle_vitaconsult")],
            [InlineKeyboardButton("← В меню", callback_data="menu:main")],
        ]
    )
    await update.effective_message.reply_text(text, reply_markup=markup)


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    action = (query.data or "").split(":", 1)[1] if ":" in (query.data or "") else ""
    if action == "toggle_vitaconsult":
        factory = async_session_factory()
        async with factory() as session:
            current = await get_flag(session, FLAG_VITACONSULT_PUBLIC, default=False)
            await set_flag(
                session, FLAG_VITACONSULT_PUBLIC, enabled=not current, actor=str(user_id)
            )
            await session.commit()
            new_value = not current
        await query.message.reply_text(
            f"VITACONSULT_PUBLIC = {'✅ true' if new_value else '❌ false'}"
        )
