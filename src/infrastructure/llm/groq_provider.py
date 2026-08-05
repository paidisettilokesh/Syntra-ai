"""
GroqProvider — Primary LLM provider using the Groq API.

Retry strategy (per model):
    - Max retries:  2  (3 total attempts)
    - Backoff:      exponential — base_delay * 2^attempt + jitter(0..1s)
    - Retriable:    RateLimitError, APITimeoutError, APIConnectionError, InternalServerError
    - Non-retriable: All other exceptions (bad request, auth error, etc.)

Model cascade within Groq:
    llama-3.3-70b-versatile  (primary)
        └── llama-3.1-8b-instant  (Groq-internal fallback if 70B fails completely)

Structured log format:
    INFO  [LLM] Provider=Groq Model=<model> Status=Success latency=0.82s retries=0
    WARNING [LLM] Provider=Groq Model=<model> Status=RateLimited retry=1/2
    ERROR [LLM] Provider=Groq Status=Failed Both models exhausted.
"""

import asyncio
import os
import random
import time
from typing import Optional

import groq
from groq import AsyncGroq

from src.config.settings import settings
from src.domain.exceptions import AIProviderError
from src.infrastructure.llm.base import ILLMProvider
from src.utils.logger import get_logger
from src.utils.sanitizer import is_valid_api_key, mask_secret

logger = get_logger(__name__)

# ── Retry configuration ────────────────────────────────────────────────────────
_MAX_RETRIES: int = 2  # 2 retries = 3 total attempts
_BASE_DELAY: float = 1.0  # seconds — doubles each attempt + jitter

# Error types that are safe to retry (transient failures)
_RETRIABLE_ERRORS = (
    groq.RateLimitError,  # HTTP 429 — quota / rate limit exceeded
    groq.APITimeoutError,  # Request timed out
    groq.APIConnectionError,  # Network / DNS failure
    groq.InternalServerError,  # HTTP 5xx — Groq server-side error
)


class GroqProvider(ILLMProvider):
    """
    Concrete LLM provider backed by the Groq API.

    A single :class:`AsyncGroq` client is created at construction time and
    reused for all subsequent calls, avoiding per-request TCP overhead.
    """

    _PRIMARY_MODEL: str = "llama-3.3-70b-versatile"
    _FALLBACK_MODEL: str = "llama-3.1-8b-instant"

    def __init__(self) -> None:
        raw_key: Optional[str] = None
        if settings.ai.groq_api_key:
            v = settings.ai.groq_api_key.get_secret_value()
            if is_valid_api_key(v):
                raw_key = v.strip()

        if not raw_key:
            env_v = os.getenv("GROQ_API_KEY")
            if is_valid_api_key(env_v):
                raw_key = env_v.strip()

        if not raw_key:
            logger.warning(
                "[LLM] GROQ_API_KEY not configured or placeholder detected. GroqProvider will be unavailable."
            )
            self._client: Optional[AsyncGroq] = None
        else:
            # Reuse one client for the lifetime of the process
            self._client = AsyncGroq(api_key=raw_key)
            logger.info(f"[LLM] GroqProvider initialized. Key: {mask_secret(raw_key)}")

    @property
    def provider_name(self) -> str:
        return "Groq"

    def _is_available(self) -> bool:
        return self._client is not None

    async def _call_model(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Execute a single chat completion against the specified Groq model.

        Applies up to ``_MAX_RETRIES`` retries with exponential backoff + jitter
        for retriable errors.  Non-retriable errors are re-raised immediately.

        Args:
            model:         Groq model identifier.
            system_prompt: System-level instruction.
            user_prompt:   Sanitised email content.

        Returns:
            Raw JSON string from the model.

        Raises:
            AIProviderError: After exhausting all retries on retriable errors.
            Exception:       Immediately for non-retriable errors.
        """
        assert self._client is not None  # guarded by _is_available() upstream

        for attempt in range(_MAX_RETRIES + 1):  # 0, 1, 2
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
                    timeout=30.0,
                )
                latency = time.monotonic() - t_start
                logger.info(
                    f"[LLM] Provider=Groq Model={model} Status=Success "
                    f"latency={latency:.2f}s retries={attempt}"
                )
                return completion.choices[0].message.content

            except _RETRIABLE_ERRORS as exc:
                latency = time.monotonic() - t_start
                is_rate_limit = isinstance(exc, groq.RateLimitError)
                status = "RateLimited" if is_rate_limit else type(exc).__name__

                logger.warning(
                    f"[LLM] Provider=Groq Model={model} Status={status} "
                    f"retry={attempt + 1}/{_MAX_RETRIES} "
                    f"latency={latency:.2f}s"
                )

                if attempt >= _MAX_RETRIES:
                    # All retry attempts exhausted — raise so caller can cascade
                    raise AIProviderError(
                        f"Groq model '{model}' failed after {_MAX_RETRIES} retries: {exc}"
                    ) from exc

                # Exponential backoff with uniform jitter to avoid thundering herd
                delay = _BASE_DELAY * (2**attempt) + random.uniform(0.0, 1.0)
                logger.info(
                    f"[LLM] Groq retrying in {delay:.2f}s "
                    f"(attempt {attempt + 1} of {_MAX_RETRIES})"
                )
                await asyncio.sleep(delay)

            except Exception as exc:
                # Non-retriable error — propagate immediately, no backoff
                latency = time.monotonic() - t_start
                logger.error(
                    f"[LLM] Provider=Groq Model={model} Status=NonRetriableError "
                    f"latency={latency:.2f}s error={exc}"
                )
                raise

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """
        Fulfil a completion request through Groq.

        Tries ``_PRIMARY_MODEL`` first (with full retry logic).  If it is
        completely exhausted, attempts ``_FALLBACK_MODEL`` (also with retries).

        Raises:
            AIProviderError: When both Groq models fail.
        """
        if not self._is_available():
            raise AIProviderError(
                "GroqProvider: GROQ_API_KEY not configured — provider unavailable."
            )

        # ── Primary model ──────────────────────────────────────────────────────
        try:
            return await self._call_model(self._PRIMARY_MODEL, system_prompt, user_prompt)
        except AIProviderError as exc:
            logger.warning(
                f"[LLM] Groq primary model '{self._PRIMARY_MODEL}' exhausted. "
                f"Trying fallback model '{self._FALLBACK_MODEL}'. Error: {exc}"
            )
        except Exception as exc:
            logger.warning(
                f"[LLM] Groq primary model '{self._PRIMARY_MODEL}' unexpected failure. "
                f"Trying '{self._FALLBACK_MODEL}'. Error: {exc}"
            )

        # ── Groq-internal fallback model ───────────────────────────────────────
        try:
            return await self._call_model(self._FALLBACK_MODEL, system_prompt, user_prompt)
        except Exception as exc:
            logger.error(
                f"[LLM] Provider=Groq Status=Failed "
                f"Both models ({self._PRIMARY_MODEL}, {self._FALLBACK_MODEL}) exhausted. "
                f"Error: {exc}"
            )
            raise AIProviderError(f"Groq provider failed on all models: {exc}") from exc
