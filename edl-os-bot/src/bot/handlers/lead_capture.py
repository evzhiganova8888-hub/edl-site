"""Общий FSM для сбора заявок (demo / diagnostic / sprint_waitlist).

Минимум для квалификации: ниша (из сегмента), email/телефон для связи,
размер компании, главная боль. После сбора → бриф Ивану + ответ
пользователю с конкретным SLA по сегменту.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from src.bot import keyboards, texts
from src.bot.handlers import consent as consent_handler
from src.core import consent as consent_core
from src.core.config import settings
from src.core.contact import normalize_email, normalize_phone
from src.core.handoff import get_rule, handoff_phrase
from src.core.notifications import build_lead_brief, send_to_admin_chat
from src.db.models import Application
from src.db.repos import (
    create_application,
    get_or_create_user,
    log_event,
    log_message,
    log_pd_access,
)
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

KEY_FLOW = "lead_flow_state"
KEY_TYPE = "lead_flow_type"
KEY_APP_ID = "lead_flow_application_id"
KEY_CONTEXT = "lead_flow_context"

STEP_ASK_PAIN = "ask_pain"
STEP_ASK_CONTACT = "ask_contact"


_INTRO_BY_TYPE = {
    "demo": texts.DEMO_INTRO,
    "diagnostic": texts.DIAGNOSTIC_INTRO,
    "sprint_waitlist": texts.SPRINT_WAITLIST_INTRO,
    "hero_summary": (
        "Видели интерактивную сводку на сайте — хотите такую же для своего "
        "бизнеса? В Чекапе мы делаем её для вашей компании. Расскажите немного "
        "о бизнесе, и я приглашу к Чекапу."
    ),
}

_PAIN_PROMPT = (
    "Расскажите, что сейчас болит больше всего? Можно в свободной форме — "
    "например: «теряем маржу по проектам», «не вижу cash-flow на месяц вперёд», "
    "«команда растёт, я тону в операционке»."
)


async def start_flow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    flow_type: str,
) -> None:
    """Стартует сбор заявки по типу demo/diagnostic/sprint_waitlist/hero_summary."""
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        if not consent_core.has_consent(user):
            await session.commit()
            await consent_handler.request_consent(update)
            return
        application = await create_application(
            session,
            user=user,
            type=flow_type,
            source=f"{flow_type}_intent",
        )
        await log_event(
            session,
            user_id=user.id,
            event=f"{flow_type}_started",
            payload={"application_id": str(application.id)},
        )
        await session.commit()
        application_id = str(application.id)

    context.user_data[KEY_TYPE] = flow_type
    context.user_data[KEY_APP_ID] = application_id
    context.user_data[KEY_FLOW] = STEP_ASK_PAIN

    intro = _INTRO_BY_TYPE.get(flow_type, texts.DEMO_INTRO)
    await update.effective_message.reply_text(intro)
    await update.effective_message.reply_text(_PAIN_PROMPT)


async def handle_text_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    state = context.user_data.get(KEY_FLOW)
    if state not in (STEP_ASK_PAIN, STEP_ASK_CONTACT):
        return False

    text = (update.effective_message.text or "").strip()
    if not text:
        return True

    if state == STEP_ASK_PAIN:
        context.user_data[KEY_CONTEXT] = text[:500]
        context.user_data[KEY_FLOW] = STEP_ASK_CONTACT
        await _ask_contact(update, context)
        return True

    if state == STEP_ASK_CONTACT:
        email = normalize_email(text)
        phone = normalize_phone(text)
        if not email and not phone and not text.startswith("@"):
            await update.effective_message.reply_text(
                "Не разобрала — нужен email, телефон или TG-username (через @). "
                "Попробуйте ещё раз."
            )
            return True

        flow_type = context.user_data.get(KEY_TYPE) or "demo"
        application_id = context.user_data.get(KEY_APP_ID)
        pain_context = context.user_data.get(KEY_CONTEXT, "")

        factory = async_session_factory()
        async with factory() as session:
            user, _ = await get_or_create_user(
                session,
                telegram_id=update.effective_user.id,
                username=update.effective_user.username,
            )
            fields_updated = []
            if email:
                user.email = email
                fields_updated.append("email")
            if phone:
                user.phone = phone
                fields_updated.append("phone")
            if fields_updated:
                await log_pd_access(
                    session,
                    actor=str(update.effective_user.id),
                    user_id=user.id,
                    action="update",
                    fields=fields_updated,
                )

            stmt = select(Application).where(Application.id == UUID(application_id))
            app = (await session.execute(stmt)).scalar_one_or_none()
            if app:
                app.status = "qualified"
                app.payload = {
                    **(app.payload or {}),
                    "pain": pain_context,
                    "contact_kind": "email" if email else ("phone" if phone else "tg"),
                }
            await log_message(
                session,
                user_id=user.id,
                direction="inbound",
                text="[contact collected]",
            )
            await log_event(
                session,
                user_id=user.id,
                event=f"{flow_type}_qualified",
                payload={"application_id": application_id},
            )
            await session.commit()

            brief = build_lead_brief(user=user, application=app, extra_context=pain_context)

        # Чистим FSM
        for k in (KEY_FLOW, KEY_TYPE, KEY_APP_ID, KEY_CONTEXT):
            context.user_data.pop(k, None)

        rule = get_rule(user.segment if user.segment else "other")
        phrase = handoff_phrase(user.segment)
        outro = (
            "Спасибо. Заявка передана Ивану.\n\n"
            f"{phrase}\n\n"
            f"Канал ответа: {_describe_channel(rule.channel)}.\n"
            f"Прямая связь, если срочно: @{settings.sales_username}."
        )
        await update.effective_message.reply_text(outro, reply_markup=keyboards.main_menu())

        try:
            await send_to_admin_chat(context.bot, brief)
        except Exception:
            logger.exception("send_to_admin_chat failed")
        return True

    return False


async def _ask_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        segment = user.segment or "other"
        await session.commit()

    rule = get_rule(segment)
    if rule.channel == "phone_or_email":
        prompt = "Напишите телефон или email — Иван свяжется в течение 4 рабочих часов."
    elif rule.channel == "direct_dm":
        prompt = (
            "Напишите ваш Telegram (через @) или email. Иван свяжется в "
            "течение часа в рабочее окно."
        )
    else:
        prompt = (
            "Напишите Telegram (через @) или email. Иван свяжется в течение "
            "24 рабочих часов."
        )
    await update.effective_message.reply_text(prompt)


def _describe_channel(channel: str) -> str:
    return {
        "phone_or_email": "телефон или email",
        "direct_dm": "@lvanKhudyakov напрямую",
        "tg_or_email": "Telegram или email",
    }.get(channel, "Telegram или email")
