"""FAQ — rules-based с поиском по ключевым словам (§7.8 ТЗ v3)."""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.bot import keyboards
from src.core import faq as faq_core
from src.core.config import settings
from src.db.repos import get_or_create_user, log_event
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

KEY_FAQ_MODE = "faq_active"


async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    items = faq_core.all_items()
    if not items:
        await update.effective_message.reply_text(
            "FAQ-база ещё наполняется. Задайте вопрос текстом, я отвечу через ИИ.",
            reply_markup=keyboards.back_to_menu(),
        )
        return

    context.user_data[KEY_FAQ_MODE] = True

    intro = "Частые вопросы. Нажмите номер или напишите вопрос своими словами:"
    buttons = []
    for i, item in enumerate(items, start=1):
        # 2 кнопки в ряд
        if i % 2 == 1:
            buttons.append([])
        buttons[-1].append(
            InlineKeyboardButton(f"{i}. {item.question[:30]}…" if len(item.question) > 30 else f"{i}. {item.question}",
                                  callback_data=f"faq:show:{i}")
        )
    buttons.append([InlineKeyboardButton("💬 Передать Ивану", url=f"https://t.me/{settings.sales_username}")])
    buttons.append([InlineKeyboardButton("← В меню", callback_data="menu:main")])

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await log_event(session, user_id=user.id, event="faq_opened")
        await session.commit()

    await update.effective_message.reply_text(intro, reply_markup=InlineKeyboardMarkup(buttons))


async def handle_show(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback `faq:show:<idx>` — показать ответ по номеру."""
    query = update.callback_query
    await query.answer()
    try:
        idx = int((query.data or "").split(":")[2])
    except (IndexError, ValueError):
        return

    item = faq_core.get_by_index(idx)
    if not item:
        await query.message.reply_text("Не нашла этот вопрос. /faq — все вопросы.")
        return

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await log_event(
            session,
            user_id=user.id,
            event="faq_question_viewed",
            payload={"index": idx},
        )
        await session.commit()

    text = f"<b>{item.question}</b>\n\n{item.answer}"
    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📋 Все вопросы", callback_data="menu:faq")],
                [InlineKeyboardButton("💬 Передать Ивану", url=f"https://t.me/{settings.sales_username}")],
            ]
        ),
    )


async def handle_text_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Если пользователь в FAQ-режиме — ищем ответ по ключевым словам.

    Возвращает True если перехватили текст.
    """
    if not context.user_data.get(KEY_FAQ_MODE):
        return False

    text = (update.effective_message.text or "").strip()
    if not text:
        return False

    # Если пользователь явно написал номер
    if text.isdigit():
        idx = int(text)
        item = faq_core.get_by_index(idx)
        if item:
            await _reply_with_item(update, item)
            return True

    item = faq_core.search(text)
    if item:
        await _reply_with_item(update, item)
        return True

    # Нет совпадений — отдаём Ивану
    context.user_data.pop(KEY_FAQ_MODE, None)
    await update.effective_message.reply_text(
        "Точного ответа на этот вопрос у меня нет — передаю Ивану.",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(
                    f"💬 Написать @{settings.sales_username}",
                    url=f"https://t.me/{settings.sales_username}",
                )],
                [InlineKeyboardButton("← В меню", callback_data="menu:main")],
            ]
        ),
    )
    return True


async def _reply_with_item(update: Update, item) -> None:
    text = f"<b>{item.question}</b>\n\n{item.answer}"
    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📋 Все вопросы", callback_data="menu:faq")],
                [InlineKeyboardButton("💬 Передать Ивану", url=f"https://t.me/{settings.sales_username}")],
            ]
        ),
    )
