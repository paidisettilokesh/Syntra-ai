from abc import ABC, abstractmethod
from typing import List, Optional

from .models import AnalysisResult, EmailMetadata, VerificationResult


class IRepository(ABC):
    @abstractmethod
    def is_email_processed(self, email_id: str) -> bool:
        pass

    @abstractmethod
    def log_email(
        self,
        email_id: str,
        sender: str,
        subject: str,
        category: str,
        score: int,
        reasoning: str,
        action_required: bool,
        confidence_score: float,
        verification_status: Optional[str] = "Legitimate",
        verification_confidence: Optional[float] = 100.0,
        risk_score: Optional[int] = 0,
        risk_level: Optional[str] = "Low",
        verification_reason: Optional[str] = "",
        triggered_rules: Optional[str] = "",
        notification_status: Optional[str] = "pending",
    ) -> None:
        pass

    @abstractmethod
    def has_notification_been_sent(self, email_id: str) -> bool:
        """Issue #10: Check if notification already sent to prevent duplicates."""
        pass

    @abstractmethod
    def update_notification_status(self, email_id: str, status: str) -> None:
        """Issue #10: Update notification status after send attempt."""
        pass


class IMailClient(ABC):
    @abstractmethod
    async def get_unseen_emails(self) -> List[EmailMetadata]:
        pass


class INotificationService(ABC):
    @abstractmethod
    def send_alert(
        self,
        email: EmailMetadata,
        analysis: AnalysisResult,
        verification_result: Optional[VerificationResult] = None,
    ) -> None:
        """
        Issue #6: verification_result is now passed to enable explainability
        in notifications — showing risk score, triggered rules, and reason.
        """
        pass


class IAIProvider(ABC):
    @abstractmethod
    async def analyze(self, email: EmailMetadata) -> AnalysisResult:
        pass
