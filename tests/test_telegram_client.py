from unittest.mock import MagicMock, patch

import pytest

from src.domain.models import AnalysisResult, EmailMetadata
from src.infrastructure.clients.telegram_client import TelegramNotificationService


@pytest.fixture
def mock_telegram_env():
    with patch("src.infrastructure.clients.telegram_client.settings") as mock_settings:
        mock_settings.notify.telegram_bot_token.get_secret_value.return_value = (
            "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        )
        mock_settings.notify.telegram_chat_id.get_secret_value.return_value = "987654321"
        mock_settings.features.enable_telegram = True
        yield mock_settings


def test_telegram_client_init(mock_telegram_env):
    service = TelegramNotificationService()
    assert service.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    assert service.chat_id == "987654321"


@patch("src.infrastructure.clients.telegram_client.requests.post")
def test_telegram_send_alert_success(mock_post, mock_telegram_env):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True, "result": {"message_id": 999}}
    mock_post.return_value = mock_response

    service = TelegramNotificationService()
    email = EmailMetadata(
        message_id="msg-101",
        sender="hr@company.com",
        subject="Interview Invitation",
        body="We invite you for an interview.",
    )
    analysis = AnalysisResult(
        category="Interview",
        importance_score=9,
        summary="Interview scheduled.",
        reasoning="Explicit interview request.",
        action_required=True,
        confidence_score=0.98,
    )

    service.send_alert(email, analysis)
    assert mock_post.called
    args, kwargs = mock_post.call_args
    assert (
        "https://api.telegram.org/bot123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11/sendMessage"
        in args[0]
    )
    assert kwargs["json"]["chat_id"] == "987654321"
    assert "Interview Invitation" in kwargs["json"]["text"]


@patch("src.infrastructure.clients.telegram_client.requests.post")
def test_telegram_send_alert_missing_credentials(mock_post):
    with patch("src.infrastructure.clients.telegram_client.settings") as mock_settings:
        mock_settings.notify.telegram_bot_token = None
        mock_settings.notify.telegram_chat_id = None
        mock_settings.features.enable_telegram = True

        service = TelegramNotificationService()
        email = EmailMetadata(
            message_id="msg-102",
            sender="hr@company.com",
            subject="Interview",
            body="Body",
        )
        analysis = AnalysisResult(
            category="Interview",
            importance_score=9,
            summary="Interview.",
            reasoning="Reason.",
            action_required=True,
            confidence_score=0.9,
        )

        from src.domain.exceptions import NotificationError

        with pytest.raises(NotificationError):
            service.send_alert(email, analysis)
        assert not mock_post.called
