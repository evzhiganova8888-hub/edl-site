"""/start dispatcher — главное меню + 7 deep-link routes (§5 + §7 ТЗ v3)."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.bot import keyboards, texts
from src.bot.handlers import audit, consent as consent_handler, faq, lead_capture, privacy, quiz
from src.core.segment import detect_from_deep_link
from src.db.repos import get_or_create_user, log_event
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

# Маппинг deep-link payload → имя обработчика-сценария.
DEEP_LINK_HANDLERS = {
    "demo": "demo",
    "audit": "audit",
    "audit_sample": "audit_sample",
    "diagnostic": "diagnostic",
    "sprint_waitlist": "sprint_waitlist",
    "hero_summary": "hero_summary",
    "quiz": "quiz",
}


async def _ensure_user(update: Update):
    """Создаёт пользователя при первом /start. Возвращает (user, session, async_factory)."""
    tg = update.effective_user
    factory = async_session_factory()
    async with factory() as session:
        user, created = await get_or_create_user(
            session,
            telegram_id=tg.id,
            username=tg.username,
            first_name=tg.first_name,
            last_name=tg.last_name,
        )
        await log_event(
            session,
            user_id=user.id,
            event="bot_start",
            payload={"created": created, "payload": (update.message.text or "") if update.message else None},
        )
        await session.commit()
        return user


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await _ensure_user(update)
    payload = " ".join(context.args) if context.args else ""

    # Сохраним сегмент, если пришёл через deep-link
    seg = detect_from_deep_link(payload)
    if seg:
        factory = async_session_factory()
        async with factory() as session:
            db_user = await session.merge(user)
            db_user.segment = seg
            await log_event(
                session,
                user_id=db_user.id,
                event="segment_detected",
                payload={"segment": seg, "method": "deep_link", "payload": payload},
            )
            await session.commit()

    # Маршрутизация
    if not payload:
        await _send_main_menu(update, greeting=True)
        return

    scenario = DEEP_LINK_HANDLERS.get(payload.split()[0])
    if scenario == "audit":
        await audit.audit_command(update, context)
        return
    if scenario == "audit_sample":
        await audit.audit_sample_command(update, context)
        return
    if scenario in ("demo", "diagnostic", "sprint_waitlist", "hero_summary"):
        await lead_capture.start_flow(update, context, flow_type=scenario)
        return
    if scenario == "quiz":
        await quiz.quiz_command(update, context)
        return

    # Неизвестный payload → главное меню
    await _send_main_menu(update, greeting=True)


async def _stub_scenario(update: Update, *, name: str, description: str) -> None:
    """Заглушка на Этапе 1 — показывает описание + предлагает hand-off."""
    factory = async_session_factory()
    async with factory() as session:
        if update.effective_user:
            user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
            await log_event(
                session, user_id=user.id, event=f"scenario_{name}_started"
            )
            await session.commit()
    await update.effective_message.reply_text(
        description, reply_markup=keyboards.audit_pay_keyboard()
    )


async def _send_main_menu(update: Update, *, greeting: bool) -> None:
    text = texts.GREETING if greeting else texts.MENU_AGAIN
    await update.effective_message.reply_text(text, reply_markup=keyboards.main_menu())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Команды:\n"
        "/start — главное меню\n"
        "/menu — показать меню ещё раз\n"
        "/audit — Бизнес-чекап\n"
        "/audit_sample — пример отчёта\n"
        "/faq — частые вопросы\n"
        "/privacy — мои данные и согласия\n"
        "/reset — сбросить контекст диалога"
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_main_menu(update, greeting=False)


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    await update.effective_message.reply_text(
        "Контекст диалога сброшен. /menu — главное меню."
    )


async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback `menu:<action>`."""
    query = update.callback_query
    await query.answer()
    action = (query.data or "").split(":", 1)[1] if ":" in (query.data or "") else ""

    if action == "main":
        await query.message.reply_text(texts.MENU_AGAIN, reply_markup=keyboards.main_menu())
        return
    if action == "audit":
        await audit.audit_command(update, context)
        return
    if action == "audit_sample":
        await audit.audit_sample_command(update, context)
        return
    if action == "faq":
        await faq.faq_command(update, context)
        return
    if action == "privacy":
        await privacy.privacy_command(update, context)
        return
    if action in ("demo", "diagnostic", "sprint_waitlist", "hero_summary"):
        await lead_capture.start_flow(update, context, flow_type=action)
        return
    if action == "quiz":
        await quiz.quiz_command(update, context)
        return

    logger.warning("Unknown menu action: %s", action)
    await query.message.reply_text(texts.MENU_AGAIN, reply_markup=keyboards.main_menu())


async def handle_segment_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback `segment:<code>` — пользователь выбрал сегмент из меню."""
    query = update.callback_query
    await query.answer()
    seg = (query.data or "").split(":", 1)[1] if ":" in (query.data or "") else "other"

    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        user.segment = seg
        await log_event(
            session,
            user_id=user.id,
            event="segment_detected",
            payload={"segment": seg, "method": "button"},
        )
        await session.commit()

    await query.message.reply_text(
        "Спасибо, отметила. Что вам сейчас полезнее?",
        reply_markup=keyboards.main_menu(),
    )
