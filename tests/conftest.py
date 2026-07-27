import os
from unittest.mock import AsyncMock, MagicMock

import pytest

# Set environment variables for testing
os.environ["POLL_INTERVAL"] = "10"
os.environ["EMAIL_USERS"] = "test@example.com"
os.environ["EMAIL_PASSWORDS"] = "password"
os.environ["GROQ_API_KEY"] = "test_groq"


@pytest.fixture
def mock_mail_client():
    client = MagicMock()
    client.get_unseen_emails = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_ai_provider():
    provider = MagicMock()
    provider.analyze = AsyncMock()
    return provider


@pytest.fixture
def mock_repository():
    repo = MagicMock()
    repo.is_email_processed.return_value = False
    return repo
