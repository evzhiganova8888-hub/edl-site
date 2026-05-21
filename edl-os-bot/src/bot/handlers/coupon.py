"""Команды для работы с купонами на Диагностику.

Для клиента:
- `/diagnostika` — проверка статуса активного купона и инструкции по
  применению. Жёстко проверяет 24-часовой TTL.

Для админа:
- `/issue_coupon <user_id>` — ручная выдача купона −20% на Диагностику.
- `/coupon_info <code>` — детали по купону.
- `/confirm_payment <code>` — пометить купон used (после оплаты Диагностики).
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.admin.auth import is_admin
from src.core.config import settings
from src.core import coupon_engine as ce
from src.db.models import User
from src.db.repos import log_event
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)


# ── Клиентская команда /diagnostika ──────────────────────────────────────────


async def diagnostika_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Клиент проверяет: есть ли активный купон с действующим TTL."""
    factory = async_session_factory()
    async with factory() as session:
        user = (
            await session.execute(
                select(User).where(User.telegram_id == update.effective_user.id)
            )
        ).scalar_one_or_none()
        if user is None:
            await update.effective_message.reply_text(
                "Сначала зайдите в /start — без этого не вижу вашу историю в боте."
            )
            return

        coupon = await ce.get_active_coupon_for_user(session, user.id)
        await session.commit()

        if coupon is None:
            await update.effective_message.reply_text(
                "Активного купона −20% на Диагностику у вас нет.\n\n"
                f"Диагностика доступна по полной цене {ce.DEFAULT_ORIGINAL_PRICE_RUB:,} ₽ — "
                f"напишите Ивану: @{settings.sales_username}.".replace(",", " "),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "💬 Написать Ивану",
                                url=f"https://t.me/{settings.sales_username}",
                            )
                        ],
                        [InlineKeyboardButton("← В меню", callback_data="menu:main")],
                    ]
                ),
            )
            return

        view = ce.view_of(coupon)
        deadline = view.expires_at.strftime("%d.%m.%Y %H:%M UTC") if view.expires_at else "—"

    await update.effective_message.reply_text(
        f"🎟 Ваш купон на Диагностику активен.\n\n"
        f"Промокод: `{view.code}`\n"
        f"Цена с купоном: {view.discounted_price_rub:,} ₽ "
        f"(вместо {view.original_price_rub:,} ₽, скидка {view.discount_pct}%)\n"
        f"Истекает: {deadline} (через {view.hours_left} ч)\n\n"
        f"Чтобы оформить — напишите Ивану: @{settings.sales_username}. "
        f"Он пришлёт реквизиты и согласует время Zoom на 90 минут.\n\n"
        f"Купон действует ровно 24 часа с момента выдачи. После истечения "
        f"Диагностика доступна по полной цене.".replace(",", " "),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "💬 Написать Ивану",
                        url=f"https://t.me/{settings.sales_username}",
                    )
                ],
            ]
        ),
    )


# ── Админские команды ───────────────────────────────────────────────────────


async def issue_coupon_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/issue_coupon <telegram_id>` — выдать купон вручную.

    Использование на этапе пилота, пока автоматическая выдача (T+48ч после
    Plus-видео) не подключена в FSM Чекапа v2.
    """
    if not is_admin(update.effective_user.id):
        return  # silent
    args = context.args or []
    if len(args) < 1:
        await update.effective_message.reply_text(
            "Использование: /issue_coupon <telegram_id>"
        )
        return
    try:
        target_tg_id = int(args[0])
    except ValueError:
        await update.effective_message.reply_text("telegram_id должен быть числом.")
        return

    factory = async_session_factory()
    async with factory() as session:
        target = (
            await session.execute(
                select(User).where(User.telegram_id == target_tg_id)
            )
        ).scalar_one_or_none()
        if target is None:
            await update.effective_message.reply_text(
                f"Не нашёл пользователя с telegram_id={target_tg_id}."
            )
            return

        coupon = await ce.issue_coupon(session, user_id=target.id)
        await log_event(
            session,
            user_id=target.id,
            event="coupon_issued",
            payload={
                "code": coupon.code,
                "issued_by": update.effective_user.id,
                "expires_at": coupon.expires_at.isoformat(),
                "target_product": coupon.target_product,
            },
        )
        await session.commit()

        view = ce.view_of(coupon)

    deadline = view.expires_at.strftime("%d.%m.%Y %H:%M UTC") if view.expires_at else "—"
    await update.effective_message.reply_text(
        f"✅ Купон выдан.\n\n"
        f"Код: `{view.code}`\n"
        f"Получатель: tg_id {target_tg_id}\n"
        f"Цена с купоном: {view.discounted_price_rub:,} ₽\n"
        f"Истекает: {deadline} (через {view.hours_left} ч)".replace(",", " "),
        parse_mode="Markdown",
    )

    # Уведомление клиенту в чат
    try:
        await context.bot.send_message(
            chat_id=target_tg_id,
            text=(
                f"🎟 Вам выдан купон −{view.discount_pct}% на Диагностику.\n\n"
                f"Промокод: `{view.code}`\n"
                f"Цена с купоном: {view.discounted_price_rub:,} ₽ "
                f"(вместо {view.original_price_rub:,} ₽)\n"
                f"Срок действия: 24 часа (истекает {deadline}).\n\n"
                f"Чтобы применить — /diagnostika или напишите Ивану "
                f"@{settings.sales_username}."
            ).replace(",", " "),
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("Failed to notify user about issued coupon")


async def coupon_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/coupon_info <code>` — посмотреть детали купона (для Ивана/Кати)."""
    if not is_admin(update.effective_user.id):
        return
    args = context.args or []
    if len(args) < 1:
        await update.effective_message.reply_text("Использование: /coupon_info <code>")
        return
    code = args[0].strip()

    factory = async_session_factory()
    async with factory() as session:
        coupon = await ce.get_coupon_by_code(session, code)
        if coupon is None:
            await update.effective_message.reply_text("Купон не найден.")
            return
        view = ce.view_of(coupon)
        await session.commit()

    await update.effective_message.reply_text(
        f"Купон `{view.code}`\n"
        f"Статус: {view.status}\n"
        f"user_id (db): {coupon.user_id}\n"
        f"Выдан: {coupon.issued_at.strftime('%d.%m.%Y %H:%M UTC')}\n"
        f"Истекает: {view.expires_at.strftime('%d.%m.%Y %H:%M UTC') if view.expires_at else '—'}\n"
        f"Цена: {view.discounted_price_rub:,} ₽ "
        f"(оригинал {view.original_price_rub:,} ₽, скидка {view.discount_pct}%)".replace(",", " "),
        parse_mode="Markdown",
    )


async def confirm_payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """`/confirm_payment <code>` — Иван подтверждает оплату Диагностики по купону.

    Купон помечается used. Если он истёк до подтверждения — отказ
    (время побеждает по контракту engine).
    """
    if not is_admin(update.effective_user.id):
        return
    args = context.args or []
    if len(args) < 1:
        await update.effective_message.reply_text(
            "Использование: /confirm_payment <code>"
        )
        return
    code = args[0].strip()

    factory = async_session_factory()
    async with factory() as session:
        ok = await ce.mark_coupon_used(
            session, code=code, activated_via="ivan_manual"
        )
        if ok:
            coupon = await ce.get_coupon_by_code(session, code)
            await log_event(
                session,
                user_id=coupon.user_id if coupon else None,
                event="coupon_used",
                payload={"code": code, "confirmed_by": update.effective_user.id},
            )
        await session.commit()

    if ok:
        await update.effective_message.reply_text(
            f"✅ Купон `{code}` помечен использованным.",
            parse_mode="Markdown",
        )
    else:
        await update.effective_message.reply_text(
            f"❌ Не получилось пометить `{code}`. Возможные причины: купон не "
            "найден, уже use'ан, истёк по времени или не активен. "
            "Проверьте через /coupon_info.",
            parse_mode="Markdown",
        )
