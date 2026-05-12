"""Свободный диалог + FSM-маршрутизатор.

Маршрут текста:
1. audit FSM (сбор контактов / оферта)
2. refund FSM (причина возврата)
3. lead_capture FSM (demo/diagnostic/sprint_waitlist)
4. свободный диалог через Claude Haiku 4.5
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.bot import keyboards, texts
from src.bot.handlers import admin as admin_handler, audit, bug_report, faq, lead_capture, refund
from src.core import llm
from src.core.config import settings
from src.core.flags import FLAG_VITACONSULT_PUBLIC, get_flag
from src.core.pd_sanitize import contains_pd
from src.core.segment import detect_from_text, detect_sub_profile
from src.core.stickers import StickerContext, pick_emoji, should_send_sticker
from src.db.repos import get_or_create_user, log_event, log_message
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

_HISTORY_KEY = "chat_history"
_MAX_HISTORY = 8
_FIRST_RESPONSE_KEY = "first_response_sent"


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not msg.text:
        return

    # 1. FSM checks (порядок важен)
    if await admin_handler.handle_text_step(update, context):
        return
    if await bug_report.handle_text_step(update, context):
        return
    if await audit.handle_text_step(update, context):
        return
    if await refund.handle_text_step(update, context):
        return
    if await lead_capture.handle_text_step(update, context):
        return
    if await faq.handle_text_step(update, context):
        return

    # 2. Свободный диалог
    user_text = msg.text.strip()

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        if not user.segment:
            seg = detect_from_text(user_text)
            if seg:
                user.segment = seg
                await log_event(
                    session,
                    user_id=user.id,
                    event="segment_detected",
                    payload={"segment": seg, "method": "markers"},
                )
        if user.segment and not user.sub_profile:
            sub = detect_sub_profile(user.segment, user_text)
            if sub:
                user.sub_profile = sub

        await log_message(
            session,
            user_id=user.id,
            direction="inbound",
            text=user_text,
            vat_topic_mentioned=any(t in user_text.lower() for t in ("ндс", "vat", "дроблен")),
        )
        vitaconsult = await get_flag(session, FLAG_VITACONSULT_PUBLIC, default=False)
        await session.commit()
        segment = user.segment or "other"
        stage = user.stage or "cold"
        user_id_for_log = user.id

    answer: str
    tokens: int | None = None
    if not settings.anthropic_api_key:
        answer = (
            "Принято. На этом этапе я ещё учусь свободно говорить — модель "
            "подключаем в этом спринте. "
            f"Пока — главное меню: /menu или напишите Ивану: @{settings.sales_username}."
        )
    else:
        try:
            history = context.user_data.get(_HISTORY_KEY, [])
            answer, tokens = await llm.reply(
                user_text=user_text,
                segment=segment,
                stage=stage,
                history=history,
                vitaconsult_public=vitaconsult,
            )
            history = (history + [
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": answer},
            ])[-_MAX_HISTORY:]
            context.user_data[_HISTORY_KEY] = history
        except Exception:
            logger.exception("LLM call failed")
            answer = texts.ERROR_GENERIC

    # 3. Стикер — определяем заранее, чтобы записать в один лог
    sticker_sent = False
    trigger = None if context.user_data.get(_FIRST_RESPONSE_KEY) else "first_response"
    if trigger:
        context.user_data[_FIRST_RESPONSE_KEY] = True
    sticker_ctx = StickerContext(
        channel="tg",
        segment=segment,
        stage=stage,
        trigger=trigger,
        last_response_was_refusal=False,
    )
    send_sticker = should_send_sticker(sticker_ctx)

    # 4. Логируем outbound заранее — получаем id для bug-report кнопки (§E.1 v3.1)
    factory = async_session_factory()
    async with factory() as session:
        out_row = await log_message(
            session,
            user_id=user_id_for_log,
            direction="outbound",
            text=answer,
            llm_tokens=tokens,
            sticker_sent=send_sticker,
        )
        out_id = out_row.id
        if contains_pd(user_text):
            await log_event(
                session,
                user_id=user_id_for_log,
                event="pd_in_inbound_text",
                payload={"sanitized": True},
            )
        await session.commit()

    # 5. Отправляем ответ с кнопкой «⚠️ Ответ неверный» + «К Ивану» (D.2 + E.1)
    await msg.reply_text(answer, reply_markup=keyboards.bug_report_keyboard(out_id))

    if send_sticker:
        try:
            await msg.reply_text(pick_emoji())
            sticker_sent = True
        except Exception:
            logger.exception("send sticker failed")
