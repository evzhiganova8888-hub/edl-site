"""/audit и /audit_sample — Бизнес-чекап (§7.4, §7.5 ТЗ v3).

На Этапе 1: показываем описание + гарантию + заглушку «оплата подключим в Спринте 2».
На Этапе 2 здесь будет реальный Robokassa invoice.
"""
from __future__ import annotations

from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from src.bot import keyboards, texts
from src.db.repos import create_application, get_or_create_user, log_event
from src.db.session import async_session_factory

_AUDIT_SAMPLE_PDF = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "audit_sample.pdf"


async def audit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await create_application(
            session,
            user=user,
            type="audit",
            source="audit_intent",
        )
        await log_event(session, user_id=user.id, event="audit_intro_shown")
        await session.commit()

    text = (
        f"{texts.AUDIT_INTRO}\n\n"
        "Оплату подключим следующим этапом разработки (Спринт 2) — нужна "
        "аккредитация Robokassa у ИП и юр-консультация. Пока — можно "
        f"посмотреть пример отчёта или написать Ивану напрямую."
    )
    await update.effective_message.reply_text(
        text, reply_markup=keyboards.audit_pay_keyboard()
    )


async def audit_sample_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    factory = async_session_factory()
    async with factory() as session:
        user, _ = await get_or_create_user(session, telegram_id=update.effective_user.id)
        await log_event(session, user_id=user.id, event="audit_sample_requested")
        await session.commit()

    if _AUDIT_SAMPLE_PDF.exists():
        await update.effective_message.reply_text(texts.AUDIT_SAMPLE_INTRO)
        with _AUDIT_SAMPLE_PDF.open("rb") as f:
            await update.effective_message.reply_document(
                document=f,
                filename="EDL_OS_audit_sample.pdf",
            )
    else:
        await update.effective_message.reply_text(
            texts.AUDIT_SAMPLE_NOT_READY,
            reply_markup=keyboards.audit_pay_keyboard(),
        )
