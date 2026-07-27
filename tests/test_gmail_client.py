from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.clients.gmail_client import GmailClient


@pytest.fixture
def mock_gmail_settings():
    with patch("src.infrastructure.clients.gmail_client.settings") as mock_settings:
        mock_settings.IMAP_SERVER = "imap.gmail.com"
        mock_settings.email.imap_server = "imap.gmail.com"
        yield mock_settings


@pytest.mark.asyncio
@patch("src.infrastructure.clients.gmail_client.imaplib.IMAP4_SSL")
@patch("src.infrastructure.clients.gmail_client.process_attachment")
async def test_gmail_client_get_unseen_emails(mock_ocr_process, mock_imap_cls, mock_gmail_settings):
    mock_imap = MagicMock()
    mock_imap.search.return_value = ("OK", [b"1"])

    raw_email_bytes = b"""MIME-Version: 1.0
Subject: Test Email Subject
From: sender@example.com
Message-ID: <id123>
Content-Type: text/plain

This is a test plain text email body.
"""
    mock_imap.fetch.return_value = ("OK", [(None, raw_email_bytes)])
    mock_imap_cls.return_value = mock_imap

    client = GmailClient("user@gmail.com", "password")
    emails = await client.get_unseen_emails()

    assert len(emails) == 1
    assert emails[0].subject == "Test Email Subject"
    assert emails[0].sender == "sender@example.com"
    assert emails[0].body == "This is a test plain text email body."

    mock_imap.login.assert_called_once_with("user@gmail.com", "password")
    mock_imap.store.assert_called_once_with(b"1", "+FLAGS", "\\Seen")


@pytest.mark.asyncio
@patch("src.infrastructure.clients.gmail_client.imaplib.IMAP4_SSL")
async def test_gmail_client_connection_error(mock_imap_cls, mock_gmail_settings):
    mock_imap_cls.side_effect = Exception("Connection Failed")

    client = GmailClient("user@gmail.com", "password")
    emails = await client.get_unseen_emails()

    assert len(emails) == 0


@pytest.mark.asyncio
@patch("src.infrastructure.clients.gmail_client.imaplib.IMAP4_SSL")
async def test_gmail_client_search_failure(mock_imap_cls, mock_gmail_settings):
    mock_imap = MagicMock()
    # Search returns error status
    mock_imap.search.return_value = ("NO", [b""])
    mock_imap_cls.return_value = mock_imap

    client = GmailClient("user@gmail.com", "password")
    emails = await client.get_unseen_emails()
    assert len(emails) == 0


@pytest.mark.asyncio
@patch("src.infrastructure.clients.gmail_client.imaplib.IMAP4_SSL")
@patch("src.infrastructure.clients.gmail_client.process_attachment")
async def test_gmail_client_multipart_and_attachments(
    mock_ocr_process, mock_imap_cls, mock_gmail_settings
):
    mock_imap = MagicMock()
    mock_imap.search.return_value = ("OK", [b"1 2"])
    mock_imap_cls.return_value = mock_imap

    # 1. Message with valid attachment under 5MB
    raw_email_attachment_bytes = b"""MIME-Version: 1.0
Subject: Attachment test
From: sender@example.com
Message-ID: <id123>
Content-Type: multipart/mixed; boundary="boundary-1"

--boundary-1
Content-Type: text/plain

Plain text section.
--boundary-1
Content-Type: application/pdf; name="resume.pdf"
Content-Disposition: attachment; filename="resume.pdf"
Content-Transfer-Encoding: base64

ZHVtbXkgcGRmIGNvbnRlbnQ=
--boundary-1--
"""

    # 2. Message with giant attachment over 5MB
    giant_payload = b"x" * (6 * 1024 * 1024)  # 6MB
    import base64

    giant_base64 = base64.b64encode(giant_payload)
    raw_email_giant_bytes = (
        b'MIME-Version: 1.0\nSubject: Giant test\nFrom: s\nMessage-ID: <id456>\nContent-Type: multipart/mixed; boundary="boundary-2"\n\n--boundary-2\nContent-Type: text/plain\n\nGiant attachment mail.\n--boundary-2\nContent-Type: application/octet-stream; filename="giant.zip"\nContent-Disposition: attachment; filename="giant.zip"\nContent-Transfer-Encoding: base64\n\n'
        + giant_base64
        + b"\n--boundary-2--"
    )

    mock_imap.fetch.side_effect = [
        ("OK", [(None, raw_email_attachment_bytes)]),
        ("OK", [(None, raw_email_giant_bytes)]),
    ]

    mock_ocr_process.return_value = "Extracted PDF OCR text"

    client = GmailClient("user@gmail.com", "password")
    emails = await client.get_unseen_emails()

    assert len(emails) == 2
    # Verify first email parsed text and OCR
    assert emails[0].subject == "Attachment test"
    assert "Plain text section." in emails[0].body
    assert "[Attachment: resume.pdf]" in emails[0].attachment_text

    # Verify second email parsed text but skipped attachment
    assert emails[1].subject == "Giant test"
    assert emails[1].attachment_text == ""  # skipped due to 5MB threshold


def test_gmail_client_mime_decoding(mock_gmail_settings):
    client = GmailClient("user@gmail.com", "password")
    # Decode already raw string
    assert client._decode_mime_words("Plain Subject") == "Plain Subject"
    assert client._decode_mime_words(None) == ""
