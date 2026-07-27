from unittest.mock import MagicMock, patch

import pytest

from src.domain.models import AnalysisResult, EmailMetadata
from src.infrastructure.clients.twilio_client import TwilioWhatsAppService


@pytest.fixture
def mock_twilio_env():
    with patch("src.infrastructure.clients.twilio_client.settings") as mock_settings:
        mock_settings.notify.twilio_account_sid.get_secret_value.return_value = "ACmock"
        mock_settings.notify.twilio_auth_token.get_secret_value.return_value = "authmock"
        mock_settings.notify.from_whatsapp_number = "whatsapp:+14155238886"
        mock_settings.notify.to_whatsapp_number = "whatsapp:+919493909629"
        yield mock_settings


@patch("src.infrastructure.clients.twilio_client.Client")
def test_twilio_client_init(mock_client_cls, mock_twilio_env):
    service = TwilioWhatsAppService()
    assert service.client is not None
    mock_client_cls.assert_called_once_with("ACmock", "authmock")


@patch("src.infrastructure.clients.twilio_client.Client")
def test_twilio_send_alert(mock_client_cls, mock_twilio_env):
    mock_client_instance = MagicMock()
    mock_client_cls.return_value = mock_client_instance

    service = TwilioWhatsAppService()

    email = EmailMetadata(
        message_id="123",
        sender="sender@example.com",
        subject="Important Announcement",
        body="Body of email...",
        attachment_text="",
    )

    analysis = AnalysisResult(
        category="Security",
        importance_score=9,
        summary="A security breach was reported.",
        reasoning="Critical alert details.",
        action_required=True,
        confidence_score=1.0,
    )

    service.send_alert(email, analysis)

    mock_client_instance.messages.create.assert_called_once()
    args, kwargs = mock_client_instance.messages.create.call_args
    assert kwargs["from_"] == "whatsapp:+14155238886"
    assert kwargs["to"] == "whatsapp:+919493909629"
    assert "*Importance:* 9/10" in kwargs["body"]
    assert "Security" in kwargs["body"]
