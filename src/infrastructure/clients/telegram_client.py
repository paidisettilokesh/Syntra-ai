import os
import time
import requests
from typing import Optional

from src.config.settings import settings
from src.domain.exceptions import NotificationError
from src.domain.interfaces import INotificationService
from src.domain.models import AnalysisResult, EmailMetadata, VerificationResult
from src.utils.logger import get_logger
from src.utils.sanitizer import mask_secret, sanitize_html_for_telegram

logger = get_logger(__name__)

# Risk level emoji mapping for visual clarity
_RISK_EMOJI = {
    "Low": "🟢",
    "Medium": "🟡",
    "High": "🟠",
    "Critical": "🔴",
}

# Verification status emoji
_STATUS_EMOJI = {
    "Legitimate": "✅",
    "Suspicious": "⚠️",
}


class TelegramNotificationService(INotificationService):
    """
    Production-grade Telegram Bot notification service for Syntra AI.
    Delivers structured alerts via Telegram Bot API using HTTP REST requests.
    """

    def __init__(self):
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram Bot Token or Chat ID not fully configured.")
        else:
            logger.debug(
                f"Telegram configured. Token: {mask_secret(self.bot_token)} | "
                f"Chat ID: {mask_secret(self.chat_id)}"
            )

    @property
    def bot_token(self) -> Optional[str]:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if token and token.strip():
            return token.strip()
        if settings.notify.telegram_bot_token:
            return settings.notify.telegram_bot_token.get_secret_value()
        return None

    @property
    def chat_id(self) -> Optional[str]:
        cid = os.getenv("TELEGRAM_CHAT_ID")
        if cid and cid.strip():
            return cid.strip()
        if settings.notify.telegram_chat_id:
            return settings.notify.telegram_chat_id.get_secret_value()
        return None

    @property
    def is_enabled(self) -> bool:
        env_enable = os.getenv("FEATURE_ENABLE_TELEGRAM") or os.getenv("ENABLE_TELEGRAM")
        if env_enable is not None:
            return env_enable.lower() in ("true", "1", "yes")
        return settings.features.enable_telegram

    def _build_html_message(
        self,
        email: EmailMetadata,
        analysis: AnalysisResult,
        verification_result: Optional[VerificationResult],
    ) -> str:
        """Build the rich HTML notification message with full explainability."""
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")

        # Sanitize all dynamic content (Issue #11)
        safe_sender = sanitize_html_for_telegram(email.sender or "Unknown Sender", max_length=200)
        safe_subject = sanitize_html_for_telegram(email.subject or "No Subject", max_length=300)
        safe_category = sanitize_html_for_telegram(analysis.category or "Informational", max_length=100)
        safe_summary = sanitize_html_for_telegram(analysis.summary or "", max_length=500)

        lines = [
            "🚨 <b>Syntra AI</b>\n",
            f"📧 <b>Sender:</b>\n{safe_sender}\n",
            f"📝 <b>Subject:</b>\n{safe_subject}\n",
            f"📂 <b>Category:</b> {safe_category}",
            f"⭐ <b>Priority:</b> {analysis.importance_score}/10",
            f"🤖 <b>AI Summary:</b>\n{safe_summary}\n",
        ]

        # Issue #6: Security verdict section for explainability
        if verification_result:
            risk_emoji = _RISK_EMOJI.get(verification_result.risk_level, "⚪")
            status_emoji = _STATUS_EMOJI.get(verification_result.status, "❓")

            safe_status = sanitize_html_for_telegram(verification_result.status, max_length=50)
            safe_risk_level = sanitize_html_for_telegram(verification_result.risk_level, max_length=20)
            safe_reason = sanitize_html_for_telegram(verification_result.reason, max_length=400)

            lines.append("─" * 20)
            lines.append(
                f"🔐 <b>Security Verdict:</b> {status_emoji} {safe_status}"
            )
            lines.append(
                f"{risk_emoji} <b>Risk Score:</b> {verification_result.risk_score}/100 "
                f"({safe_risk_level})"
            )

            if verification_result.triggered_rules:
                safe_rules = sanitize_html_for_telegram(
                    ", ".join(verification_result.triggered_rules[:6]), max_length=300
                )
                lines.append(f"📋 <b>Rules Triggered:</b> {safe_rules}")

            if safe_reason:
                lines.append(f"💡 <b>Reason:</b> {safe_reason}")

        lines.append(f"\n⏰ <b>Received:</b> {timestamp_str}")

        return "\n".join(lines)

    def _build_plain_message(
        self,
        email: EmailMetadata,
        analysis: AnalysisResult,
        verification_result: Optional[VerificationResult],
    ) -> str:
        """Build plain-text fallback notification message."""
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            "🚨 Syntra AI\n",
            f"📧 Sender:\n{email.sender}\n",
            f"📝 Subject:\n{email.subject}\n",
            f"📂 Category: {analysis.category}",
            f"⭐ Priority: {analysis.importance_score}/10",
            f"🤖 AI Summary:\n{(analysis.summary or '')[:500]}\n",
        ]

        if verification_result:
            risk_emoji = _RISK_EMOJI.get(verification_result.risk_level, "⚪")
            status_emoji = _STATUS_EMOJI.get(verification_result.status, "❓")
            lines.append("--------------------")
            lines.append(f"🔐 Security: {status_emoji} {verification_result.status}")
            lines.append(
                f"{risk_emoji} Risk: {verification_result.risk_score}/100 ({verification_result.risk_level})"
            )
            if verification_result.triggered_rules:
                lines.append(f"📋 Rules: {', '.join(verification_result.triggered_rules[:6])}")
            if verification_result.reason:
                lines.append(f"💡 Reason: {verification_result.reason[:300]}")

        lines.append(f"\n⏰ Received: {timestamp_str}")

        return "\n".join(lines)

    def send_alert(
        self,
        email: EmailMetadata,
        analysis: AnalysisResult,
        verification_result: Optional[VerificationResult] = None,
    ) -> None:
        """
        Formats and dispatches a Telegram notification for high-priority emails.
        HTML-escapes dynamic text and falls back to plain unformatted text if HTML parsing fails.
        Raises NotificationError if delivery fails after all attempts.

        Issue #6: Includes verification_result for full security explainability.
        """
        if not self.is_enabled:
            logger.info("Telegram notifications are disabled by feature flag.")
            return

        if not self.bot_token or not self.chat_id:
            logger.warning("Invalid Telegram Chat ID or Bot Token. Skipping notification.")
            raise NotificationError("Telegram Bot Token or Chat ID is not configured.")

        html_message = self._build_html_message(email, analysis, verification_result)
        plain_message = self._build_plain_message(email, analysis, verification_result)

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        html_payload = {
            "chat_id": self.chat_id,
            "text": html_message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        plain_payload = {
            "chat_id": self.chat_id,
            "text": plain_message,
            "disable_web_page_preview": True,
        }

        max_attempts = 3
        timeout_seconds = 10

        for payload, mode_label in [(html_payload, "HTML"), (plain_payload, "Plain Text Fallback")]:
            for attempt in range(1, max_attempts + 1):
                try:
                    response = requests.post(url, json=payload, timeout=timeout_seconds)
                    data = response.json()

                    if response.status_code == 200 and data.get("ok"):
                        msg_id = data.get("result", {}).get("message_id", "N/A")
                        logger.info(f"Telegram notification sent. Message ID: {msg_id}")
                        return
                    else:
                        error_desc = data.get("description", "Unknown Error")
                        logger.warning(
                            f"Telegram API {mode_label} attempt {attempt} failed. "
                            f"HTTP {response.status_code}: {error_desc}"
                        )
                        if response.status_code == 400 and "parse" in error_desc.lower():
                            logger.info("HTML parse error — engaging plain text fallback...")
                            break

                except requests.exceptions.RequestException as e:
                    logger.warning(f"Telegram network attempt {attempt}/{max_attempts} failed: {e}")
                    if attempt == max_attempts and mode_label == "Plain Text Fallback":
                        raise NotificationError(f"Telegram network delivery failed: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error in Telegram notification service: {e}")
                    raise NotificationError(f"Unexpected Telegram failure: {e}")

        raise NotificationError("Telegram notification delivery failed after all payload attempts.")
