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
from src.db.repos import create_application, get_or_create_user, log_event
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
            [
                InlineKeyboardButton("🎁 Demo себе · Plus", callback_data="admin:self_demo:plus"),
                InlineKeyboardButton("🎁 Demo себе · Base", callback_data="admin:self_demo:base"),
            ],
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

    raw = query.data or ""
    action = raw.split(":", 1)[1] if ":" in raw else ""
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
        return

    if action.startswith("self_demo:"):
        plan = action.split(":", 1)[1] if ":" in action else "plus"
        if plan not in ("base", "plus"):
            plan = "plus"
        # Эмулируем /grant_demo <self> <plan> — переиспользуем команду.
        context.args = [str(user_id), plan]
        await grant_demo_command(update, context)
        return


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


# ─── /grant_demo ──────────────────────────────────────────────────────────────


def _resolve_user_ref(arg: str) -> tuple[int | None, str | None]:
    """Парсит аргумент команды: telegram_id (число) или @username.
    Возвращает (telegram_id, username) — заполнено ровно одно.
    """
    arg = arg.strip()
    if not arg:
        return None, None
    if arg.startswith("@"):
        return None, arg[1:].strip()
    try:
        return int(arg), None
    except ValueError:
        return None, arg if arg.isalnum() or "_" in arg else None


async def grant_demo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/grant_demo <telegram_id|@username> [base|plus]

    Создаёт оплаченную Application для демо-клиента, открывает /checkup доступ
    без онлайн-оплаты. Используется Катей/Иваном для партнёрских/экспертных
    обкаток (например, VitaКонсалт).

    Пользователь должен хотя бы раз написать /start боту — иначе мы не
    знаем его telegram_id и не сможем отправить уведомление.
    """
    admin_tg_id = update.effective_user.id
    msg = update.effective_message
    if not is_admin(admin_tg_id):
        await msg.reply_text("Только для команды EDL.")
        return

    args = context.args or []
    if not args:
        await msg.reply_text(
            "Использование: /grant_demo <telegram_id|@username> [base|plus]\n"
            "По умолчанию — plus (с видео-разбором).\n\n"
            "Перед grant пользователь должен хотя бы раз нажать /start у бота "
            "(чтобы он попал в нашу БД).\n\n"
            "Пример: /grant_demo 105255440 plus\n"
            "         /grant_demo @Linamironovich plus"
        )
        return

    ref_tg_id, ref_username = _resolve_user_ref(args[0])
    if ref_tg_id is None and not ref_username:
        await msg.reply_text(
            "Не разобрал первый аргумент. Дайте telegram_id (число) или @username."
        )
        return

    plan = "plus"
    if len(args) > 1:
        plan_arg = args[1].lower()
        if plan_arg in ("base", "plus"):
            plan = plan_arg
        else:
            await msg.reply_text("Тариф: base | plus (по умолчанию plus).")
            return

    amount_rub = 14000.0 if plan == "plus" else 9000.0

    factory = async_session_factory()
    async with factory() as session:
        from sqlalchemy import select as sa_select
        if ref_tg_id is not None:
            stmt = sa_select(User).where(User.telegram_id == ref_tg_id)
        else:
            stmt = sa_select(User).where(User.telegram_username == ref_username)
        target_user = (await session.execute(stmt)).scalar_one_or_none()

        if target_user is None:
            await msg.reply_text(
                f"Пользователь {args[0]} не найден в БД.\n\n"
                "Попросите его нажать /start у @edl_os_bot, потом повторите команду. "
                "Иначе бот не сможет отправить уведомление об открытии доступа."
            )
            return

        # is_self_demo=True если админ выдаёт демо самому себе.
        # Self-demo не триггерит видео-бриф Кате (бесконечный цикл при самотесте)
        # и исключается из воронки метрик (exclude_from_funnel=True).
        is_self_demo = target_user.telegram_id == admin_tg_id
        app = await create_application(
            session,
            user=target_user,
            type="audit",
            source="demo_grant",
            payload={
                "plan": plan,
                "source": "demo_grant",
                "granted_by_telegram_id": admin_tg_id,
                "is_self_demo": is_self_demo,
                "exclude_from_funnel": is_self_demo,
            },
        )
        result = await mark_application_paid(
            session,
            app=app,
            user=target_user,
            amount_rub=amount_rub,
            payment_provider="demo_grant",
            provider_payment_id=f"demo:{admin_tg_id}",
            actor=f"admin:{admin_tg_id}",
        )
        session.add(Event(
            user_id=target_user.id,
            event="demo_access_granted",
            payload={
                "application_id": str(app.id),
                "plan": plan,
                "granted_by_telegram_id": admin_tg_id,
            },
        ))
        await session.commit()
        target_telegram_id = target_user.telegram_id
        target_name = (
            " ".join(filter(None, [target_user.last_name, target_user.first_name]))
            or target_user.telegram_username
            or str(target_user.telegram_id)
        )

    # Уведомляем клиента
    plus_video_line = (
        texts.CHECKUP_DEMO_ACCESS_GRANTED_PLUS_VIDEO_LINE if plan == "plus" else "\n"
    )
    plan_suffix = " (Plus, с видео)" if plan == "plus" else " (Базовый)"
    text_to_client = texts.CHECKUP_DEMO_ACCESS_GRANTED.format(
        plan_suffix=plan_suffix,
        plus_video_line=plus_video_line,
    )

    delivered = True
    try:
        from src.bot import keyboards
        await context.bot.send_message(
            chat_id=target_telegram_id,
            text=text_to_client,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🚀 Начать Чекап", callback_data="menu:checkup")]]
            ),
        )
    except Exception:
        logger.exception("grant_demo: failed to notify user %s", target_telegram_id)
        delivered = False

    self_demo_tag = " · self-demo (не в воронке, без видео-брифа Кате)" if is_self_demo else ""
    summary = (
        f"✅ Demo-доступ выдан{self_demo_tag}: {target_name} "
        f"(tg_id={target_telegram_id}, plan={plan}).\n"
        f"Application: {result['application_id']}\n"
        f"Refund window до: {result.get('refund_eligible_until', '—')}"
    )
    if not delivered:
        summary += "\n\n⚠️ Не удалось отправить уведомление клиенту (возможно, заблокировал бота)."
    await msg.reply_text(summary)


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
