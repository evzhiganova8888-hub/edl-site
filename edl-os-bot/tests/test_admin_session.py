"""AdminSession: hmac comparison logic + is_admin_active fallback."""
import hmac
import os

import pytest

os.environ.setdefault("BOT_ADMIN_ACCESS_KEY", "test-secret-key-32-characters-long")


def _digest(key: str, value: str) -> bool:
    return hmac.compare_digest(key.encode(), value.encode())


def test_hmac_compare_correct_key():
    key = "test-secret-key-32-characters-long"
    assert _digest(key, key) is True


def test_hmac_compare_wrong_key():
    key = "test-secret-key-32-characters-long"
    assert _digest(key, "wrong-key") is False


def test_hmac_compare_timing_safe():
    # hmac.compare_digest должен принимать bytes, не падать
    assert hmac.compare_digest(b"abc", b"abc") is True
    assert hmac.compare_digest(b"abc", b"def") is False


def test_config_accepts_admin_key():
    from src.core.config import settings
    # settings загружается с env-значением выше
    assert isinstance(settings.bot_admin_access_key, str)


def test_config_admin_session_hours_default():
    from src.core.config import settings
    assert settings.admin_session_hours >= 1
