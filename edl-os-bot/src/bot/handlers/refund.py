"""/refund — запрос возврата (§7.10 ТЗ v3 + §D.6 v3.1).

Гарантия возврата 14 дней — УСЛОВНАЯ (а не «безусловная»):
работает только при выполнении ОБОИХ условий одновременно:
1. ответы в Чекапе прошли рубрику качества (см. KB 08_checkup_quality_rubric);
2. ни одну из рекомендаций отчёта клиент не может реализовать в компании.

Контекст для реалистичности рекомендаций собирается во время Чекапа —
поэтому условие №2 выполнимо только при честных ответах.

Заявка подаётся в боте, Иван проверяет соответствие условиям и подтверждает
возврат в Robokassa. Причина указывается в свободной форме.
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
        "Окно возврата по Бизнес-чекапу открыто.\n"
        f"Действует до {deadline} (UTC).\n\n"
        "Гарантия возврата — *условная* и работает при выполнении ОБОИХ "
        "условий одновременно:\n"
        "1) ваши ответы прошли рубрику качества Чекапа "
        "(минимум слов и хотя бы одна цифра на каждый вопрос);\n"
        "2) ни одну из 5 (Base) / 7 (Plus) рекомендаций отчёта вы не можете "
        "реализовать в вашей компании.\n\n"
        "Контекст для реалистичности рекомендаций мы собираем во время самого "
        "Чекапа — поэтому условие №2 выполнимо только при честных ответах.\n\n"
        "Если оба условия выполняются — оформите заявку кнопкой ниже и "
        "коротко опишите, какие рекомендации и почему не применимы. "
        "Иван проверит и подтвердит возврат в Robokassa в течение 1 рабочего "
        "часа, средства поступят на карту до 5 рабочих дней.",
        reply_markup=keyboards.refund_keyboard(str(active.id)),
    )


async def handle_refund_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback `refund:request:<application_id>` — заявка на возврат.

    Создаём Refund(status=requested) и уведомляем Ивана. Просим клиента
    обязательно описать одним сообщением, какие рекомендации и почему он
    не может реализовать (это условие №2 гарантии). Иван валидирует
    и подтверждает возврат в Robokassa.
    """
    query = update.callback_query
    await query.answer()
    parts = (query.data or "").split(":")
    if len(parts) < 3:
        return
    application_id = parts[2]
    try:
        app_uuid = UUID(application_id)
    except (ValueError, TypeError):
        # Защита от malformed callback (старая клавиатура / искажённый payload).
        # Молча возвращаем в меню — лучше, чем сорваться в _global_error_handler.
        await query.message.reply_text(
            texts.REFUND_NO_ACTIVE, reply_markup=keyboards.main_menu()
        )
        return

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        stmt = select(Application).where(Application.id == app_uuid)
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

        # Dedup: не создаём второй refund. Учитываем все нон-терминальные
        # статусы (включая processing/failed — failed может быть retry'ed
        # Иваном вручную, не пользователем).
        existing = (
            await session.execute(
                select(Refund)
                .join(Payment, Refund.payment_id == Payment.id)
                .where(Payment.application_id == app.id)
                .where(
                    Refund.status.in_(
                        ["requested", "processing", "completed", "failed"]
                    )
                )
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
                "via": "conditional",
                "refund_id": str(refund.id) if refund else None,
            },
        )
        await session.commit()

        brief = build_refund_request_brief(
            user=user,
            application=app,
            reason="(ожидаем обоснование от клиента — какие рекомендации не применимы)",
        )
        refund_id = str(refund.id) if refund else None

    # Сообщаем юзеру и просим обоснование — оно ОБЯЗАТЕЛЬНО для проверки условий.
    if refund_id:
        context.user_data[KEY_REFUND_COMMENT_REFUND_ID] = refund_id
        await query.message.reply_text(
            "✅ Заявка на возврат принята. Чтобы Иван мог подтвердить её — "
            "напишите одним сообщением: какие из рекомендаций отчёта и "
            "почему вы не можете реализовать в вашей компании.\n\n"
            "Это условие №2 гарантии — без обоснования возврат не оформляется.\n\n"
            "После подтверждения Иваном средства поступят на карту в течение "
            "5 рабочих дней.\n\n"
            f"Если есть вопросы — @{settings.sales_username}.",
            reply_markup=keyboards.main_menu(),
        )
    else:
        await query.message.reply_text(
            "Заявка зафиксирована. Иван свяжется по деталям возврата.\n"
            f"Если срочно — @{settings.sales_username}.",
            reply_markup=keyboards.main_menu(),
        )

    # Бриф Ивану — сразу, дальше дополним причиной от клиента
    try:
        await send_to_admin_chat(context.bot, brief)
    except Exception:
        logger.exception("send_to_admin_chat failed")


async def handle_text_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Сбор обязательного обоснования возврата (условие №2 гарантии).

    Клиент должен описать, какие рекомендации и почему не применимы.
    Текст сохраняется в Refund.reason — Иван валидирует условие до
    подтверждения возврата.
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
    await update.effective_message.reply_text(
        "Принял обоснование. Иван проверит соответствие условиям "
        "гарантии и свяжется с вами в течение рабочего часа."
    )
    return True
