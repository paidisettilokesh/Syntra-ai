"""
OpenRouterProvider — Fallback LLM provider via OpenRouter.

Uses the official OpenAI Python SDK pointed at the OpenRouter API endpoint.
A single AsyncOpenAI client is created once and reused for all requests.

Model cascade (stops at first success, no per-model retries):
    1. google/gemini-2.5-flash      (default first choice)
    2. deepseek/deepseek-chat-v3    (second choice)
    3. qwen/qwen3-32b               (third choice)

Structured log format:
    INFO  [LLM] Provider=OpenRouter Model=google/gemini-2.5-flash Status=Success latency=1.24s
    ERROR [LLM] Provider=OpenRouter Model=google/gemini-2.5-flash Status=Failed latency=0.31s
    INFO  [LLM] Provider=OpenRouter trying next model: deepseek/deepseek-chat-v3
    ERROR [LLM] Provider=OpenRouter Status=AllModelsFailed models_tried=[...]
"""

import os
import time
from typing import List, Optional

from openai import AsyncOpenAI

from src.config.settings import settings
from src.domain.exceptions import AIProviderError
from src.infrastructure.llm.base import ILLMProvider
from src.utils.logger import get_logger
from src.utils.sanitizer import is_valid_api_key, mask_secret

logger = get_logger(__name__)

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Default model cascade — override via constructor for testing
_DEFAULT_MODELS: List[str] = [
    "google/gemini-2.5-flash",
    "deepseek/deepseek-chat-v3",
    "qwen/qwen3-32b",
]


class OpenRouterProvider(ILLMProvider):
    """
    Concrete LLM provider backed by OpenRouter.

    OpenRouter acts as a unified gateway to multiple underlying models.
    This provider iterates through ``_DEFAULT_MODELS`` in order, returning
    the first successful response.  No per-model retries — model failures
    are treated as permanent within a single ``complete()`` call.

    A single :class:`AsyncOpenAI` client is created at construction time
    and reused for all subsequent calls (reuses underlying TCP connections).
    """

    def __init__(self, models: Optional[List[str]] = None) -> None:
        """
        Args:
            models: Optional override of the model cascade list.
                    Defaults to ``_DEFAULT_MODELS``.
        """
        self._models: List[str] = models or list(_DEFAULT_MODELS)

        raw_key: Optional[str] = None
        if settings.ai.openrouter_api_key:
            v = settings.ai.openrouter_api_key.get_secret_value()
            if is_valid_api_key(v):
                raw_key = v.strip()

        if not raw_key:
            env_v = os.getenv("OPENROUTER_API_KEY")
            if is_valid_api_key(env_v):
                raw_key = env_v.strip()

        if not raw_key:
            logger.warning(
                "[LLM] OPENROUTER_API_KEY not configured or placeholder detected. "
                "OpenRouterProvider will be unavailable."
            )
            self._client: Optional[AsyncOpenAI] = None
        else:
            self._client = AsyncOpenAI(
                api_key=raw_key,
                base_url=_OPENROUTER_BASE_URL,
            )
            logger.info(
                f"[LLM] OpenRouterProvider initialized. "
                f"Key: {mask_secret(raw_key)} "
                f"Models: {self._models}"
            )

    @property
    def provider_name(self) -> str:
        return "OpenRouter"

    def _is_available(self) -> bool:
        return self._client is not None

    async def _call_model(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Execute a single chat completion against one OpenRouter model.

        Args:
            model:         OpenRouter model identifier (e.g. ``google/gemini-2.5-flash``).
            system_prompt: System-level instruction.
            user_prompt:   Sanitised email content.

        Returns:
            Raw JSON string from the model.

        Raises:
            Exception: On any failure — caller handles the cascade.
        """
        assert self._client is not None

        t_start = time.monotonic()
        try:
            completion = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                timeout=45.0,
            )
            latency = time.monotonic() - t_start
            logger.info(
                f"[LLM] Provider=OpenRouter Model={model} Status=Success " f"latency={latency:.2f}s"
            )
            return completion.choices[0].message.content

        except Exception as exc:
            latency = time.monotonic() - t_start
            logger.error(
                f"[LLM] Provider=OpenRouter Model={model} Status=Failed "
                f"latency={latency:.2f}s error={exc}"
            )
            raise

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """
        Try each model in the cascade and return the first successful response.

        Args:
            system_prompt: System-level instruction.
            user_prompt:   Sanitised email content.

        Returns:
            Raw JSON string from the first model that succeeds.

        Raises:
            AIProviderError: If every model in the cascade fails.
        """
        if not self._is_available():
            raise AIProviderError(
                "OpenRouterProvider: OPENROUTER_API_KEY not configured — " "provider unavailable."
            )

        for i, model in enumerate(self._models):
            try:
                return await self._call_model(model, system_prompt, user_prompt)

            except Exception:
                # Log and advance to the next model — exception already logged inside _call_model
                is_last = i == len(self._models) - 1
                if not is_last:
                    next_model = self._models[i + 1]
                    logger.info(f"[LLM] Provider=OpenRouter trying next model: {next_model}")

        # All models failed
        logger.error(
            f"[LLM] Provider=OpenRouter Status=AllModelsFailed " f"models_tried={self._models}"
        )
        raise AIProviderError(f"OpenRouter provider failed on all models: {self._models}")
