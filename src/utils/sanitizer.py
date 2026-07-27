"""
src/utils/sanitizer.py

Central security utility module for:
- AI prompt injection hardening
- Credential masking in logs
- HTML sanitization for notifications
- Text length enforcement
"""
import html
import re
from typing import Optional


# Patterns that indicate prompt injection attempts within email content
_INJECTION_PATTERNS = [
    r"ignore (previous|all|above|prior) instructions?",
    r"you are (now|a|an) (different|new|better|evil|unrestricted)",
    r"disregard (all|your|the) (previous|prior|above|instructions|system)",
    r"(system|assistant|user):\s",
    r"<(system|instruction|prompt)>",
    r"\[INST\]",
    r"###\s*(instruction|system|prompt)",
    r"act as (if you (are|were)|a )",
    r"jailbreak",
    r"do anything now",
    r"dan mode",
]

_COMPILED_INJECTION = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


def sanitize_for_ai(text: str, max_length: int = 18000) -> str:
    """
    Prepare text for inclusion in an AI prompt:
    1. Truncate to max_length to prevent token exhaustion.
    2. Strip obvious prompt injection patterns.
    3. Returns clean text suitable for wrapping in delimiters.
    """
    if not text:
        return ""

    # Truncate first (before scanning — avoids scanning huge strings)
    truncated = text[:max_length]

    # Flag injection patterns (do not silently remove — replace with [REDACTED] so
    # the AI can see the pattern was present and still assess context appropriately)
    for pattern in _COMPILED_INJECTION:
        truncated = pattern.sub("[POTENTIAL_INJECTION_REDACTED]", truncated)

    return truncated


def wrap_for_ai_prompt(label: str, content: str, max_length: int = 18000) -> str:
    """
    Wrap sanitized content in XML-like delimiters to create clear boundaries
    between the AI's system instructions and the untrusted email content.

    Example output:
        <EMAIL_SENDER>John Doe <jdoe@gmail.com></EMAIL_SENDER>
    """
    safe = sanitize_for_ai(content, max_length)
    tag = label.upper().replace(" ", "_")
    return f"<{tag}>{safe}</{tag}>"


def is_valid_api_key(value: Optional[str]) -> bool:
    """
    Return True if value is a non-empty string and not a placeholder like 'your_...'.
    """
    if not value or not isinstance(value, str):
        return False
    v = value.strip().lower()
    if not v:
        return False
    if (
        v.startswith("your_")
        or v.startswith("your...")
        or v.startswith("your-")
        or "placeholder" in v
        or "change_me" in v
        or v == "unset"
    ):
        return False
    return True


def mask_secret(value: Optional[str], visible_chars: int = 4) -> str:
    """
    Mask a secret/credential for safe log output.
    Reveals key prefix and suffix while obscuring the secret core.

    Examples:
        mask_secret("sk-or-v1-example1234567890abcdef") -> "sk-or-v1...cdef"
        mask_secret("gsk_example1234567890abcdef")      -> "gsk_...cdef"
        mask_secret(None)                               -> "UNSET"
        mask_secret("your_openrouter_api_key_here")     -> "UNSET"
    """
    if not value or not is_valid_api_key(value):
        return "UNSET"
    val = value.strip()
    if val.startswith("sk-or-v1-"):
        return f"sk-or-v1...{val[-4:]}"
    if val.startswith("gsk_"):
        return f"gsk_...{val[-5:]}"
    if len(val) <= visible_chars * 2:
        return "*" * len(val)
    return f"{val[:visible_chars]}...{val[-visible_chars:]}"


def sanitize_html_for_telegram(text: str, max_length: int = 500) -> str:
    """
    Escape HTML special characters and truncate text for safe Telegram HTML messages.
    Telegram's HTML parse mode only supports a limited subset — escaping is mandatory.
    """
    if not text:
        return ""
    escaped = html.escape(str(text))
    if len(escaped) > max_length:
        escaped = escaped[:max_length] + "…"
    return escaped


def strip_html_tags(text: str) -> str:
    """
    Remove HTML tags from a string, returning plain text.
    Used when falling back from HTML to plain-text notifications.
    """
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"&[a-zA-Z]+;", " ", clean)
    return clean.strip()
