import json
import logging
import logging.handlers
import os
from datetime import datetime, timezone


class StructuredJsonFormatter(logging.Formatter):
    """JSON log formatter for production log aggregation (ELK, Loki, Splunk, Cloud Logging)."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Include structured extras if present
        for key in ("email_id", "sender", "category", "risk_score",
                    "notification_status", "duration_ms", "verification_status"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        if record.exc_info:
            log_entry["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


def _is_structured() -> bool:
    """Read STRUCTURED_LOGGING env var without depending on full settings stack."""
    return os.environ.get("STRUCTURED_LOGGING", "false").lower() in ("true", "1", "yes")


def _get_log_level() -> int:
    raw = os.environ.get("LOG_LEVEL", "INFO").upper()
    return getattr(logging, raw, logging.INFO)


def _get_log_file() -> str:
    return os.environ.get("LOG_FILE", "logs/agent.log")


def _get_max_bytes() -> int:
    try:
        return int(os.environ.get("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
    except (ValueError, TypeError):
        return 10 * 1024 * 1024


def _get_backup_count() -> int:
    try:
        return int(os.environ.get("LOG_BACKUP_COUNT", "5"))
    except (ValueError, TypeError):
        return 5


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger with both console and rotating file output.

    - Console: always active; level = LOG_LEVEL env var (default INFO)
    - File: RotatingFileHandler at LOG_FILE path; same level
    - Format: plain text by default; JSON when STRUCTURED_LOGGING=true
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    level = _get_log_level()
    logger.setLevel(logging.DEBUG)  # Root level — handlers control the output level

    use_json = _is_structured()
    plain_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    if use_json:
        formatter: logging.Formatter = StructuredJsonFormatter()
    else:
        formatter = logging.Formatter(plain_fmt)

    # ── Console handler (always present) ──────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # ── Rotating file handler ──────────────────────────────────────────────
    log_file = _get_log_file()
    try:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=_get_max_bytes(),
            backupCount=_get_backup_count(),
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        # Do not crash if log file cannot be opened; console logging continues
        logger.warning(
            f"Could not configure file logging at '{log_file}': {e}. "
            "Logging to console only."
        )

    return logger
