import os

import pytest
from pydantic import ValidationError

from src.config.settings import Settings


def test_default_settings():
    os.environ.clear()
    os.environ["EMAIL_USERS"] = "test@example.com"
    os.environ["EMAIL_PASSWORDS"] = "secret"

    settings = Settings()
    assert settings.app.environment == "development"
    assert settings.app.poll_interval == 60
    assert settings.features.enable_ai is True


def test_feature_flag_override():
    os.environ.clear()
    os.environ["EMAIL_USERS"] = "test@example.com"
    os.environ["EMAIL_PASSWORDS"] = "secret"
    os.environ["FEATURE_ENABLE_AI"] = "false"

    settings = Settings()
    assert settings.features.enable_ai is False


def test_invalid_polling_interval():
    os.environ.clear()
    os.environ["EMAIL_USERS"] = "test@example.com"
    os.environ["EMAIL_PASSWORDS"] = "secret"
    os.environ["POLL_INTERVAL"] = "1"

    with pytest.raises(ValidationError):
        Settings()
