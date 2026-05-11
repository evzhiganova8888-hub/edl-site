"""/refund — запрос возврата (§7.10 ТЗ v3)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from src.bot import keyboards, texts
from src.core.config import settings
from src.core.notifications import build_refund_request_brief, send_to_admin_chat
from src.db.models import Application, Refund
from src.db.repos import get_or_create_user, log_event
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

KEY_REFUND_FLOW = "refund_flow_application_id"


async def refund_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает активные заявки с правом на возврат + кнопку."""
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        stmt = (
            select(Application)
            .where(Application.user_id == user.id)
            .where(Application.type == "audit")
            .where(Application.status == "paid")
            .order_by(Application.payment_succeeded_at.desc())
        )
        active = (await session.execute(stmt)).scalars().first()
        await session.commit()

    if not active:
        await update.effective_message.reply_text(
            texts.REFUND_NO_ACTIVE, reply_markup=keyboards.main_menu()
        )
        return

    now = datetime.now(timezone.utc)
    if active.refund_eligible_until and active.refund_eligible_until < now:
        await update.effective_message.reply_text(
            texts.REFUND_WINDOW_CLOSED, reply_markup=keyboards.main_menu()
        )
        return

    await update.effective_message.reply_text(
        "Доступен возврат за Бизнес-чекап. Окно действует до "
        f"{active.refund_eligible_until.strftime('%d.%m.%Y %H:%M')} (UTC).",
        reply_markup=keyboards.refund_keyboard(str(active.id)),
    )


async def handle_refund_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback `refund:request:<application_id>` — спрашиваем причину."""
    query = update.callback_query
    await query.answer()
    parts = (query.data or "").split(":")
    if len(parts) < 3:
        return
    application_id = parts[2]

    context.user_data[KEY_REFUND_FLOW] = application_id
    await query.message.reply_text(texts.REFUND_ASK_REASON)


async def handle_text_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """FSM-шаг refund: ждём причину текстом. True если обработано."""
    application_id = context.user_data.get(KEY_REFUND_FLOW)
    if not application_id:
        return False

    reason = (update.effective_message.text or "").strip()
    context.user_data.pop(KEY_REFUND_FLOW, None)

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        stmt = select(Application).where(Application.id == UUID(application_id))
        app = (await session.execute(stmt)).scalar_one_or_none()
        if not app:
            await update.effective_message.reply_text(
                texts.REFUND_NO_ACTIVE, reply_markup=keyboards.main_menu()
            )
            return True

        # Достаём payment_id (последний succeeded по этой заявке)
        from src.db.models import Payment

        pay_stmt = (
            select(Payment)
            .where(Payment.application_id == app.id)
            .where(Payment.status == "succeeded")
        )
        payment = (await session.execute(pay_stmt)).scalars().first()
        if payment:
            session.add(
                Refund(
                    payment_id=payment.id,
                    user_id=user.id,
                    status="requested",
                    reason=reason,
                )
            )
        app.status = "refund_requested"
        await log_event(
            session,
            user_id=user.id,
            event="refund_requested",
            payload={"application_id": application_id, "reason": reason[:200]},
        )
        await session.commit()

        brief = build_refund_request_brief(user=user, application=app, reason=reason)

    await update.effective_message.reply_text(
        texts.REFUND_REQUESTED + settings.sales_username,
        reply_markup=keyboards.main_menu(),
    )

    # Бриф Ивану
    try:
        await send_to_admin_chat(context.bot, brief)
    except Exception:
        logger.exception("send_to_admin_chat failed")

    return True
