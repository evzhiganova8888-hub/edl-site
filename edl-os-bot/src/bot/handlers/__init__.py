"""Регистрация хендлеров на python-telegram-bot Application."""
from __future__ import annotations

import logging
import traceback

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.bot.handlers import (
    admin,
    admin_login,
    audit,
    bug_report,
    bugs,
    checkup,
    consent,
    dialog,
    faq,
    feedback as feedback_handler,
    privacy,
    quiz,
    refund,
    start,
)
from src.core.config import settings
from src.db.repos import log_event
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)


async def _global_error_handler(
    update: object, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Ловит все неперехваченные exception. Юзер получает понятный fallback,
    мы — лог + запись в events.

    Без этого handler exception проглатывается python-telegram-bot и юзер
    видит «ничего не происходит» (см. inv_id NULL bug 12.05.2026).
    """
    err = context.error
    tb = "".join(traceback.format_exception(type(err), err, err.__traceback__)) if err else "<no error>"
    logger.error("Unhandled exception in handler: %s\n%s", err, tb)

    user_id = None
    if isinstance(update, Update):
        if update.effective_user:
            user_id = update.effective_user.id
        msg = update.effective_message
        if msg:
            try:
                await msg.reply_text(
                    "Что-то пошло не так на нашей стороне. Я уже сообщил команде.\n"
                    f"Если срочно — напишите Ивану: @{settings.sales_username}.\n"
                    "Чтобы вернуться в меню: /menu"
                )
            except Exception:
                logger.exception("Failed to notify user about error")

    # Лог в БД для VoC
    try:
        factory = async_session_factory()
        async with factory() as session:
            await log_event(
                session,
                user_id=user_id,
                event="unhandled_exception",
                payload={
                    "error": str(err)[:500] if err else None,
                    "type": type(err).__name__ if err else None,
                    "tb_tail": tb[-1500:],
                },
            )
            await session.commit()
    except Exception:
        logger.exception("Failed to log unhandled_exception event")


def register(app: Application) -> None:
    # Commands
    app.add_handler(CommandHandler("start", start.start_command))
    app.add_handler(CommandHandler("help", start.help_command))
    app.add_handler(CommandHandler("menu", start.menu_command))
    app.add_handler(CommandHandler("faq", faq.faq_command))
    app.add_handler(CommandHandler("privacy", privacy.privacy_command))
    app.add_handler(CommandHandler("delete_my_data", privacy.delete_my_data_command))
    app.add_handler(CommandHandler("export_my_data", privacy.export_my_data_command))
    app.add_handler(CommandHandler("audit", audit.audit_command))
    app.add_handler(CommandHandler("audit_sample", audit.audit_sample_command))
    app.add_handler(CommandHandler("refund", refund.refund_command))
    app.add_handler(CommandHandler("quiz", quiz.quiz_command))
    app.add_handler(CommandHandler("admin", admin.admin_command))
    app.add_handler(CommandHandler("admin_login", admin_login.admin_login_command))
    app.add_handler(CommandHandler("admin_logout", admin_login.admin_logout_command))
    app.add_handler(CommandHandler("mark_paid", admin.mark_paid_command))
    app.add_handler(CommandHandler("applications", admin.applications_command))
    app.add_handler(CommandHandler("checkup", checkup.checkup_command))
    app.add_handler(CommandHandler("bugs", bugs.bugs_command))
    app.add_handler(CommandHandler("feedback", feedback_handler.feedback_command))
    app.add_handler(CommandHandler("reset", start.reset_command))

    # Callback queries (inline buttons)
    app.add_handler(CallbackQueryHandler(consent.handle_consent, pattern=r"^consent:"))
    app.add_handler(CallbackQueryHandler(start.handle_menu_button, pattern=r"^menu:"))
    app.add_handler(CallbackQueryHandler(start.handle_segment_button, pattern=r"^segment:"))
    app.add_handler(CallbackQueryHandler(audit.start_purchase, pattern=r"^audit:start_purchase(?::(?:base|plus))?$"))
    app.add_handler(CallbackQueryHandler(audit.cancel_collection, pattern=r"^audit:cancel_collection$"))
    app.add_handler(CallbackQueryHandler(audit.notify_waiting, pattern=r"^audit:notify_waiting$"))
    app.add_handler(CallbackQueryHandler(audit.handle_offer, pattern=r"^offer:"))
    app.add_handler(CallbackQueryHandler(refund.handle_refund_callback, pattern=r"^refund:request:"))
    app.add_handler(CallbackQueryHandler(privacy.handle_privacy_action, pattern=r"^privacy:"))
    app.add_handler(CallbackQueryHandler(quiz.handle_answer, pattern=r"^quiz:ans:"))
    app.add_handler(CallbackQueryHandler(quiz.handle_cancel, pattern=r"^quiz:cancel$"))
    app.add_handler(CallbackQueryHandler(faq.handle_show, pattern=r"^faq:show:"))
    app.add_handler(CallbackQueryHandler(admin.handle_admin_callback, pattern=r"^admin:"))
    app.add_handler(CallbackQueryHandler(admin_login.admin_login_hint, pattern=r"^admin_login:hint$"))
    app.add_handler(CallbackQueryHandler(checkup.handle_checkup_callback, pattern=r"^checkup:"))
    app.add_handler(CallbackQueryHandler(bug_report.handle_callback, pattern=r"^bugreport:"))
    app.add_handler(CallbackQueryHandler(bugs.handle_bug_callback, pattern=r"^bug:"))
    app.add_handler(CallbackQueryHandler(feedback_handler.handle_callback, pattern=r"^feedback:"))
    app.add_handler(CallbackQueryHandler(feedback_handler.handle_waitlist_callback, pattern=r"^waitlist:"))

    # Free-form text — FSM-маршрутизатор (audit / refund / lead / faq / dialog)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, dialog.handle_text))

    # Глобальный error_handler: ловим всё неперехваченное, чтобы юзер не
    # видел «ничего не происходит» при exception (см. P0 bug inv_id NULL).
    app.add_error_handler(_global_error_handler)
