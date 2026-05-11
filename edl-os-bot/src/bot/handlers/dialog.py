"""Свободный диалог через Anthropic Claude Haiku 4.5.

В LLM передаём только обезличенный текст (см. core/pd_sanitize.py).
На Этапе 1 — если ANTHROPIC_API_KEY не задан, бот отвечает заглушкой
и предлагает hand-off.
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.bot import texts
from src.core import llm
from src.core.config import settings
from src.core.pd_sanitize import contains_pd
from src.core.segment import detect_sub_profile, detect_from_text
from src.db.repos import get_or_create_user, log_event, log_message
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

_HISTORY_KEY = "chat_history"
_MAX_HISTORY = 8


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not msg.text:
        return

    user_text = msg.text.strip()

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        # Если сегмент не задан, попробуем по маркер-словам
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
        # Под-профиль
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
        await session.commit()
        segment = user.segment or "other"
        stage = user.stage or "cold"

    # Если ключа нет — простая безопасная отбивка
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
                user_text=user_text, segment=segment, stage=stage, history=history
            )
            history = (history + [
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": answer},
            ])[-_MAX_HISTORY:]
            context.user_data[_HISTORY_KEY] = history
        except Exception:
            logger.exception("LLM call failed")
            answer = texts.ERROR_GENERIC
            tokens = 0

    await msg.reply_text(answer)

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await log_message(
            session,
            user_id=user.id,
            direction="outbound",
            text=answer,
            llm_tokens=tokens if "tokens" in locals() else None,
        )
        if contains_pd(user_text):
            await log_event(
                session,
                user_id=user.id,
                event="pd_in_inbound_text",
                payload={"sanitized": True},
            )
        await session.commit()
