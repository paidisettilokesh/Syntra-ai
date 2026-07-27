"""
ILLMProvider — Abstract interface for raw LLM completion calls.

This is an infrastructure-level abstraction, separate from the domain-level
IAIProvider. Business logic (EmailOrchestrator, EmailVerificationService)
depends only on IAIProvider. Provider switching and retry strategy depend
on ILLMProvider, keeping them fully isolated from business logic.

Hierarchy:
    IAIProvider  (domain interface — email classification + verification)
        └── ChainAIProvider
              └── ILLMProvider  (infrastructure interface — raw LLM call)
                    ├── GroqProvider         (primary)
                    ├── OpenRouterProvider   (fallback)
                    └── FallbackLLMProvider  (orchestrator)
"""

from abc import ABC, abstractmethod


class ILLMProvider(ABC):
    """
    Low-level contract for a single chat-completion request.

    Implementors accept sanitized system and user prompts and return
    the raw JSON string response from the model.  All retry logic,
    backoff, and model-cascade decisions live in the concrete classes.
    """

    @abstractmethod
    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send a chat completion request and return the model's raw JSON string.

        Args:
            system_prompt: Instruction telling the model its role and output schema.
            user_prompt:   Sanitized, XML-delimited email content (untrusted input).

        Returns:
            Raw JSON string conforming to the schema described in the system prompt.

        Raises:
            AIProviderError: If the provider cannot fulfil the request after all
                             internal retries / model cascades are exhausted.
        """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider label used in structured log messages."""
