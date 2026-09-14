"""Settings: збирається з env-значень; AUTH_MODE=dev у prod — помилка."""

import pytest
from pydantic import ValidationError

from zoshyt.config import Settings

# _env_file=None — щоб тест не читав локальний .env і був детермінованим.


def test_settings_from_values() -> None:
    settings = Settings(
        _env_file=None,
        telegram_bot_token="123:fake-token",
        webapp_url="https://example.invalid",
        db_url="postgresql+asyncpg://u:p@localhost/zoshyt",
    )

    assert settings.app_env == "dev"
    assert settings.auth_mode == "telegram"
    assert settings.admin_chat_id is None


def test_dev_auth_forbidden_in_prod() -> None:
    with pytest.raises(ValidationError, match="AUTH_MODE=dev is forbidden"):
        Settings(
            _env_file=None,
            app_env="prod",
            auth_mode="dev",
            telegram_bot_token="123:fake-token",
            webapp_url="https://example.invalid",
            db_url="postgresql+asyncpg://u:p@localhost/zoshyt",
        )
