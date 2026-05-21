"""Application configuration loaded from environment."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_PAYMENT_MODES = {"stub", "manual", "yookassa"}


class Settings(BaseSettings):
    """Single source of truth for runtime config."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"

    # Telegram
    bot_token: str = ""
    bot_username: str = "edl_os_bot"
    admin_user_ids_raw: str = Field(default="", alias="ADMIN_USER_IDS")
    admin_chat_id: int | None = None

    # Webhook (optional). If empty — polling mode.
    webhook_base_url: str = ""
    webhook_secret_token: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://edl:edl@postgres:5432/edl"
    sync_database_url: str = "postgresql://edl:edl@postgres:5432/edl"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"
    anthropic_max_tokens: int = 600
    anthropic_base_url: str = ""

    # PAYMENT_MODE: "stub" | "manual" | "yookassa".
    # - stub: Application создаётся, status=awaiting_manual_payment,
    #   Иван/Катя помечают /mark_paid вручную. Никаких invoice не генерируется.
    # - manual: устаревший синоним stub (для обратной совместимости).
    # - yookassa: создаётся invoice URL через ЮKassa API.
    # Май-июнь 2026: работаем в stub, ЮKassa на модерации.
    payment_mode: str = "stub"

    @field_validator("payment_mode")
    @classmethod
    def _validate_payment_mode(cls, v: str) -> str:
        if v not in _VALID_PAYMENT_MODES:
            raise ValueError(f"PAYMENT_MODE must be one of {_VALID_PAYMENT_MODES}, got {v!r}")
        return v

    # ЮKassa
    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""

    # Admin session (in-bot access key)
    bot_admin_access_key: str = ""  # пустой — фича выключена
    admin_session_hours: int = 8

    # Branding / links
    channel_url: str = "https://t.me/edl_os"
    sales_username: str = "lvanKhudyakov"
    calendly_url: str = "https://calendly.com/evzhiganova8888/30min"
    site_url: str = "https://elephantdreams.ru"
    privacy_policy_url: str = "https://elephantdreams.ru/legal/privacy.html"
    offer_url: str = "https://elephantdreams.ru/legal/offer.html"
    offer_checkup_url: str = "https://elephantdreams.ru/legal/offer-checkup-2026-05.html"
    privacy_policy_version: str = "2026-05-11"

    # Mini-Чекап v2: внутренний токен для GET /internal/quiz/{id}
    internal_api_token: str = ""

    # Toggle (§10)
    vitaconsult_public: bool = False

    # Working hours (МСК)
    working_hours_start: int = 10
    working_hours_end: int = 19
    timezone: str = "Europe/Moscow"

    @property
    def admin_user_ids(self) -> list[int]:
        raw = self.admin_user_ids_raw.replace(" ", "")
        return [int(x) for x in raw.split(",") if x]

    @property
    def use_webhook(self) -> bool:
        return bool(self.webhook_base_url)

    @property
    def normalized_database_url(self) -> str:
        """Railway даёт postgresql://, SQLAlchemy asyncpg требует postgresql+asyncpg://."""
        url = self.database_url
        if url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


@lru_cache(maxsize=1)
def _settings() -> Settings:
    return Settings()


settings = _settings()
