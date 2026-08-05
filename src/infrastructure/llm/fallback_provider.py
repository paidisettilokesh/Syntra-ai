"""
FallbackLLMProvider — Two-tier LLM orchestrator.

Flow:
    1. GroqProvider.complete()         ← primary (handles its own retry + backoff)
         ↓ raises AIProviderError after all retries exhausted
    2. Log: "Switching to OpenRouter"
    3. OpenRouterProvider.complete()   ← fallback (3-model cascade)
         ↓ raises AIProviderError if all models fail
    4. Raise AIProviderError          ← application logs but does NOT crash

The application never crashes because a single provider failed.
Business logic (ChainAIProvider) receives either a JSON string or AIProviderError —
it has no knowledge of which provider fulfilled the request.

Structured log format:
    WARNING [LLM] Provider=Groq Status=Failed after retries. Activating OpenRouter fallback.
    INFO    [LLM] Switching to OpenRouter
    ERROR   [LLM] Both providers failed. Primary=Groq Fallback=OpenRouter.
"""

from src.domain.exceptions import AIProviderError
from src.infrastructure.llm.base import ILLMProvider
from src.infrastructure.llm.groq_provider import GroqProvider
from src.infrastructure.llm.openrouter_provider import OpenRouterProvider
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FallbackLLMProvider(ILLMProvider):
    """
    Orchestrates the two-tier provider fallback strategy.

    This class has no retry logic of its own — it delegates retries to
    :class:`GroqProvider` and model cascading to :class:`OpenRouterProvider`.
    Its sole responsibility is to switch providers when the primary fails.

    Args:
        primary:  GroqProvider (or any ILLMProvider for testing).
        fallback: OpenRouterProvider (or any ILLMProvider for testing).
    """

    def __init__(
        self,
        primary: GroqProvider,
        fallback: OpenRouterProvider,
    ) -> None:
        self._primary = primary
        self._fallback = fallback

    @property
    def provider_name(self) -> str:
        return f"Fallback({self._primary.provider_name} → {self._fallback.provider_name})"

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """
        Execute the LLM request with automatic provider fallback.

        Args:
            system_prompt: System-level instruction for the model.
            user_prompt:   Sanitised, XML-delimited email content.

        Returns:
            Raw JSON string from the first provider that succeeds.

        Raises:
            AIProviderError: If both primary and fallback providers are exhausted.
        """
        # ── Primary: Groq ──────────────────────────────────────────────────────
        try:
            return await self._primary.complete(system_prompt, user_prompt)

        except AIProviderError as exc:
            logger.warning(
                f"[LLM] Provider={self._primary.provider_name} "
                f"Status=Failed after retries. "
                f"Activating {self._fallback.provider_name} fallback. "
                f"Error: {exc}"
            )
        except Exception as exc:
            # Unexpected (non-AIProviderError) failure from primary — still fall through
            logger.warning(
                f"[LLM] Provider={self._primary.provider_name} "
                f"Status=UnexpectedFailure. "
                f"Activating {self._fallback.provider_name} fallback. "
                f"Error: {exc}"
            )

        # ── Switching to fallback ──────────────────────────────────────────────
        logger.info(f"[LLM] SwitchingTo={self._fallback.provider_name}")

        # ── Fallback: OpenRouter ───────────────────────────────────────────────
        try:
            return await self._fallback.complete(system_prompt, user_prompt)

        except AIProviderError as exc:
            logger.error(
                f"[LLM] Both providers failed. "
                f"Primary={self._primary.provider_name} "
                f"Fallback={self._fallback.provider_name}. "
                f"Last error: {exc}"
            )
            raise AIProviderError(f"All LLM providers exhausted. Last error: {exc}") from exc

        except Exception as exc:
            logger.error(
                f"[LLM] Fallback provider '{self._fallback.provider_name}' "
                f"unexpected failure: {exc}"
            )
            raise AIProviderError(f"Fallback provider failed unexpectedly: {exc}") from exc
