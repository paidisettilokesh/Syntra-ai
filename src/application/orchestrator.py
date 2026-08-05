import os
import time
from typing import List, Optional

from src.application.rule_engine import RuleEngine
from src.application.services.email_verification import EmailVerificationService
from src.config.settings import settings
from src.domain.interfaces import IAIProvider, IMailClient, INotificationService, IRepository
from src.domain.models import VerificationResult
from src.utils.audit_log import log_email_processed
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EmailOrchestrator:
    def __init__(
        self,
        mail_clients: List[IMailClient],
        repository: IRepository,
        ai_provider: IAIProvider,
        notification_services: List[INotificationService],
        verification_service: Optional[EmailVerificationService] = None,
    ):
        self.mail_clients = mail_clients
        self.repository = repository
        self.ai_provider = ai_provider
        self.notification_services = notification_services
        self.rule_engine = RuleEngine()
        self.verification_service = verification_service or EmailVerificationService(ai_provider=ai_provider)
        # Issue #12: In-memory deduplication cache for hot-path performance.
        # Avoids a DB query for emails already seen in this process session.
        self._seen_email_ids: set = set()

    async def _process_single_client(self, mail_client: IMailClient):
        client_name = getattr(mail_client, "user", "unknown")
        logger.info(f"Checking inbox for client: {client_name}")
        try:
            emails = await mail_client.get_unseen_emails()
        except Exception as e:
            logger.error(f"Failed to fetch emails for {client_name}: {e}")
            return

        for email in emails:
            # Issue #5 & #12: In-memory dedup check first (fast), then DB check (persistent)
            if email.message_id in self._seen_email_ids:
                logger.debug(f"In-memory dedup hit — skipping already-seen email: {email.message_id}")
                continue

            if self.repository.is_email_processed(email.message_id):
                logger.info(f"Skipping already-processed email: '{email.subject}' [{email.message_id}]")
                self._seen_email_ids.add(email.message_id)
                continue

            # Register in memory immediately to prevent race conditions in concurrent clients
            self._seen_email_ids.add(email.message_id)

            start_time = time.monotonic()
            logger.info(f"Analyzing email: '{email.subject}' from {email.sender}")

            # 1. Email Verification Layer
            try:
                verification_result = await self.verification_service.verify_email(email)
            except Exception as e:
                logger.error(f"Error during email verification: {e}")
                verification_result = VerificationResult(
                    is_legitimate=True,
                    confidence=50.0,
                    risk_level="Medium",
                    reason=f"Verification error fallback: {e}",
                    threats=[],
                )

            # 2. Rule Engine First Pass
            analysis = self.rule_engine.evaluate(email)

            if analysis:
                logger.info(f"  -> Bypassed AI (Rule Match): {analysis.category}")
            else:
                # 3. AI Evaluation
                try:
                    analysis = await self.ai_provider.analyze(email)
                except Exception as e:
                    logger.error(f"  -> Skipping due to analysis error: {e}")
                    continue

            # 4. Notification Logic (Determine if we should notify)
            high_priority_categories = [
                "Job Offer",
                "Interview",
                "Internship",
                "Assessment",
                "Security",
                "Bank",
                "Deadline",
                "Personal",
            ]

            should_notify = False
            notification_status = "suppressed"

            notify_all = os.environ.get("NOTIFY_ALL_EMAILS", "false").lower() in ("true", "1", "yes")

            if (
                notify_all
                or analysis.importance_score >= 7
                or analysis.action_required
                or analysis.category in high_priority_categories
            ):
                if verification_result.is_legitimate or not settings.verification.block_suspicious_emails:
                    should_notify = True
                else:
                    logger.warning(
                        f"  -> High priority email BLOCKED by security: "
                        f"Risk {verification_result.risk_score}/100 ({verification_result.risk_level}). "
                        f"Reason: {verification_result.reason[:120]}"
                    )
                    notification_status = "blocked_by_security"
            else:
                logger.info(
                    f"  -> Processed silently (Score: {analysis.importance_score}, Category: {analysis.category})"
                )

            # 5. Send Notifications — with duplicate notification prevention (Issue #10)
            if should_notify:
                # Issue #10: Check DB to prevent sending duplicate notifications
                # (e.g., if the email was somehow persisted with notification_status='sent' already)
                try:
                    already_sent = self.repository.has_notification_been_sent(email.message_id)
                except Exception:
                    already_sent = False

                if already_sent:
                    logger.info(f"  -> Notification already sent for {email.message_id}. Skipping duplicate.")
                    notification_status = "sent"
                else:
                    logger.info(
                        f"  -> High Priority! Triggering notifications. "
                        f"(Risk: {verification_result.risk_score}/100, Level: {verification_result.risk_level})"
                    )
                    success_count = 0
                    for notifier in self.notification_services:
                        try:
                            # Issue #6: Pass verification_result for explainability in notifications
                            notifier.send_alert(email, analysis, verification_result)
                            success_count += 1
                        except Exception as e:
                            logger.warning(f"  -> Notification failed via {notifier.__class__.__name__}: {e}")

                    if success_count == 0 and self.notification_services:
                        notification_status = "failed"
                    else:
                        notification_status = "sent"

            # 6. Save to DB with Verification Details (ALWAYS execute regardless of notification success)
            try:
                self.repository.log_email(
                    email_id=email.message_id,
                    sender=email.sender,
                    subject=email.subject,
                    category=analysis.category,
                    score=analysis.importance_score,
                    reasoning=analysis.reasoning,
                    action_required=analysis.action_required,
                    confidence_score=analysis.confidence_score,
                    verification_status=verification_result.status,
                    verification_confidence=verification_result.confidence,
                    risk_score=verification_result.risk_score,
                    risk_level=verification_result.risk_level,
                    verification_reason=verification_result.reason,
                    triggered_rules=", ".join(verification_result.triggered_rules),
                    notification_status=notification_status,
                )
            except Exception as e:
                logger.error(f"  -> Failed to persist email to database: {e}")

            # 7. Audit Logging
            duration_ms = (time.monotonic() - start_time) * 1000
            log_email_processed(
                email_id=email.message_id,
                sender=email.sender,
                subject=email.subject,
                category=analysis.category,
                importance_score=analysis.importance_score,
                risk_score=verification_result.risk_score,
                verification_status=verification_result.status,
                notification_status=notification_status,
                duration_ms=duration_ms,
                account=client_name,
            )

    async def process_inboxes(self):
        import asyncio

        tasks = [self._process_single_client(client) for client in self.mail_clients]
        await asyncio.gather(*tasks, return_exceptions=True)
