"""/admin команда для команды EDL (Катя, Иван) — сводка + toggle.

Доступ — только telegram_id из ADMIN_USER_IDS.
Toggle VITACONSULT_PUBLIC требует обязательной причины (§C.6 v3.1).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.admin.auth import is_admin
from src.core.flags import FLAG_VITACONSULT_PUBLIC, get_flag, set_flag
from src.db.models import Application, BotError, Event, Payment
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

_PENDING_TOGGLE_KEY = "admin_pending_toggle"  # ждём reason для VITACONSULT toggle


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
        unresolved_bugs = await session.scalar(
            select(func.count(BotError.id)).where(BotError.reviewed_at.is_(None))
        ) or 0
        vitaconsult = await get_flag(session, FLAG_VITACONSULT_PUBLIC, default=False)

    text = (
        "📊 Админка · последние 30 дней\n\n"
        f"Старты /start: {starts or 0}\n"
        f"Новые заявки: {new_apps or 0}\n"
        f"Оплаты: {paid or 0}\n"
        f"Выручка: {revenue_kop / 100:,.0f} ₽\n\n"
        f"⚠️ Bug-report'ы (неразобранные): {unresolved_bugs}\n\n"
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
        # Просим причину перед переключением (§C.6 v3.1)
        context.user_data[_PENDING_TOGGLE_KEY] = {
            "key": FLAG_VITACONSULT_PUBLIC,
            "from": current,
            "to": not current,
        }
        await query.message.reply_text(
            f"Готовим переключение VITACONSULT_PUBLIC: "
            f"{'true' if current else 'false'} → "
            f"{'true' if not current else 'false'}.\n\n"
            "Напишите *причину* одним сообщением (≥3 символов). "
            "Без причины toggle не сработает.\n\n"
            "Чтобы отменить — /reset.",
            parse_mode="Markdown",
        )


async def handle_text_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Если админ переключает VITACONSULT и ждём reason — обрабатываем тут."""
    pending = context.user_data.get(_PENDING_TOGGLE_KEY)
    if not pending:
        return False
    user_id = update.effective_user.id
    if not is_admin(user_id):
        # Чужак не должен застрять в admin FSM
        context.user_data.pop(_PENDING_TOGGLE_KEY, None)
        return False

    text = (update.effective_message.text or "").strip()
    if len(text) < 3:
        await update.effective_message.reply_text(
            "Причина слишком короткая. Минимум 3 символа. Попробуйте ещё раз "
            "или /reset для отмены."
        )
        return True

    factory = async_session_factory()
    async with factory() as session:
        await set_flag(
            session, pending["key"], enabled=pending["to"], actor=str(user_id)
        )
        session.add(
            Event(
                user_id=user_id,
                event="feature_flag_toggled",
                payload={
                    "key": pending["key"],
                    "old": pending["from"],
                    "new": pending["to"],
                    "actor_telegram_id": user_id,
                    "reason": text[:500],
                    "via": "telegram_admin",
                },
            )
        )
        await session.commit()
    context.user_data.pop(_PENDING_TOGGLE_KEY, None)
    await update.effective_message.reply_text(
        f"✅ {pending['key']} = {'true' if pending['to'] else 'false'}\n"
        f"Причина зафиксирована в audit-log."
    )
    return True
