"""Application configuration loaded from environment."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    anthropic_max_tokens: int = 1024

    # Robokassa
    robokassa_merchant_login: str = ""
    robokassa_password_1: str = ""
    robokassa_password_2: str = ""
    robokassa_is_test: int = 1
    # PAYMENT_MODE: "manual" | "robokassa".
    # - manual: бот собирает контакты + оферту, шлёт детальный бриф Ивану в
    #   Sales-чат, Иван оформляет счёт через бухгалтерию, после прихода денег
    #   помечает оплату через POST /admin/applications/{id}/mark-paid.
    # - robokassa: создаётся invoice URL, пользователь оплачивает картой,
    #   ResultURL callback автоматом ставит status=paid.
    # Май 2026: ждём активацию Robokassa, работаем в manual. В июне переключим.
    payment_mode: str = "manual"

    # ЮKassa
    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""

    # Branding / links
    channel_url: str = "https://t.me/edl_os"
    sales_username: str = "lvanKhudyakov"
    calendly_url: str = "https://calendly.com/evzhiganova8888/30min"
    site_url: str = "https://elephantdreams.ru"
    privacy_policy_url: str = "https://elephantdreams.ru/legal/privacy.html"
    offer_url: str = "https://elephantdreams.ru/legal/offer.html"
    privacy_policy_version: str = "2026-05-11"

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


@lru_cache(maxsize=1)
def _settings() -> Settings:
    return Settings()


settings = _settings()
