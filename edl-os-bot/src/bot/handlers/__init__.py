"""Registers all handlers on the python-telegram-bot Application."""
from __future__ import annotations

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from src.bot.handlers import audit, consent, dialog, faq, privacy, start


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
    app.add_handler(CommandHandler("reset", start.reset_command))

    # Callback queries (inline buttons)
    app.add_handler(CallbackQueryHandler(consent.handle_consent, pattern=r"^consent:"))
    app.add_handler(CallbackQueryHandler(start.handle_menu_button, pattern=r"^menu:"))
    app.add_handler(CallbackQueryHandler(start.handle_segment_button, pattern=r"^segment:"))

    # Free-form text — диалог через LLM (последним, чтобы не перехватывать команды)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, dialog.handle_text))
