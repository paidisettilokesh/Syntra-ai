"""
Structured audit event emitter for Syntra AI Mail Agent.

Emits structured log records with email-processing metadata as extra fields,
enabling downstream log aggregators (ELK, Loki, Splunk) to index and query
individual email processing events.
"""

from .logger import get_logger

logger = get_logger("audit")


def log_email_processed(
    *,
    email_id: str,
    sender: str,
    subject: str,
    category: str,
    importance_score: int,
    risk_score: int,
    verification_status: str,
    notification_status: str,
    duration_ms: float,
    account: str = "",
) -> None:
    """
    Emit a structured audit log record for a single email processing event.

    All keyword arguments are attached as extra fields on the LogRecord,
    making them available to the StructuredJsonFormatter and any custom
    log handlers.
    """
    extra = {
        "email_id": email_id,
        "sender": sender,
        "category": category,
        "risk_score": risk_score,
        "verification_status": verification_status,
        "notification_status": notification_status,
        "duration_ms": round(duration_ms, 2),
    }
    logger.info(
        f"[AUDIT] email_id={email_id!r} "
        f"category={category!r} "
        f"score={importance_score} "
        f"risk={risk_score} "
        f"verification={verification_status!r} "
        f"notification={notification_status!r} "
        f"duration_ms={duration_ms:.1f} "
        f"account={account!r}",
        extra=extra,
    )
