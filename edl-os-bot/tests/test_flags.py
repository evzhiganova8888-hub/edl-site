"""Feature flags: env-fallback и инвалидация кэша."""
from src.core.flags import FLAG_VITACONSULT_PUBLIC, _env_fallback, invalidate_cache


def test_env_fallback_for_vitaconsult():
    assert _env_fallback(FLAG_VITACONSULT_PUBLIC, default=False) is False


def test_env_fallback_unknown_key():
    assert _env_fallback("nonexistent_flag", default=False) is False
    assert _env_fallback("nonexistent_flag", default=True) is True


def test_invalidate_cache_no_error():
    # Просто не должно падать
    invalidate_cache()
    invalidate_cache("some_key")
