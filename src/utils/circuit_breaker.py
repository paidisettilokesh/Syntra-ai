"""
Circuit Breaker utility for Syntra AI Mail Agent.

Implements the CLOSED / OPEN / HALF-OPEN state machine pattern to prevent
cascading failures when an external service (e.g. Gmail IMAP, AI provider)
becomes temporarily unavailable.

State transitions:
    CLOSED  → OPEN       : after `failure_threshold` consecutive failures
    OPEN    → HALF-OPEN  : after `recovery_timeout` seconds
    HALF-OPEN → CLOSED   : on first successful call in half-open state
    HALF-OPEN → OPEN     : on failure in half-open state (resets timer)
"""

import asyncio
import time
from enum import Enum
from typing import Callable, Optional

from .logger import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    CLOSED = "CLOSED"  # Normal operation — calls are allowed
    OPEN = "OPEN"  # Failing fast — calls are blocked
    HALF_OPEN = "HALF_OPEN"  # Probe state — one trial call is allowed


class CircuitBreaker:
    """
    Async-safe circuit breaker.

    Args:
        name: Human-readable label used in log messages.
        failure_threshold: Consecutive failures before opening the circuit.
        recovery_timeout: Seconds in OPEN state before transitioning to HALF-OPEN.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 300.0,  # 5 minutes
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def is_open(self) -> bool:
        return self._state == CircuitState.OPEN

    def _check_recovery(self) -> None:
        """Transition OPEN → HALF-OPEN if recovery timeout has elapsed."""
        if (
            self._state == CircuitState.OPEN
            and self._last_failure_time is not None
            and (time.monotonic() - self._last_failure_time) >= self.recovery_timeout
        ):
            self._state = CircuitState.HALF_OPEN
            logger.info(
                f"Circuit '{self.name}': OPEN → HALF-OPEN after "
                f"{self.recovery_timeout:.0f}s recovery timeout."
            )

    async def call(self, func: Callable, *args, **kwargs):
        """
        Execute `func` through the circuit breaker.

        Raises:
            RuntimeError: If the circuit is OPEN and recovery timeout has not elapsed.
        """
        async with self._lock:
            self._check_recovery()

            if self._state == CircuitState.OPEN:
                raise RuntimeError(
                    f"Circuit '{self.name}' is OPEN. "
                    f"Service unavailable — skipping call to protect downstream resources. "
                    f"Will retry after {self.recovery_timeout:.0f}s."
                )

        # Attempt the call (outside the lock to avoid blocking)
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as exc:
            await self._on_failure(exc)
            raise

    async def _on_success(self) -> None:
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.info(
                    f"Circuit '{self.name}': HALF-OPEN → CLOSED after successful probe call."
                )
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None

    async def _on_failure(self, exc: Exception) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit '{self.name}': HALF-OPEN → OPEN — probe call failed: {exc}"
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.error(
                    f"Circuit '{self.name}': CLOSED → OPEN after "
                    f"{self._failure_count} consecutive failures. "
                    f"Last error: {exc}. "
                    f"Will attempt recovery in {self.recovery_timeout:.0f}s."
                )
            else:
                logger.warning(
                    f"Circuit '{self.name}': failure {self._failure_count}/"
                    f"{self.failure_threshold}. Error: {exc}"
                )

    def reset(self) -> None:
        """Manually reset the circuit to CLOSED state (for testing or manual recovery)."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        logger.info(f"Circuit '{self.name}': manually reset to CLOSED.")
