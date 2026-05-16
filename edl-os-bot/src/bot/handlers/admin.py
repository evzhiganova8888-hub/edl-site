"""/admin команда для команды EDL — сводка, /mark_paid, /applications."""
from __future__ import annotations

import io
import csv
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.admin.auth import is_admin, is_admin_active
from src.bot import texts
from src.core.flags import FLAG_VITACONSULT_PUBLIC, get_flag, set_flag
from src.core.notifications import send_to_admin_chat
from src.core.payment_marking import mark_application_paid
from src.db.models import Application, BotError, CheckupAnswer, Event, Feedback, Payment, User
from src.db.repos import get_or_create_user, log_event
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

_PENDING_TOGGLE_KEY = "admin_pending_toggle"  # ждём reason для VITACONSULT toggle


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.effective_message.reply_text(
            "Эта команда — только для команды EDL. Если что-то ищете — /menu."
        )
        return

    factory = async_session_factory()
    since = datetime.now(timezone.utc) - timedelta(days=30)
    async with factory() as session:
        new_apps = await session.scalar(
            select(func.count(Application.id)).where(Application.created_at >= since)
        )
        paid = await session.scalar(
            select(func.count(Application.id))
            .where(Application.payment_succeeded_at >= since)
        )
        revenue_kop = await session.scalar(
            select(func.sum(Payment.amount_kopecks))
            .where(Payment.status == "succeeded")
            .where(Payment.paid_at >= since)
        ) or 0
        starts = await session.scalar(
            select(func.count(Event.id))
            .where(Event.event == "bot_start")
            .where(Event.occurred_at >= since)
        )
        unresolved_bugs = await session.scalar(
            select(func.count(BotError.id)).where(BotError.reviewed_at.is_(None))
        ) or 0
        vitaconsult = await get_flag(session, FLAG_VITACONSULT_PUBLIC, default=False)

    text = (
        "📊 Админка · последние 30 дней\n\n"
        f"Старты /start: {starts or 0}\n"
        f"Новые заявки: {new_apps or 0}\n"
        f"Оплаты: {paid or 0}\n"
        f"Выручка: {revenue_kop / 100:,.0f} ₽\n\n"
        f"⚠️ Bug-report'ы (неразобранные): {unresolved_bugs}\n\n"
        f"VITACONSULT_PUBLIC: {'✅ включено' if vitaconsult else '❌ выключено'}"
    )
    toggle_label = (
        "🔒 Выключить VITACONSULT" if vitaconsult else "🔓 Включить VITACONSULT"
    )
    markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(toggle_label, callback_data="admin:toggle_vitaconsult")],
            [InlineKeyboardButton("← В меню", callback_data="menu:main")],
        ]
    )
    await update.effective_message.reply_text(text, reply_markup=markup)


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    action = (query.data or "").split(":", 1)[1] if ":" in (query.data or "") else ""
    if action == "toggle_vitaconsult":
        factory = async_session_factory()
        async with factory() as session:
            current = await get_flag(session, FLAG_VITACONSULT_PUBLIC, default=False)
        # Просим причину перед переключением (§C.6 v3.1)
        context.user_data[_PENDING_TOGGLE_KEY] = {
            "key": FLAG_VITACONSULT_PUBLIC,
            "from": current,
            "to": not current,
        }
        await query.message.reply_text(
            f"Готовим переключение VITACONSULT_PUBLIC: "
            f"{'true' if current else 'false'} → "
            f"{'true' if not current else 'false'}.\n\n"
            "Напишите *причину* одним сообщением (≥3 символов). "
            "Без причины toggle не сработает.\n\n"
            "Чтобы отменить — /reset.",
            parse_mode="Markdown",
        )


async def handle_text_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Если админ переключает VITACONSULT и ждём reason — обрабатываем тут."""
    pending = context.user_data.get(_PENDING_TOGGLE_KEY)
    if not pending:
        return False
    user_id = update.effective_user.id
    if not is_admin(user_id):
        # Чужак не должен застрять в admin FSM
        context.user_data.pop(_PENDING_TOGGLE_KEY, None)
        return False

    text = (update.effective_message.text or "").strip()
    if len(text) < 3:
        await update.effective_message.reply_text(
            "Причина слишком короткая. Минимум 3 символа. Попробуйте ещё раз "
            "или /reset для отмены."
        )
        return True

    factory = async_session_factory()
    async with factory() as session:
        await set_flag(
            session, pending["key"], enabled=pending["to"], actor=str(user_id)
        )
        session.add(
            Event(
                user_id=user_id,
                event="feature_flag_toggled",
                payload={
                    "key": pending["key"],
                    "old": pending["from"],
                    "new": pending["to"],
                    "actor_telegram_id": user_id,
                    "reason": text[:500],
                    "via": "telegram_admin",
                },
            )
        )
        await session.commit()
    context.user_data.pop(_PENDING_TOGGLE_KEY, None)
    await update.effective_message.reply_text(
        f"✅ {pending['key']} = {'true' if pending['to'] else 'false'}\n"
        f"Причина зафиксирована в audit-log."
    )
    return True


# ─── /mark_paid ───────────────────────────────────────────────────────────────


async def mark_paid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/mark_paid <application_id> <amount> [reference]

    Помечает оплату заявки и отправляет уведомление пользователю.
    """
    user_id = update.effective_user.id
    msg = update.effective_message
    factory = async_session_factory()
    async with factory() as session:
        if not await is_admin_active(session, user_id):
            await msg.reply_text("Только для команды EDL. /admin_login <KEY>")
            return

    args = context.args or []
    if len(args) < 2:
        await msg.reply_text(
            "Использование: /mark_paid <application_id> <amount_rub> [reference]\n"
            "Пример: /mark_paid 550e8400-e29b-41d4-a716-446655440000 9000 \"счёт-12\""
        )
        return

    app_id_str = args[0]
    try:
        app_uuid = UUID(app_id_str)
        amount_rub = float(args[1])
    except (ValueError, AttributeError):
        await msg.reply_text("Неверный формат application_id или суммы.")
        return

    reference = " ".join(args[2:]).strip('"\'') if len(args) > 2 else ""

    factory = async_session_factory()
    async with factory() as session:
        from sqlalchemy import select as sa_select
        stmt = sa_select(Application).where(Application.id == app_uuid)
        app = (await session.execute(stmt)).scalar_one_or_none()
        if app is None:
            await msg.reply_text(f"Заявка {app_id_str} не найдена.")
            return
        app_user = await session.get(User, app.user_id)
        if app_user is None:
            await msg.reply_text("Пользователь заявки не найден.")
            return

        result = await mark_application_paid(
            session,
            app=app,
            user=app_user,
            amount_rub=amount_rub,
            payment_provider="manual_admin",
            provider_payment_id=reference or None,
            actor=f"admin:{user_id}",
        )
        session.add(Event(
            user_id=app_user.id,
            event="application_marked_paid_via_bot",
            payload={
                "application_id": str(app_uuid),
                "actor_telegram_id": user_id,
                "amount_rub": amount_rub,
                "reference": reference,
                "already_paid": result.get("already_paid", False),
            },
        ))
        await session.commit()
        target_telegram_id = app_user.telegram_id

    if result.get("already_paid"):
        await msg.reply_text(f"Заявка {app_id_str} уже была помечена как оплаченная (idempotent).")
        return

    # Уведомляем пользователя
    try:
        from src.bot import keyboards
        await context.bot.send_message(
            chat_id=target_telegram_id,
            text=texts.CHECKUP_PAYMENT_CONFIRMED,
            reply_markup=keyboards.InlineKeyboardMarkup(
                [[keyboards.InlineKeyboardButton("🚀 Начать Чекап", callback_data="menu:checkup")]]
            ),
        )
    except Exception:
        logger.exception("Failed to notify user %s about payment", target_telegram_id)

    await msg.reply_text(
        f"✅ Заявка {app_id_str} помечена оплаченной ({amount_rub:.0f} ₽). "
        f"Пользователю отправлено уведомление."
    )


# ─── /applications ────────────────────────────────────────────────────────────


async def applications_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/applications [pending|paid|all] [limit=20]"""
    user_id = update.effective_user.id
    msg = update.effective_message
    factory = async_session_factory()
    async with factory() as session:
        if not await is_admin_active(session, user_id):
            await msg.reply_text("Только для команды EDL. /admin_login <KEY>")
            return

    args = context.args or []
    status_filter = args[0] if args else "pending"
    try:
        limit = int(args[1]) if len(args) > 1 else 20
    except ValueError:
        limit = 20
    limit = min(limit, 50)

    factory = async_session_factory()
    async with factory() as session:
        stmt = select(Application, User).join(User, Application.user_id == User.id)
        if status_filter == "pending":
            stmt = stmt.where(Application.status.in_(["awaiting_manual_payment", "new", "qualified"]))
        elif status_filter == "paid":
            stmt = stmt.where(Application.status == "paid")
        stmt = stmt.order_by(Application.created_at.desc()).limit(limit)
        rows = (await session.execute(stmt)).all()

    if not rows:
        await msg.reply_text(f"Заявок с фильтром «{status_filter}» не найдено.")
        return

    lines = [f"📋 Заявки ({status_filter}, последние {limit}):\n"]
    for app, u in rows:
        name = " ".join(filter(None, [u.last_name, u.first_name])) or u.telegram_username or str(u.telegram_id)
        plan = (app.payload or {}).get("plan", "?") if app.payload else "?"
        lines.append(
            f"• {app.created_at.strftime('%d.%m %H:%M')} | {app.status} | {plan} | "
            f"{name} | /mark_paid {app.id} 9000"
        )

    await msg.reply_text("\n".join(lines)[:4000])
