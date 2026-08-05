from unittest.mock import AsyncMock, MagicMock, patch

import groq
import pytest

from src.domain.exceptions import AIProviderError
from src.infrastructure.llm.fallback_provider import FallbackLLMProvider
from src.infrastructure.llm.groq_provider import GroqProvider
from src.infrastructure.llm.openrouter_provider import OpenRouterProvider


@pytest.fixture
def mock_groq_settings():
    with patch("src.infrastructure.llm.groq_provider.settings") as mock_s:
        mock_s.ai.groq_api_key.get_secret_value.return_value = "groq_key"
        yield mock_s


@pytest.fixture
def mock_openrouter_settings():
    with patch("src.infrastructure.llm.openrouter_provider.settings") as mock_s:
        mock_s.ai.openrouter_api_key.get_secret_value.return_value = "openrouter_key"
        yield mock_s


# ── GroqProvider Tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_groq_success(mock_groq_settings):
    with patch("src.infrastructure.llm.groq_provider.AsyncGroq") as mock_client_cls:
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content='{"status": "ok"}'))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_client_cls.return_value = mock_client

        provider = GroqProvider()
        res = await provider.complete("sys", "user")

        assert res == '{"status": "ok"}'
        mock_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_groq_rate_limit(mock_groq_settings):
    with patch("src.infrastructure.llm.groq_provider.AsyncGroq") as mock_client_cls:
        mock_client = MagicMock()
        # Mock RateLimitError
        rate_limit_err = groq.RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429, headers={}),
            body={},
        )
        mock_client.chat.completions.create = AsyncMock(side_effect=rate_limit_err)
        mock_client_cls.return_value = mock_client

        provider = GroqProvider()
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(AIProviderError) as exc_info:
                await provider.complete("sys", "user")

        assert "Groq provider failed on all models" in str(exc_info.value)
        # Should attempt primary 3 times (0, 1, 2 retries) and fallback 3 times (0, 1, 2 retries) = 6 total attempts
        assert mock_client.chat.completions.create.call_count == 6


@pytest.mark.asyncio
async def test_groq_timeout(mock_groq_settings):
    with patch("src.infrastructure.llm.groq_provider.AsyncGroq") as mock_client_cls:
        mock_client = MagicMock()
        timeout_err = groq.APITimeoutError(request=MagicMock())
        mock_client.chat.completions.create = AsyncMock(side_effect=timeout_err)
        mock_client_cls.return_value = mock_client

        provider = GroqProvider()
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(AIProviderError):
                await provider.complete("sys", "user")

        assert mock_client.chat.completions.create.call_count == 6


@pytest.mark.asyncio
async def test_groq_connection_error(mock_groq_settings):
    with patch("src.infrastructure.llm.groq_provider.AsyncGroq") as mock_client_cls:
        mock_client = MagicMock()
        conn_err = groq.APIConnectionError(request=MagicMock())
        mock_client.chat.completions.create = AsyncMock(side_effect=conn_err)
        mock_client_cls.return_value = mock_client

        provider = GroqProvider()
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(AIProviderError):
                await provider.complete("sys", "user")

        assert mock_client.chat.completions.create.call_count == 6


@pytest.mark.asyncio
async def test_groq_500_error(mock_groq_settings):
    with patch("src.infrastructure.llm.groq_provider.AsyncGroq") as mock_client_cls:
        mock_client = MagicMock()
        server_err = groq.InternalServerError(
            message="Internal Server Error",
            response=MagicMock(status_code=500, headers={}),
            body={},
        )
        mock_client.chat.completions.create = AsyncMock(side_effect=server_err)
        mock_client_cls.return_value = mock_client

        provider = GroqProvider()
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(AIProviderError):
                await provider.complete("sys", "user")

        assert mock_client.chat.completions.create.call_count == 6


# ── OpenRouterProvider Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_openrouter_success(mock_openrouter_settings):
    with patch("src.infrastructure.llm.openrouter_provider.AsyncOpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content='{"result": "openrouter_ok"}'))
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_client_cls.return_value = mock_client

        provider = OpenRouterProvider()
        res = await provider.complete("sys", "user")

        assert res == '{"result": "openrouter_ok"}'
        mock_client.chat.completions.create.assert_called_once()
        # Primary model used first
        assert (
            mock_client.chat.completions.create.call_args[1]["model"] == "google/gemini-2.5-flash"
        )


@pytest.mark.asyncio
async def test_openrouter_model_failure_cascade(mock_openrouter_settings):
    with patch("src.infrastructure.llm.openrouter_provider.AsyncOpenAI") as mock_client_cls:
        mock_client = MagicMock()
        success_completion = MagicMock()
        success_completion.choices = [
            MagicMock(message=MagicMock(content='{"result": "deepseek_ok"}'))
        ]

        # First model fails, second succeeds
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[Exception("Gemini Flash error"), success_completion]
        )
        mock_client_cls.return_value = mock_client

        provider = OpenRouterProvider()
        res = await provider.complete("sys", "user")

        assert res == '{"result": "deepseek_ok"}'
        assert mock_client.chat.completions.create.call_count == 2
        calls = mock_client.chat.completions.create.call_args_list
        assert calls[0][1]["model"] == "google/gemini-2.5-flash"
        assert calls[1][1]["model"] == "deepseek/deepseek-chat-v3"


@pytest.mark.asyncio
async def test_openrouter_all_models_fail(mock_openrouter_settings):
    with patch("src.infrastructure.llm.openrouter_provider.AsyncOpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("Model failed"))
        mock_client_cls.return_value = mock_client

        provider = OpenRouterProvider(models=["m1", "m2", "m3"])
        with pytest.raises(AIProviderError) as exc_info:
            await provider.complete("sys", "user")

        assert "OpenRouter provider failed on all models" in str(exc_info.value)
        assert mock_client.chat.completions.create.call_count == 3


# ── FallbackLLMProvider Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fallback_primary_success():
    primary = MagicMock()
    primary.provider_name = "Groq"
    primary.complete = AsyncMock(return_value='{"source": "groq"}')

    fallback = MagicMock()
    fallback.provider_name = "OpenRouter"

    provider = FallbackLLMProvider(primary=primary, fallback=fallback)
    res = await provider.complete("sys", "user")

    assert res == '{"source": "groq"}'
    primary.complete.assert_called_once_with("sys", "user")
    assert not fallback.complete.called


@pytest.mark.asyncio
async def test_fallback_switches_to_openrouter_on_primary_failure():
    primary = MagicMock()
    primary.provider_name = "Groq"
    primary.complete = AsyncMock(side_effect=AIProviderError("Groq failed"))

    fallback = MagicMock()
    fallback.provider_name = "OpenRouter"
    fallback.complete = AsyncMock(return_value='{"source": "openrouter"}')

    provider = FallbackLLMProvider(primary=primary, fallback=fallback)
    res = await provider.complete("sys", "user")

    assert res == '{"source": "openrouter"}'
    primary.complete.assert_called_once_with("sys", "user")
    fallback.complete.assert_called_once_with("sys", "user")


@pytest.mark.asyncio
async def test_fallback_both_providers_unavailable():
    primary = MagicMock()
    primary.provider_name = "Groq"
    primary.complete = AsyncMock(side_effect=AIProviderError("Groq unavailable"))

    fallback = MagicMock()
    fallback.provider_name = "OpenRouter"
    fallback.complete = AsyncMock(side_effect=AIProviderError("OpenRouter unavailable"))

    provider = FallbackLLMProvider(primary=primary, fallback=fallback)
    with pytest.raises(AIProviderError) as exc_info:
        await provider.complete("sys", "user")

    assert "All LLM providers exhausted" in str(exc_info.value)
