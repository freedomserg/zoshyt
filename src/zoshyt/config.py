"""Налаштування з env через pydantic-settings.

Єдине джерело конфігурації для api і bot. Перелік змінних — крок 1
плану; B2_* читає лише rclone на VPS, SMTP_* не заводиться (ADR-0011).
"""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["dev", "prod"] = "dev"
    auth_mode: Literal["telegram", "dev"] = "telegram"
    telegram_bot_token: str
    webapp_url: str
    db_url: str
    admin_chat_id: int | None = None
    hc_api_url: str | None = None
    hc_bot_url: str | None = None
    hc_reminders_url: str | None = None

    @model_validator(mode="after")
    def dev_auth_forbidden_in_prod(self) -> "Settings":
        # CLAUDE.md: AUTH_MODE=dev у prod → процес МУСИТЬ впасти на старті.
        if self.app_env == "prod" and self.auth_mode == "dev":
            raise ValueError("AUTH_MODE=dev is forbidden when APP_ENV=prod")
        return self


@lru_cache
def get_settings() -> Settings:
    """Читає env один раз; api і bot викликають на старті."""
    return Settings()
