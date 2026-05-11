"""/audit и /audit_sample — Бизнес-чекап (§7.4, §7.5 ТЗ v3).

Полный flow Этапа 2:
1. Согласие на ПД (§13)
2. Сбор контактов: ФИО → email → компания (FSM в context.user_data)
3. Принятие оферты
4. Robokassa invoice URL → пользователь оплачивает на стороне
5. ResultURL callback (см. main.py) переводит status=paid + шлёт бриф Ивану
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from src.bot import keyboards, texts
from src.bot.handlers import consent as consent_handler
from src.core import consent as consent_core
from src.core import offer as offer_core
from src.core.config import settings
from src.core.contact import normalize_company, normalize_email, normalize_full_name
from src.core.payments import RobokassaClient
from src.core.payments.robokassa import RobokassaInvoice
from src.db.models import Application, Payment
from src.db.repos import (
    create_application,
    get_or_create_user,
    log_event,
    log_message,
    log_pd_access,
)
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

_AUDIT_SAMPLE_PDF = (
    Path(__file__).resolve().parent.parent.parent.parent / "assets" / "audit_sample.pdf"
)

AUDIT_AMOUNT_RUB = 9000.0

# FSM keys в context.user_data
KEY_FLOW = "audit_flow_state"
KEY_APP_ID = "audit_application_id"

FLOW_AWAIT_FULL_NAME = "await_full_name"
FLOW_AWAIT_EMAIL = "await_email"
FLOW_AWAIT_COMPANY = "await_company"


# ----------------------------- /audit -----------------------------


async def audit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await log_event(session, user_id=user.id, event="audit_intro_shown")
        await session.commit()

    await update.effective_message.reply_text(
        texts.AUDIT_INTRO, reply_markup=keyboards.audit_pay_keyboard()
    )


async def audit_sample_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await log_event(session, user_id=user.id, event="audit_sample_requested")
        await session.commit()

    if _AUDIT_SAMPLE_PDF.exists():
        await update.effective_message.reply_text(texts.AUDIT_SAMPLE_INTRO)
        with _AUDIT_SAMPLE_PDF.open("rb") as f:
            await update.effective_message.reply_document(
                document=f, filename="EDL_OS_audit_sample.pdf"
            )
    else:
        await update.effective_message.reply_text(
            texts.AUDIT_SAMPLE_NOT_READY,
            reply_markup=keyboards.audit_pay_keyboard(),
        )


# --------------------- Callback: start purchase -------------------


async def start_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Колбэк `audit:start_purchase` — старт сбора контактов."""
    query = update.callback_query
    await query.answer()

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)

        # Шаг 1 — проверка согласия
        if not consent_core.has_consent(user):
            await session.commit()
            await consent_handler.request_consent(update)
            return

        # Создаём заявку (paid=false пока)
        application = await create_application(
            session,
            user=user,
            type="audit",
            source="purchase_intent",
        )
        await log_event(
            session,
            user_id=user.id,
            event="audit_purchase_started",
            payload={"application_id": str(application.id)},
        )
        await session.commit()
        application_id = str(application.id)

    context.user_data[KEY_APP_ID] = application_id
    context.user_data[KEY_FLOW] = FLOW_AWAIT_FULL_NAME

    await query.message.reply_text(texts.AUDIT_PURCHASE_START)
    await query.message.reply_text(
        texts.ASK_FULL_NAME, reply_markup=keyboards.cancel_collection_keyboard()
    )


async def cancel_collection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data.pop(KEY_FLOW, None)
    context.user_data.pop(KEY_APP_ID, None)
    await query.message.reply_text(texts.CANCELLED_COLLECTION, reply_markup=keyboards.main_menu())


# -------------------- FSM text input handler ----------------------


async def handle_text_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Обрабатывает FSM-шаг audit. Возвращает True если шаг был обработан."""
    state = context.user_data.get(KEY_FLOW)
    if state not in (FLOW_AWAIT_FULL_NAME, FLOW_AWAIT_EMAIL, FLOW_AWAIT_COMPANY):
        return False

    text = (update.effective_message.text or "").strip()
    application_id = context.user_data.get(KEY_APP_ID)
    if not application_id:
        context.user_data.pop(KEY_FLOW, None)
        return False

    if state == FLOW_AWAIT_FULL_NAME:
        full_name = normalize_full_name(text)
        if not full_name:
            await update.effective_message.reply_text(
                texts.INVALID_FULL_NAME, reply_markup=keyboards.cancel_collection_keyboard()
            )
            return True
        parts = full_name.split()
        last_name = parts[0]
        first_name = " ".join(parts[1:]) if len(parts) > 1 else None

        factory = async_session_factory()
        async with factory() as session:
            user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
            user.last_name = last_name
            user.first_name = first_name
            await log_pd_access(
                session,
                actor=str(update.effective_user.id),
                user_id=user.id,
                action="update",
                fields=["first_name", "last_name"],
            )
            await log_message(
                session, user_id=user.id, direction="inbound", text="[FIO collected]"
            )
            await session.commit()

        context.user_data[KEY_FLOW] = FLOW_AWAIT_EMAIL
        await update.effective_message.reply_text(
            texts.ASK_EMAIL, reply_markup=keyboards.cancel_collection_keyboard()
        )
        return True

    if state == FLOW_AWAIT_EMAIL:
        email = normalize_email(text)
        if not email:
            await update.effective_message.reply_text(
                texts.INVALID_EMAIL, reply_markup=keyboards.cancel_collection_keyboard()
            )
            return True

        factory = async_session_factory()
        async with factory() as session:
            user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
            user.email = email
            await log_pd_access(
                session,
                actor=str(update.effective_user.id),
                user_id=user.id,
                action="update",
                fields=["email"],
            )
            await log_message(
                session, user_id=user.id, direction="inbound", text="[email collected]"
            )
            await session.commit()

        context.user_data[KEY_FLOW] = FLOW_AWAIT_COMPANY
        await update.effective_message.reply_text(
            texts.ASK_COMPANY, reply_markup=keyboards.cancel_collection_keyboard()
        )
        return True

    if state == FLOW_AWAIT_COMPANY:
        company = normalize_company(text)
        if not company:
            await update.effective_message.reply_text(
                texts.INVALID_COMPANY, reply_markup=keyboards.cancel_collection_keyboard()
            )
            return True

        factory = async_session_factory()
        async with factory() as session:
            user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
            user.company_name = company
            await log_pd_access(
                session,
                actor=str(update.effective_user.id),
                user_id=user.id,
                action="update",
                fields=["company_name"],
            )
            await log_message(
                session, user_id=user.id, direction="inbound", text="[company collected]"
            )
            await session.commit()

        # Контакты собраны — теперь оферта
        context.user_data.pop(KEY_FLOW, None)
        await _show_offer(update, context)
        return True

    return False


async def _show_offer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        f"{texts.OFFER_HEADER}\n\n{offer_core.offer_summary()}",
        reply_markup=keyboards.offer_keyboard(),
        disable_web_page_preview=True,
    )


# ---------------------- Offer accept callbacks --------------------


async def handle_offer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    decision = (query.data or "").split(":", 1)[1] if ":" in (query.data or "") else "decline"

    if decision != "accept":
        await query.message.reply_text(texts.CANCELLED_COLLECTION, reply_markup=keyboards.main_menu())
        return

    application_id = context.user_data.get(KEY_APP_ID)
    if not application_id:
        await query.message.reply_text(
            "Сессия покупки сбросилась. /audit — начнём заново.",
            reply_markup=keyboards.main_menu(),
        )
        return

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await offer_core.accept_offer(session, user)
        await session.commit()

    await _send_invoice(update, context, application_id)


# ----------------------- Build invoice URL ------------------------


async def _send_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, application_id: str) -> None:
    client = RobokassaClient()
    if not client.configured:
        await update.effective_message.reply_text(
            texts.PAYMENT_NOT_CONFIGURED, reply_markup=keyboards.main_menu()
        )
        # Регистрируем заявку как qualified для ручной обработки
        factory = async_session_factory()
        async with factory() as session:
            stmt = select(Application).where(Application.id == UUID(application_id))
            app = (await session.execute(stmt)).scalar_one_or_none()
            if app:
                app.status = "qualified"
            user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
            await log_event(
                session,
                user_id=user.id,
                event="audit_payment_skipped_unconfigured",
                payload={"application_id": application_id},
            )
            await session.commit()
        return

    factory = async_session_factory()
    async with factory() as session:
        stmt = select(Application).where(Application.id == UUID(application_id))
        app = (await session.execute(stmt)).scalar_one_or_none()
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        if app is None:
            await update.effective_message.reply_text(
                "Заявка не найдена. /audit — попробуем ещё раз."
            )
            return
        invoice = RobokassaInvoice(
            inv_id=app.inv_id,
            amount_rub=AUDIT_AMOUNT_RUB,
            description="Бизнес-чекап EDL OS · аналитический отчёт + видео-разбор",
            email=user.email,
            user_telegram_id=user.telegram_id,
        )
        url = client.build_invoice_url(invoice)

        # Создаём pending платёж
        session.add(
            Payment(
                application_id=app.id,
                user_id=user.id,
                amount_kopecks=int(AUDIT_AMOUNT_RUB * 100),
                currency="RUB",
                provider="robokassa",
                provider_invoice_id=str(app.inv_id),
                status="pending",
            )
        )
        await log_event(
            session,
            user_id=user.id,
            event="audit_invoice_created",
            payload={"application_id": application_id, "inv_id": app.inv_id},
        )
        await session.commit()

    await update.effective_message.reply_text(
        texts.PAYMENT_LINK_READY, reply_markup=keyboards.audit_pay_keyboard(invoice_url=url)
    )
