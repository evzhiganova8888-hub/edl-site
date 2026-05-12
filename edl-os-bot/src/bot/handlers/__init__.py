"""Регистрация хендлеров на python-telegram-bot Application."""
from __future__ import annotations

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from src.bot.handlers import (
    admin,
    audit,
    bug_report,
    consent,
    dialog,
    faq,
    privacy,
    quiz,
    refund,
    start,
)


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
    app.add_handler(CommandHandler("reset", start.reset_command))

    # Callback queries (inline buttons)
    app.add_handler(CallbackQueryHandler(consent.handle_consent, pattern=r"^consent:"))
    app.add_handler(CallbackQueryHandler(start.handle_menu_button, pattern=r"^menu:"))
    app.add_handler(CallbackQueryHandler(start.handle_segment_button, pattern=r"^segment:"))
    app.add_handler(CallbackQueryHandler(audit.start_purchase, pattern=r"^audit:start_purchase(?::(?:base|plus))?$"))
    app.add_handler(CallbackQueryHandler(audit.cancel_collection, pattern=r"^audit:cancel_collection$"))
    app.add_handler(CallbackQueryHandler(audit.handle_offer, pattern=r"^offer:"))
    app.add_handler(CallbackQueryHandler(refund.handle_refund_callback, pattern=r"^refund:request:"))
    app.add_handler(CallbackQueryHandler(privacy.handle_privacy_action, pattern=r"^privacy:"))
    app.add_handler(CallbackQueryHandler(quiz.handle_answer, pattern=r"^quiz:ans:"))
    app.add_handler(CallbackQueryHandler(quiz.handle_cancel, pattern=r"^quiz:cancel$"))
    app.add_handler(CallbackQueryHandler(faq.handle_show, pattern=r"^faq:show:"))
    app.add_handler(CallbackQueryHandler(admin.handle_admin_callback, pattern=r"^admin:"))
    app.add_handler(CallbackQueryHandler(bug_report.handle_callback, pattern=r"^bugreport:"))

    # Free-form text — FSM-маршрутизатор (audit / refund / lead / faq / dialog)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, dialog.handle_text))
