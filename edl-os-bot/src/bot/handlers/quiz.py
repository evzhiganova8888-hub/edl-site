"""Quiz Founder OS Score — 12 вопросов в боте (§7.2 ТЗ v3)."""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.bot import keyboards
from src.bot.handlers import lead_capture
from src.core.quiz import (
    QUIZ_QUESTIONS,
    layer_label,
    layer_scores,
    recommendation,
    total_score,
)
from src.db.repos import get_or_create_user, log_event
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

KEY_IDX = "quiz_index"
KEY_ANS = "quiz_answers"


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Стартует квиз. Можно вызывать из /start quiz или /quiz."""
    context.user_data[KEY_IDX] = 0
    context.user_data[KEY_ANS] = {}

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await log_event(session, user_id=user.id, event="quiz_started")
        await session.commit()

    await update.effective_message.reply_text(
        "Quiz Founder OS Score — 12 вопросов на 3 минуты. "
        "В конце получите балл 0–100 и рекомендацию: с чего вам начинать."
    )
    await _send_question(update, context, index=0)


async def _send_question(
    update: Update, context: ContextTypes.DEFAULT_TYPE, *, index: int
) -> None:
    q = QUIZ_QUESTIONS[index]
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"quiz:ans:{index}:{score}")]
        for label, score in q.options
    ]
    buttons.append([InlineKeyboardButton("Прервать", callback_data="quiz:cancel")])
    markup = InlineKeyboardMarkup(buttons)
    await update.effective_message.reply_text(q.text, reply_markup=markup)


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback `quiz:ans:<index>:<score>`."""
    query = update.callback_query
    await query.answer()
    parts = (query.data or "").split(":")
    if len(parts) < 4:
        return
    try:
        index = int(parts[2])
        score = int(parts[3])
    except ValueError:
        return

    if index >= len(QUIZ_QUESTIONS):
        return

    answers = context.user_data.setdefault(KEY_ANS, {})
    answers[QUIZ_QUESTIONS[index].key] = score
    next_index = index + 1
    context.user_data[KEY_IDX] = next_index

    if next_index < len(QUIZ_QUESTIONS):
        await _send_question(update, context, index=next_index)
        return

    await _finish(update, context)


async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data.pop(KEY_IDX, None)
    context.user_data.pop(KEY_ANS, None)
    await query.message.reply_text(
        "Окей, прервала. Если передумаете — /start quiz запустит заново.",
        reply_markup=keyboards.main_menu(),
    )


async def _finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    answers = context.user_data.get(KEY_ANS, {})
    context.user_data.pop(KEY_IDX, None)
    context.user_data.pop(KEY_ANS, None)

    score = total_score(answers)
    layers = layer_scores(answers)
    product, rec_text = recommendation(score)

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        user.quiz_score = score
        await log_event(
            session,
            user_id=user.id,
            event="quiz_completed",
            payload={"score": score, "layers": layers, "recommended": product},
        )
        await session.commit()

    layer_lines = "\n".join(
        f"• {layer_label(k)}: {v}/30" for k, v in layers.items()
    )
    text = (
        f"Ваш Founder OS Score: <b>{score}/100</b>\n\n"
        f"По слоям:\n{layer_lines}\n\n"
        f"{rec_text}"
    )

    # CTA по рекомендации
    if product == "audit":
        markup = keyboards.audit_pay_keyboard()
    elif product == "diagnostic":
        markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📋 Заявка на Диагностику", callback_data="menu:diagnostic")],
                [InlineKeyboardButton("Сначала Чекап за 9 000 ₽", callback_data="menu:audit")],
                [InlineKeyboardButton("← В меню", callback_data="menu:main")],
            ]
        )
    else:
        markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🏗 Лист ожидания Спринта", callback_data="menu:sprint_waitlist")],
                [InlineKeyboardButton("← В меню", callback_data="menu:main")],
            ]
        )

    await update.effective_message.reply_text(text, reply_markup=markup, parse_mode="HTML")
