try:
    from twilio.rest import Client
    HAS_TWILIO = True
except ImportError:
    HAS_TWILIO = False

from typing import Optional

from src.config.settings import settings
from src.domain.exceptions import NotificationError
from src.domain.interfaces import INotificationService
from src.domain.models import AnalysisResult, EmailMetadata, VerificationResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TwilioWhatsAppService(INotificationService):
    def __init__(self):
        if not HAS_TWILIO:
            logger.warning("Twilio library not installed. WhatsApp service disabled.")
            self.client = None
            return

        if settings.notify.twilio_account_sid and settings.notify.twilio_auth_token:
            self.client = Client(
                settings.notify.twilio_account_sid.get_secret_value(),
                settings.notify.twilio_auth_token.get_secret_value(),
            )
        else:
            self.client = None
            logger.warning("Twilio credentials not configured.")

    def send_alert(
        self,
        email: EmailMetadata,
        analysis: AnalysisResult,
        verification_result: Optional[VerificationResult] = None,
    ) -> None:
        if not self.client:
            return

        action_req_str = "Yes 🔴" if analysis.action_required else "No 🟢"

        # Issue #6: Include security verdict in WhatsApp message
        security_section = ""
        if verification_result:
            risk_emoji = {"Low": "🟢", "Medium": "🟡", "High": "🟠", "Critical": "🔴"}.get(
                verification_result.risk_level, "⚪"
            )
            security_section = (
                f"\n\n*Security Verdict:*\n"
                f"{risk_emoji} Risk: {verification_result.risk_score}/100 ({verification_result.risk_level})\n"
                f"Status: {verification_result.status}"
            )

        message_body = f"""
🚨 *High Priority Email Alert* 🚨

*From:* {email.sender}
*Subject:* {email.subject}
*Category:* {analysis.category}
*Importance:* {analysis.importance_score}/10
*Action Required:* {action_req_str}

*Summary:*
{analysis.summary}

*Reasoning:*
{analysis.reasoning}{security_section}
        """.strip()

        try:
            from_whatsapp = settings.notify.from_whatsapp_number
            to_whatsapp = settings.notify.to_whatsapp_number

            if not from_whatsapp or not to_whatsapp:
                raise NotificationError("WhatsApp numbers not fully configured in settings.")

            from_num = (
                from_whatsapp
                if from_whatsapp.startswith("whatsapp:")
                else f"whatsapp:{from_whatsapp}"
            )
            to_num = (
                to_whatsapp if to_whatsapp.startswith("whatsapp:") else f"whatsapp:{to_whatsapp}"
            )

            message = self.client.messages.create(from_=from_num, body=message_body, to=to_num)
            logger.info(f"WhatsApp alert sent. SID: {message.sid}")
        except Exception as e:
            logger.error(f"Error sending WhatsApp alert: {e}")
            raise NotificationError(f"WhatsApp alert failed: {e}")
