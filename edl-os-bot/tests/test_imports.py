"""Smoke-импорты — гарантия, что все модули корректно собираются."""


def test_import_main():
    import src.main  # noqa: F401


def test_import_handlers():
    from src.bot.handlers import (
        admin,
        admin_login,
        audit,
        checkup,
        consent,
        dialog,
        faq,
        lead_capture,
        privacy,
        quiz,
        refund,
        start,
    )  # noqa: F401


def test_import_core():
    from src.core import (
        checkup_questions,
        checkup_report,
        config,
        consent,
        contact,
        faq,
        flags,
        handoff,
        llm,
        notifications,
        offer,
        pd_sanitize,
        prompts,
        quiz,
        scope_guard,
        segment,
        stickers,
        working_hours,
    )  # noqa: F401
    from src.core.payments import StubPaymentClient  # noqa: F401


def test_import_tasks():
    from src.tasks import celery_app, refund_check  # noqa: F401


def test_import_admin():
    from src.admin import auth, routes  # noqa: F401


def test_import_db():
    from src.db import models, repos, session  # noqa: F401


def test_settings_loaded():
    from src.core.config import settings

    assert settings.bot_username == "edl_os_bot"
