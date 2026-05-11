"""Команды /privacy, /delete_my_data, /export_my_data (152-ФЗ, §13)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.bot import texts
from src.core.config import settings
from src.db.repos import get_or_create_user, log_event, log_pd_access
from src.db.session import async_session_factory


def _privacy_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📜 Политика", url=settings.privacy_policy_url)],
            [InlineKeyboardButton("📤 Выгрузить мои данные", callback_data="privacy:export")],
            [InlineKeyboardButton("🗑 Удалить мои данные", callback_data="privacy:delete")],
            [InlineKeyboardButton("← В главное меню", callback_data="menu:main")],
        ]
    )


async def handle_privacy_action(update, context):
    """Callback `privacy:export` / `privacy:delete`."""
    query = update.callback_query
    await query.answer()
    action = (query.data or "").split(":", 1)[1] if ":" in (query.data or "") else ""
    if action == "export":
        await export_my_data_command(update, context)
    elif action == "delete":
        await delete_my_data_command(update, context)


def _user_payload(user) -> dict:
    return {
        "telegram_id": user.telegram_id,
        "telegram_username": user.telegram_username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "segment": user.segment,
        "sub_profile": user.sub_profile,
        "stage": user.stage,
        "consent_pd_given_at": user.consent_pd_given_at.isoformat()
        if user.consent_pd_given_at
        else None,
        "consent_pd_version": user.consent_pd_version,
        "consent_marketing_given_at": user.consent_marketing_given_at.isoformat()
        if user.consent_marketing_given_at
        else None,
        "consent_offer_accepted_at": user.consent_offer_accepted_at.isoformat()
        if user.consent_offer_accepted_at
        else None,
        "email": user.email,
        "phone": user.phone,
        "company_name": user.company_name,
        "company_size": user.company_size,
        "company_revenue_range": user.company_revenue_range,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


async def privacy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await log_pd_access(
            session,
            actor=str(update.effective_user.id),
            user_id=user.id,
            action="read",
            fields=list(_user_payload(user).keys()),
        )
        await session.commit()
        payload = _user_payload(user)

    body = [texts.PRIVACY_HEADER, ""]
    if user.consent_pd_given_at:
        body.append(
            f"Согласие на ПД зафиксировано: {user.consent_pd_given_at.strftime('%Y-%m-%d %H:%M')} "
            f"(версия {user.consent_pd_version})."
        )
    else:
        body.append("Согласие на ПД пока не дано.")
    body.append("")
    body.append("Что у нас сохранено:")
    for key, value in payload.items():
        if value not in (None, ""):
            body.append(f"• {key}: {value}")
    body.append("")
    body.append(f"Оператор: ИП Жиганова Е. В., политика: {settings.privacy_policy_url}")

    await update.effective_message.reply_text(
        "\n".join(body), reply_markup=_privacy_keyboard()
    )


async def delete_my_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        # Стираем ПД, но оставляем запись для аудита 152-ФЗ.
        user.first_name = None
        user.last_name = None
        user.email = None
        user.phone = None
        user.company_name = None
        user.consent_pd_given_at = None
        user.consent_marketing_given_at = None
        await log_pd_access(
            session,
            actor=str(update.effective_user.id),
            user_id=user.id,
            action="delete",
            fields=["first_name", "last_name", "email", "phone", "company_name"],
        )
        await log_event(session, user_id=user.id, event="pd_deleted")
        await session.commit()

    await update.effective_message.reply_text(
        "Готово. Ваши персональные данные удалены. Если захотите вернуться — "
        "просто напишите /start."
    )


async def export_my_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        payload = _user_payload(user)
        await log_pd_access(
            session,
            actor=str(update.effective_user.id),
            user_id=user.id,
            action="export",
            fields=list(payload.keys()),
        )
        await log_event(session, user_id=user.id, event="pd_exported")
        await session.commit()

    payload["_exported_at"] = datetime.now(timezone.utc).isoformat()
    text = "```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```"
    await update.effective_message.reply_text(text, parse_mode="Markdown")
