"""/audit и /audit_sample — Бизнес-чекап.

Полный flow:
1. Согласие на ПД
2. Сбор контактов: ФИО → email → компания (FSM в context.user_data)
3. Принятие оферты
4. stub-режим: бриф Ивану в Sales-чат + status=awaiting_manual_payment
5. Иван помечает оплату через /mark_paid — юзер получает уведомление + /checkup
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
from src.core.input_validation import InputValidationError, validate_user_text
from src.core.notifications import build_manual_payment_brief, send_to_admin_chat
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

_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "assets"
_AUDIT_SAMPLE_PDF = _ASSETS_DIR / "audit_sample.pdf"
_AUDIT_SAMPLE_HTML = _ASSETS_DIR / "audit_sample.html"

AUDIT_AMOUNT_RUB = 9000.0
AUDIT_PLUS_AMOUNT_RUB = 14000.0

PLAN_BASE = "base"
PLAN_PLUS = "plus"

# FSM keys в context.user_data
KEY_FLOW = "audit_flow_state"
KEY_APP_ID = "audit_application_id"
KEY_PLAN = "audit_plan"

FLOW_AWAIT_FULL_NAME = "await_full_name"
FLOW_AWAIT_EMAIL = "await_email"
FLOW_AWAIT_COMPANY = "await_company"


def _plan_amount(plan: str) -> float:
    return AUDIT_PLUS_AMOUNT_RUB if plan == PLAN_PLUS else AUDIT_AMOUNT_RUB


def _plan_description(plan: str) -> str:
    if plan == PLAN_PLUS:
        return "Бизнес-чекап Plus EDL OS · отчёт + видео-разбор от Кати"
    return "Бизнес-чекап EDL OS · аналитический отчёт по 4 слоям"


# ----------------------------- /audit -----------------------------


async def audit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await log_event(session, user_id=user.id, event="audit_intro_shown")
        await session.commit()

    await update.effective_message.reply_text(
        texts.AUDIT_INTRO,
        parse_mode="Markdown",
        reply_markup=keyboards.audit_pay_keyboard(),
    )


async def audit_sample_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await log_event(session, user_id=user.id, event="audit_sample_requested")
        await session.commit()

    # PDF — основной формат; HTML — fallback, когда PDF ещё не сделан.
    # Шлём ОДИН файл, не оба (P2 fix QA v3.1).
    sent_any = False
    if _AUDIT_SAMPLE_PDF.exists():
        await update.effective_message.reply_text(texts.AUDIT_SAMPLE_INTRO)
        with _AUDIT_SAMPLE_PDF.open("rb") as f:
            await update.effective_message.reply_document(
                document=f, filename="EDL_OS_audit_sample.pdf"
            )
        sent_any = True
    elif _AUDIT_SAMPLE_HTML.exists():
        await update.effective_message.reply_text(texts.AUDIT_SAMPLE_INTRO)
        with _AUDIT_SAMPLE_HTML.open("rb") as f:
            await update.effective_message.reply_document(
                document=f, filename="EDL_OS_audit_sample.html"
            )
        sent_any = True
    if not sent_any:
        await update.effective_message.reply_text(
            texts.AUDIT_SAMPLE_NOT_READY,
            reply_markup=keyboards.waitlist_keyboard("audit_pdf"),
        )
        return
    # CTA после превью
    await update.effective_message.reply_text(
        "Это обезличенный пример. Ваш отчёт будет содержать цифры именно "
        "по вашей компании. Заказать свой Чекап ниже.",
        reply_markup=keyboards.audit_pay_keyboard(),
    )


# --------------------- Callback: start purchase -------------------


async def start_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Колбэк `audit:start_purchase:<plan>` — старт сбора контактов.

    plan ∈ {base, plus}. base — Чекап 9 000 ₽, plus — 14 000 ₽ с видео.
    """
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    parts = data.split(":")
    plan = parts[2] if len(parts) >= 3 and parts[2] in (PLAN_BASE, PLAN_PLUS) else PLAN_BASE

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
            payload={"plan": plan},
        )
        await log_event(
            session,
            user_id=user.id,
            event="audit_purchase_started",
            payload={"application_id": str(application.id), "plan": plan},
        )
        await session.commit()
        application_id = str(application.id)

    context.user_data[KEY_APP_ID] = application_id
    context.user_data[KEY_PLAN] = plan
    context.user_data[KEY_FLOW] = FLOW_AWAIT_FULL_NAME

    plan_label = "Plus · 14 000 ₽" if plan == PLAN_PLUS else "Базовый · 9 000 ₽"
    await query.message.reply_text(
        f"Хорошо, оформляем Бизнес-чекап {plan_label}.\n\n"
        "Соберу минимум — ФИО, email для чека и название компании. "
        "Это нужно для договора и фискального чека (54-ФЗ)."
    )
    await query.message.reply_text(
        texts.ASK_FULL_NAME, reply_markup=keyboards.cancel_collection_keyboard()
    )


async def cancel_collection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data.pop(KEY_FLOW, None)
    context.user_data.pop(KEY_APP_ID, None)
    await query.message.reply_text(texts.CANCELLED_COLLECTION, reply_markup=keyboards.main_menu())


async def notify_waiting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Колбэк audit:notify_waiting — юзер хочет уведомление при активации."""
    query = update.callback_query
    await query.answer(
        "Хорошо, пришлю уведомление как только статус заявки изменится на paid.",
        show_alert=False,
    )
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await log_event(
            session,
            user_id=user.id,
            event="audit_user_subscribed_to_paid_event",
        )
        await session.commit()


# -------------------- FSM text input handler ----------------------


async def handle_text_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Обрабатывает FSM-шаг audit. Возвращает True если шаг был обработан."""
    state = context.user_data.get(KEY_FLOW)
    if state not in (FLOW_AWAIT_FULL_NAME, FLOW_AWAIT_EMAIL, FLOW_AWAIT_COMPANY):
        return False

    # Валидация на длину/control chars (§C.9 v3.1)
    try:
        text = validate_user_text((update.effective_message.text or "").strip())
    except InputValidationError as e:
        await update.effective_message.reply_text(
            str(e), reply_markup=keyboards.cancel_collection_keyboard()
        )
        return True

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


async def _plan_from_application(app: Application | None) -> str:
    """Plan — единый источник истины: Application.payload['plan']."""
    if app is None:
        return PLAN_BASE
    payload = app.payload or {}
    plan = payload.get("plan", PLAN_BASE)
    return plan if plan in (PLAN_BASE, PLAN_PLUS) else PLAN_BASE


async def _handoff_manual_payment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    application_id: str,
    plan: str,
    amount: float,
) -> None:
    """Manual-payment режим: бот собрал данные, передаёт Ивану в Sales-чат
    для ручного оформления счёта через бухгалтерию.

    Юзеру шлём MANUAL_PAYMENT_SUBMITTED. Application.status = awaiting_manual_payment.
    """
    factory = async_session_factory()
    async with factory() as session:
        stmt = select(Application).where(Application.id == UUID(application_id))
        app = (await session.execute(stmt)).scalar_one_or_none()
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        if app is None:
            await update.effective_message.reply_text(
                "Заявка не найдена. /audit — попробуем ещё раз.",
                reply_markup=keyboards.main_menu(),
            )
            return

        app.status = "awaiting_manual_payment"
        await log_event(
            session,
            user_id=user.id,
            event="manual_payment_submitted",
            payload={
                "application_id": application_id,
                "inv_id": app.inv_id,
                "plan": plan,
                "amount_rub": amount,
            },
        )

        full_name = " ".join(
            filter(None, [user.last_name, user.first_name])
        ).strip() or None
        brief = build_manual_payment_brief(
            user=user,
            application=app,
            plan=plan,
            amount_rub=amount,
            full_name=full_name,
            company=user.company_name,
        )
        await session.commit()

    await update.effective_message.reply_text(
        texts.MANUAL_PAYMENT_SUBMITTED,
        reply_markup=keyboards.payment_submitted_keyboard(),
        disable_web_page_preview=True,
    )

    try:
        await send_to_admin_chat(context.bot, brief)
    except Exception:
        logger.exception("manual_payment: send_to_admin_chat failed")


async def _send_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, application_id: str) -> None:
    # P0-3 fix: читаем plan из БД, не из context (context мог истечь / /reset).
    factory = async_session_factory()
    async with factory() as session:
        stmt = select(Application).where(Application.id == UUID(application_id))
        app = (await session.execute(stmt)).scalar_one_or_none()
        plan = await _plan_from_application(app)
    amount = _plan_amount(plan)

    # stub / manual — бот собирает данные, шлёт бриф Ивану, тот оформляет счёт.
    if settings.payment_mode in ("stub", "manual"):
        await _handoff_manual_payment(update, context, application_id, plan, amount)
        return

    # yookassa — пока не реализовано, fallback в stub
    await _handoff_manual_payment(update, context, application_id, plan, amount)
