"""Smoke-импорты — гарантия, что все модули корректно собираются."""


def test_import_main():
    import src.main  # noqa: F401


def test_import_handlers():
    from src.bot.handlers import audit, consent, dialog, faq, privacy, start  # noqa: F401


def test_import_core():
    from src.core import config, consent, handoff, llm, pd_sanitize, prompts, segment, stickers, working_hours  # noqa: F401


def test_import_db():
    from src.db import models, repos, session  # noqa: F401


def test_settings_loaded():
    from src.core.config import settings

    assert settings.bot_username == "edl_os_bot"
