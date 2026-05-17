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


# ─── /emails_dump ─────────────────────────────────────────────────────────────

_BETA_SINCE = datetime(2026, 5, 12, 0, 0, 0, tzinfo=timezone.utc)
_BETA_UNTIL = datetime(2026, 5, 19, 23, 59, 59, tzinfo=timezone.utc)


async def emails_dump_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/emails_dump — CSV с email'ами пользователей беты 12–19 мая."""
    user_id = update.effective_user.id
    msg = update.effective_message
    factory = async_session_factory()
    async with factory() as session:
        if not await is_admin_active(session, user_id):
            await msg.reply_text("Только для команды EDL. /admin_login <KEY>")
            return

    async with factory() as session:
        stmt = (
            select(User, Application)
            .outerjoin(Application, Application.user_id == User.id)
            .where(User.created_at >= _BETA_SINCE)
            .where(User.created_at <= _BETA_UNTIL)
            .order_by(User.created_at)
        )
        rows = (await session.execute(stmt)).all()

        session.add(Event(
            user_id=user_id,
            event="emails_dumped",
            payload={"actor": user_id, "rows": len(rows)},
        ))
        from src.db.models import PDAccessLog
        session.add(PDAccessLog(
            actor=str(user_id),
            action="export",
            fields=["telegram_id", "telegram_username", "first_name", "last_name",
                    "email", "company_name", "segment", "quiz_score", "created_at"],
        ))
        await session.commit()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "telegram_id", "telegram_username", "first_name", "last_name",
        "email", "company_name", "segment", "quiz_score",
        "created_at", "has_application", "application_status",
        "consent_marketing_given_at",
    ])
    seen_users: set[int] = set()
    for u, app in rows:
        if u.id in seen_users:
            continue
        seen_users.add(u.id)
        # Не включаем email если нет согласия на маркетинг
        email = u.email if u.consent_marketing_given_at else ""
        writer.writerow([
            u.telegram_id, u.telegram_username or "",
            u.first_name or "", u.last_name or "",
            email, u.company_name or "",
            u.segment or "", u.quiz_score or "",
            u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
            "yes" if app else "no",
            app.status if app else "",
            u.consent_marketing_given_at.strftime("%Y-%m-%d") if u.consent_marketing_given_at else "",
        ])

    buf.seek(0)
    await msg.reply_document(
        document=buf.getvalue().encode("utf-8"),
        filename="edl_beta_emails_12_19_may_2026.csv",
        caption=f"Пользователи беты 12–19 мая 2026. Уникальных: {len(seen_users)}.",
    )


# ─── /beta_summary ────────────────────────────────────────────────────────────


async def beta_summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/beta_summary — сводка по событиям беты 12–19 мая."""
    user_id = update.effective_user.id
    msg = update.effective_message
    factory = async_session_factory()
    async with factory() as session:
        if not await is_admin_active(session, user_id):
            await msg.reply_text("Только для команды EDL. /admin_login <KEY>")
            return

    async with factory() as session:
        # Уникальные старты
        starts = await session.scalar(
            select(func.count(func.distinct(Event.user_id)))
            .where(Event.event == "bot_start")
            .where(Event.occurred_at.between(_BETA_SINCE, _BETA_UNTIL))
        ) or 0

        # Прошли Quiz
        quiz_done = await session.scalar(
            select(func.count(func.distinct(Event.user_id)))
            .where(Event.event == "quiz_completed")
            .where(Event.occurred_at.between(_BETA_SINCE, _BETA_UNTIL))
        ) or 0

        # Открыли /audit
        audit_open = await session.scalar(
            select(func.count(Event.id))
            .where(Event.event == "audit_intro_shown")
            .where(Event.occurred_at.between(_BETA_SINCE, _BETA_UNTIL))
        ) or 0

        # Дали согласие на оферту
        offer_accepted = await session.scalar(
            select(func.count(Event.id))
            .where(Event.event == "offer_accepted")
            .where(Event.occurred_at.between(_BETA_SINCE, _BETA_UNTIL))
        ) or 0

        # Оплаты
        paid_count = await session.scalar(
            select(func.count(Application.id))
            .where(Application.status == "paid")
            .where(Application.payment_succeeded_at.between(_BETA_SINCE, _BETA_UNTIL))
        ) or 0

        paid_sum = await session.scalar(
            select(func.sum(Payment.amount_kopecks))
            .where(Payment.status == "succeeded")
            .where(Payment.paid_at.between(_BETA_SINCE, _BETA_UNTIL))
        ) or 0

        # Bug reports
        bug_count = await session.scalar(
            select(func.count(BotError.id))
            .where(BotError.reported_at.between(_BETA_SINCE, _BETA_UNTIL))
        ) or 0

        # Feedback
        feedback_count = await session.scalar(
            select(func.count(Feedback.id))
            .where(Feedback.reported_at.between(_BETA_SINCE, _BETA_UNTIL))
        ) or 0

        # Off-topic blocks
        off_topic = await session.scalar(
            select(func.count(Event.id))
            .where(Event.event == "off_topic_blocked")
            .where(Event.occurred_at.between(_BETA_SINCE, _BETA_UNTIL))
        ) or 0

        # Чекапы завершены
        checkups_done = await session.scalar(
            select(func.count(Event.id))
            .where(Event.event == "checkup_completed")
            .where(Event.occurred_at.between(_BETA_SINCE, _BETA_UNTIL))
        ) or 0

    text = (
        "📊 *Итоги беты 12–19 мая 2026*\n\n"
        f"🚀 Уникальных /start: {starts}\n"
        f"🎯 Прошли Quiz: {quiz_done}\n"
        f"📋 Открыли /audit: {audit_open}\n"
        f"✅ Приняли оферту: {offer_accepted}\n\n"
        f"💰 Оплаты: {paid_count} шт · {paid_sum / 100:,.0f} ₽\n"
        f"✅ Завершили Чекап: {checkups_done}\n\n"
        f"⚠️ Bug-reports: {bug_count}\n"
        f"💬 Feedback: {feedback_count}\n"
        f"🚫 Off-topic заблокировано: {off_topic}\n\n"
        "Подробный CSV: /emails_dump"
    )
    await msg.reply_text(text, parse_mode="Markdown")


# ─── F8: /upload_plus_video ───────────────────────────────────────────────────

_PLUS_VIDEO_UPLOAD_KEY = "plus_video_upload_app_id"


async def upload_plus_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/upload_plus_video <application_id> — Катя загружает видео для клиента Plus."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.effective_message.reply_text("Только для команды EDL.")
        return

    args = context.args or []
    if len(args) != 1:
        await update.effective_message.reply_text(
            "Использование: /upload_plus_video <application_id>"
        )
        return

    application_id = args[0]
    factory = async_session_factory()
    async with factory() as session:
        try:
            app_uuid = UUID(application_id)
        except ValueError:
            await update.effective_message.reply_text("Неверный формат application_id.")
            return
        app = await session.get(Application, app_uuid)
        if app is None:
            await update.effective_message.reply_text(f"Заявка {application_id} не найдена.")
            return
        if app.status != "paid":
            await update.effective_message.reply_text(
                f"Заявка {application_id} не оплачена (status={app.status})."
            )
            return

    context.user_data[_PLUS_VIDEO_UPLOAD_KEY] = application_id
    await update.effective_message.reply_text(
        f"Ожидаю файл видео для заявки {application_id}.\n"
        "Прикрепите видео следующим сообщением.",
    )


async def handle_admin_video_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик файла/видео в режиме загрузки Plus-видео."""
    application_id = context.user_data.get(_PLUS_VIDEO_UPLOAD_KEY)
    if not application_id:
        return  # не в режиме загрузки

    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    msg = update.effective_message
    video = msg.video or msg.document
    if not video:
        await msg.reply_text("Нужен файл видео или документ.")
        return

    file_id = video.file_id

    factory = async_session_factory()
    async with factory() as session:
        try:
            app_uuid = UUID(application_id)
        except ValueError:
            return
        app = await session.get(Application, app_uuid)
        if app is None:
            await msg.reply_text("Заявка не найдена.")
            context.user_data.pop(_PLUS_VIDEO_UPLOAD_KEY, None)
            return

        user_obj = (await session.execute(
            select(User).where(User.id == app.user_id)
        )).scalar_one_or_none()
        if user_obj is None:
            await msg.reply_text("Пользователь заявки не найден.")
            return

        now = datetime.now(timezone.utc)
        # Сохраняем метаданные видео (F8 migration 0011 поля если есть)
        if hasattr(app, "plus_video_uploaded_at"):
            app.plus_video_uploaded_at = now
        if hasattr(app, "plus_video_url"):
            app.plus_video_url = file_id  # храним Telegram file_id

        await log_event(session, user_id=app.user_id, event="plus_video_uploaded",
                        payload={"application_id": application_id})
        await session.commit()

    # Отправляем видео клиенту
    try:
        await context.bot.send_video(
            chat_id=user_obj.telegram_id,
            video=file_id,
            caption=(
                "🎬 Ваше персональное видео-разбор от Кати Жигановой.\n\n"
                "Смотрите, конспектируйте и внедряйте. "
                "Если появятся вопросы — пишите прямо сюда."
            ),
        )
        logger.info("Plus video sent to user %s for application %s", user_obj.telegram_id, application_id)
    except Exception:
        logger.exception("Failed to send plus video to user %s", user_obj.telegram_id)
        await msg.reply_text(
            f"Ошибка при отправке видео клиенту {user_obj.telegram_id}. "
            "Проверьте что бот не заблокирован."
        )
        return

    # Фиксируем время отправки
    factory2 = async_session_factory()
    async with factory2() as session2:
        app2 = await session2.get(Application, app_uuid)
        if app2 and hasattr(app2, "plus_video_sent_to_client_at"):
            app2.plus_video_sent_to_client_at = datetime.now(timezone.utc)
        await session2.commit()

    context.user_data.pop(_PLUS_VIDEO_UPLOAD_KEY, None)
    await msg.reply_text(
        f"✅ Видео отправлено клиенту (tg_id={user_obj.telegram_id}).\n"
        f"Email: {user_obj.email or '—'}"
    )
