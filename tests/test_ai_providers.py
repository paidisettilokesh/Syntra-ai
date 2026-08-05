from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.exceptions import AIProviderError
from src.domain.models import EmailMetadata
from src.infrastructure.clients.ai_providers import ChainAIProvider
from src.infrastructure.llm.base import ILLMProvider


@pytest.fixture
def mock_llm_provider():
    llm = MagicMock(spec=ILLMProvider)
    llm.provider_name = "MockLLM"
    return llm


@pytest.mark.asyncio
async def test_chain_ai_provider_analyze_success(mock_llm_provider):
    mock_llm_provider.complete = AsyncMock(return_value="""
    {
        "category": "Job Offer",
        "importance_score": 8,
        "summary": "You have a job offer from Tech Corp.",
        "reasoning": "Standard job offer subject.",
        "action_required": true,
        "confidence_score": 0.95
    }
    """)

    provider = ChainAIProvider(llm_provider=mock_llm_provider)
    email = EmailMetadata(
        message_id="123",
        sender="hr@techcorp.com",
        subject="Job Offer Details",
        body="Congratulations!",
        attachment_text="",
    )

    res = await provider.analyze(email)

    assert res.category == "Job Offer"
    assert res.importance_score == 8
    assert res.action_required is True
    mock_llm_provider.complete.assert_called_once()


@pytest.mark.asyncio
async def test_chain_ai_provider_verify_email_success(mock_llm_provider):
    mock_llm_provider.complete = AsyncMock(return_value="""
    {
        "is_legitimate": true,
        "confidence": 95.0,
        "risk_level": "Low",
        "reason": "Legitimate job offer email.",
        "threats": []
    }
    """)

    provider = ChainAIProvider(llm_provider=mock_llm_provider)
    email = EmailMetadata(
        message_id="123",
        sender="hr@techcorp.com",
        subject="Job Offer Details",
        body="Congratulations!",
    )

    res = await provider.verify_email(email)

    assert res.is_legitimate is True
    assert res.risk_level == "Low"
    mock_llm_provider.complete.assert_called_once()


@pytest.mark.asyncio
async def test_chain_ai_provider_all_llm_fail(mock_llm_provider):
    mock_llm_provider.complete = AsyncMock(side_effect=AIProviderError("All providers failed"))

    provider = ChainAIProvider(llm_provider=mock_llm_provider)
    email = EmailMetadata(
        message_id="123",
        sender="hr@techcorp.com",
        subject="Job Offer Details",
        body="Congratulations!",
    )

    with pytest.raises(AIProviderError) as exc_info:
        await provider.analyze(email)
    assert "All providers failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_chain_ai_provider_invalid_json(mock_llm_provider):
    mock_llm_provider.complete = AsyncMock(return_value="""
    {
        "importance_score": 5,
        "summary": "Missing required category field"
    }
    """)

    provider = ChainAIProvider(llm_provider=mock_llm_provider)
    email = EmailMetadata(message_id="123", sender="s", subject="sub", body="body")

    with pytest.raises(AIProviderError) as exc_info:
        await provider.analyze(email)
    assert "Invalid AI Response format" in str(exc_info.value)


@pytest.mark.asyncio
async def test_prompt_truncation_and_sanitization(mock_llm_provider):
    mock_llm_provider.complete = AsyncMock(return_value="""
    {
        "category": "Informational",
        "importance_score": 5,
        "summary": "Long truncated email.",
        "reasoning": "Fits standard structure.",
        "action_required": false,
        "confidence_score": 0.90
    }
    """)

    provider = ChainAIProvider(llm_provider=mock_llm_provider)
    long_body = "x" * 25000
    email = EmailMetadata(
        message_id="123", sender="s", subject="sub", body=long_body, attachment_text=""
    )

    await provider.analyze(email)

    mock_llm_provider.complete.assert_called_once()
    args, kwargs = mock_llm_provider.complete.call_args
    system_prompt, user_prompt = args
    assert "<UNTRUSTED_EMAIL_CONTENT>" in user_prompt
    assert len(user_prompt) <= 22000
