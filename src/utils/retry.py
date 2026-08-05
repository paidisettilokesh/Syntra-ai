import asyncio
import functools
from typing import Callable

from .logger import get_logger

logger = get_logger(__name__)


def async_retry(max_retries=3, base_delay=2):
    """
    Exponential-backoff retry decorator for async functions.

    Delay between attempts: base_delay ** attempt_number (seconds).
    The wrapped function's metadata is preserved via @functools.wraps.
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries} attempts. Error: {e}"
                        )
                        raise
                    delay = base_delay**attempt
                    logger.warning(
                        f"Attempt {attempt} failed for {func.__name__}. "
                        f"Retrying in {delay}s. Error: {e}"
                    )
                    await asyncio.sleep(delay)

        return wrapper

    return decorator
