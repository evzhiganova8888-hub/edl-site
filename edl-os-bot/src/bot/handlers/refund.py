"""/refund — запрос возврата (§7.10 ТЗ v3 + §D.6 v3.1 — 1-click).

V3.1: возврат подаётся в 1 клик. Причина — опциональная, post-action,
не блокирует процесс. Mutualism: «деньги ваши, забирайте — расскажете
причину потом, если захотите».
"""
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
from src.db.models import Application, Payment, Refund
from src.db.repos import get_or_create_user, log_event
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

# Опциональный сбор причины ПОСЛЕ того, как возврат уже подан.
KEY_REFUND_COMMENT_REFUND_ID = "refund_pending_comment_refund_id"


async def refund_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает активные заявки с правом на возврат + кнопку 1-click."""
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

    deadline = active.refund_eligible_until.strftime("%d.%m.%Y %H:%M") if active.refund_eligible_until else "—"
    await update.effective_message.reply_text(
        "Доступен возврат за Бизнес-чекап.\n"
        f"Окно действует до {deadline} (UTC).\n\n"
        "Один клик — возврат подаётся. Причину расскажете потом, если захотите.",
        reply_markup=keyboards.refund_keyboard(str(active.id)),
    )


async def handle_refund_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback `refund:request:<application_id>` — 1-click возврат.

    Сразу создаём Refund(status=requested), уведомляем Ивана, спрашиваем
    причину как опциональный post-action (Mutualism, §D.6 v3.1).
    """
    query = update.callback_query
    await query.answer()
    parts = (query.data or "").split(":")
    if len(parts) < 3:
        return
    application_id = parts[2]

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        stmt = select(Application).where(Application.id == UUID(application_id))
        app = (await session.execute(stmt)).scalar_one_or_none()
        if not app:
            await query.message.reply_text(
                texts.REFUND_NO_ACTIVE, reply_markup=keyboards.main_menu()
            )
            return

        # Проверка окна 14 дней — повторно, на случай гонки
        now = datetime.now(timezone.utc)
        if app.refund_eligible_until and app.refund_eligible_until < now:
            await query.message.reply_text(
                texts.REFUND_WINDOW_CLOSED, reply_markup=keyboards.main_menu()
            )
            return

        # Dedup: не создаём второй refund по той же заявке
        existing = (
            await session.execute(
                select(Refund)
                .join(Payment, Refund.payment_id == Payment.id)
                .where(Payment.application_id == app.id)
                .where(Refund.status.in_(["requested", "completed"]))
            )
        ).scalars().first()
        if existing:
            await query.message.reply_text(
                "Возврат по этой заявке уже подан. Иван свяжется по дальнейшим шагам.\n"
                f"Если срочно — @{settings.sales_username}.",
                reply_markup=keyboards.main_menu(),
            )
            return

        pay_stmt = (
            select(Payment)
            .where(Payment.application_id == app.id)
            .where(Payment.status == "succeeded")
        )
        payment = (await session.execute(pay_stmt)).scalars().first()

        refund = None
        if payment:
            refund = Refund(
                payment_id=payment.id,
                user_id=user.id,
                status="requested",
                reason=None,
            )
            session.add(refund)
            await session.flush()
        app.status = "refund_requested"
        await log_event(
            session,
            user_id=user.id,
            event="refund_requested",
            payload={
                "application_id": application_id,
                "via": "one_click",
                "refund_id": str(refund.id) if refund else None,
            },
        )
        await session.commit()

        brief = build_refund_request_brief(
            user=user, application=app, reason="(причина не указана — 1-click)"
        )
        refund_id = str(refund.id) if refund else None

    # Сообщаем юзеру + предлагаем (необязательно) рассказать причину
    if refund_id:
        context.user_data[KEY_REFUND_COMMENT_REFUND_ID] = refund_id
        await query.message.reply_text(
            "✅ Возврат подаётся. Средства вернутся на карту в течение "
            "5 рабочих дней с момента подтверждения Иваном в Robokassa.\n\n"
            "Если хотите рассказать причину — напишите ниже одним сообщением. "
            "Нам важно, но это необязательно.\n\n"
            f"Если что — @{settings.sales_username}.",
            reply_markup=keyboards.bug_report_skip_keyboard(),
        )
    else:
        await query.message.reply_text(
            "Запрос принят. Иван свяжется по деталям возврата.\n"
            f"Если срочно — @{settings.sales_username}.",
            reply_markup=keyboards.main_menu(),
        )

    # Бриф Ивану — сразу, не ждём причины
    try:
        await send_to_admin_chat(context.bot, brief)
    except Exception:
        logger.exception("send_to_admin_chat failed")


async def handle_text_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Опциональный post-action: пользователь захотел рассказать причину.

    Если он молчит / отвечает «нет» — мы ничего не блокируем.
    """
    refund_id = context.user_data.get(KEY_REFUND_COMMENT_REFUND_ID)
    if not refund_id:
        return False

    text = (update.effective_message.text or "").strip()
    context.user_data.pop(KEY_REFUND_COMMENT_REFUND_ID, None)

    if not text:
        return True

    factory = async_session_factory()
    async with factory() as session:
        row = (
            await session.execute(select(Refund).where(Refund.id == UUID(refund_id)))
        ).scalar_one_or_none()
        if row:
            row.reason = text[:2000]
            await log_event(
                session,
                user_id=row.user_id,
                event="refund_reason_added",
                payload={"refund_id": refund_id, "reason": text[:200]},
            )
            await session.commit()
    await update.effective_message.reply_text("Спасибо, добавил к заявке возврата.")
    return True
