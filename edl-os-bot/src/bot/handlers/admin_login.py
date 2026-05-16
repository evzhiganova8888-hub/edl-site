"""/admin_login и /admin_logout — in-bot admin session через access key."""
from __future__ import annotations

import hmac
import logging
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from src.admin.auth import is_admin_active
from src.core.config import settings
from src.core.notifications import send_to_admin_chat
from src.db.models import AdminSession, Event
from src.db.repos import get_or_create_user
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)

_RATE_LIMIT_PREFIX = "admin_login_attempts:"
_RATE_LIMIT_WINDOW = 600   # 10 минут
_RATE_LIMIT_MAX = 3
_LOCK_SECONDS = 3600       # 1 час блокировки


def _redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def _is_rate_limited(telegram_id: int) -> bool:
    r = _redis()
    try:
        key = f"{_RATE_LIMIT_PREFIX}{telegram_id}"
        count = await r.get(key)
        return count is not None and int(count) >= _RATE_LIMIT_MAX
    finally:
        await r.aclose()


async def _record_attempt(telegram_id: int) -> int:
    r = _redis()
    try:
        key = f"{_RATE_LIMIT_PREFIX}{telegram_id}"
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, _RATE_LIMIT_WINDOW)
        results = await pipe.execute()
        return int(results[0])
    finally:
        await r.aclose()


async def _lock_account(telegram_id: int) -> None:
    r = _redis()
    try:
        key = f"{_RATE_LIMIT_PREFIX}{telegram_id}"
        await r.set(key, _RATE_LIMIT_MAX + 1, ex=_LOCK_SECONDS)
    finally:
        await r.aclose()


async def admin_login_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/admin_login <KEY>."""
    user = update.effective_user
    msg = update.effective_message

    # Фича выключена если ключ не настроен
    if not settings.bot_admin_access_key:
        await msg.reply_text("Вход через access key не настроен. Обратитесь к команде EDL.")
        return

    # Парсим ключ
    args = context.args or []
    if not args:
        await msg.reply_text(
            "Использование: /admin_login <ваш_ключ>\n"
            "Ключ выдают Катя/Иван. Бот не печатает ключ в чат."
        )
        return

    provided_key = args[0]

    # Rate limit
    if await _is_rate_limited(user.id):
        await msg.reply_text(
            "Слишком много попыток. Попробуйте через час или напишите Кате/Ивану."
        )
        return

    # Проверка ключа через constant-time compare
    key_ok = hmac.compare_digest(provided_key, settings.bot_admin_access_key)
    if not key_ok:
        attempts = await _record_attempt(user.id)
        remaining = _RATE_LIMIT_MAX - attempts
        if remaining <= 0:
            await _lock_account(user.id)
            # Алерт в admin_chat
            factory = async_session_factory()
            async with factory() as session:
                await session.commit()
            logger.warning("Admin login locked for telegram_id=%s after %s attempts", user.id, attempts)
            await msg.reply_text(
                "Аккаунт временно заблокирован из-за превышения числа попыток. "
                "Попробуйте через час."
            )
        else:
            await msg.reply_text(f"Неверный ключ. Осталось попыток: {remaining}.")
        return

    # Ключ верный — создаём AdminSession
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.admin_session_hours)
    factory = async_session_factory()
    async with factory() as session:
        session.add(AdminSession(
            telegram_id=user.id,
            granted_by="access_key",
            expires_at=expires_at,
        ))
        db_user, _ = await get_or_create_user(session, telegram_id=user.id)
        session.add(Event(
            user_id=db_user.id,
            event="admin_session_granted",
            payload={
                "telegram_id": user.id,
                "granted_by": "access_key",
                "key_prefix": settings.bot_admin_access_key[:3],
                "expires_at": expires_at.isoformat(),
            },
        ))
        await session.commit()

    await msg.reply_text(
        f"Доступ открыт на {settings.admin_session_hours} часов. "
        "Используйте /admin для статистики, /applications, /mark_paid, "
        "/beta_summary, /emails_dump, /admin_logout."
    )
    logger.info("Admin session granted for telegram_id=%s", user.id)


async def admin_logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/admin_logout — отзывает текущую AdminSession."""
    user = update.effective_user
    msg = update.effective_message
    factory = async_session_factory()
    async with factory() as session:
        now = datetime.now(timezone.utc)
        stmt = (
            select(AdminSession)
            .where(AdminSession.telegram_id == user.id)
            .where(AdminSession.expires_at > now)
            .where(AdminSession.revoked_at.is_(None))
        )
        sessions = (await session.execute(stmt)).scalars().all()
        for s in sessions:
            s.revoked_at = now
        db_user, _ = await get_or_create_user(session, telegram_id=user.id)
        session.add(Event(
            user_id=db_user.id,
            event="admin_session_revoked",
            payload={"telegram_id": user.id, "sessions_revoked": len(sessions)},
        ))
        await session.commit()

    await msg.reply_text("Сессия завершена. До следующего /admin_login.")


async def admin_login_hint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Колбэк admin_login:hint — подсказка как войти."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Введите команду /admin_login <ваш_ключ>.\n"
        "Ключ выдают Катя/Иван. Бот не печатает ваш ключ в чат и не сохраняет его — "
        "только проверяет соответствие."
    )
