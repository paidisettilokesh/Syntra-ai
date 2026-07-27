from unittest.mock import MagicMock, patch

import pytest

from src.config.validator import StartupValidator
from src.domain.exceptions import InvalidConfiguration


def test_validator_mismatched_emails():
    with patch("src.config.validator.settings") as mock_settings:
        mock_settings.email.user_list = ["u1@gmail.com", "u2@gmail.com"]
        mock_settings.email.password_list = ["p1"]
        mock_settings.app.temp_directory = "data/temp"

        with patch("src.config.validator.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path.return_value = mock_path_instance
            with patch("src.config.validator.os.access", return_value=True):
                with pytest.raises(InvalidConfiguration) as exc_info:
                    StartupValidator.validate()
                assert "Number of EMAIL_USERS (2) must match EMAIL_PASSWORDS (1)" in str(exc_info.value)


def test_validator_missing_telegram_secrets():
    with patch("src.config.validator.settings") as mock_settings:
        mock_settings.email.user_list = ["u1@gmail.com"]
        mock_settings.email.password_list = ["p1"]
        mock_settings.app.temp_directory = "data/temp"
        mock_settings.features.enable_telegram = True
        mock_settings.notify.telegram_bot_token = None
        mock_settings.notify.telegram_chat_id = "chat_id"

        with patch("src.config.validator.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path.return_value = mock_path_instance
            with patch("src.config.validator.os.access", return_value=True):
                with pytest.raises(InvalidConfiguration) as exc_info:
                    StartupValidator.validate()
                assert "Telegram notifications are enabled (FEATURE_ENABLE_TELEGRAM=true) but TELEGRAM_BOT_TOKEN" in str(
                    exc_info.value
                )


def test_validator_directory_not_exists_creates_it():
    with patch("src.config.validator.settings") as mock_settings:
        mock_settings.email.user_list = ["u1@gmail.com"]
        mock_settings.email.password_list = ["p1"]
        mock_settings.app.temp_directory = "data/temp"
        mock_settings.features.enable_telegram = False

        with patch("src.config.validator.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = False
            mock_path.return_value = mock_path_instance
            with patch("src.config.validator.os.access", return_value=True):
                StartupValidator.validate()
                # Should call mkdir since path does not exist
                mock_path_instance.mkdir.assert_called()


def test_validator_directory_not_writable():
    with patch("src.config.validator.settings") as mock_settings:
        mock_settings.email.user_list = ["u1@gmail.com"]
        mock_settings.email.password_list = ["p1"]
        mock_settings.app.temp_directory = "data/temp"
        mock_settings.features.enable_telegram = False

        with patch("src.config.validator.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path.return_value = mock_path_instance
            # Return False for write access check
            with patch("src.config.validator.os.access", return_value=False):
                with pytest.raises(InvalidConfiguration) as exc_info:
                    StartupValidator.validate()
                assert "is not writable" in str(exc_info.value)
