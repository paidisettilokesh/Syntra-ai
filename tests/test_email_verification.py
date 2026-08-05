from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.orchestrator import EmailOrchestrator
from src.application.services.email_verification import EmailVerificationService
from src.domain.exceptions import AIProviderError
from src.domain.models import AnalysisResult, EmailMetadata


@pytest.fixture
def verification_service():
    return EmailVerificationService(ai_provider=None)


@pytest.mark.asyncio
async def test_trusted_github_email(verification_service):
    email = EmailMetadata(
        message_id="github-1",
        sender="GitHub <notifications@github.com>",
        subject="Security alert: Dependabot vulnerability update",
        body="Dependabot detected a security vulnerability in your repository. Please update your dependencies.",
    )
    result = await verification_service.verify_email(email)
    assert result.is_legitimate is True
    assert result.status == "Legitimate"
    assert result.risk_score < 20
    assert result.risk_level == "Low"
    assert "Trusted Sender Allowlist" in result.triggered_rules


@pytest.mark.asyncio
async def test_trusted_linkedin_email(verification_service):
    email = EmailMetadata(
        message_id="linkedin-1",
        sender="LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>",
        subject="Top job recommendations for Senior Python Engineer",
        body="View new job opportunities matching your profile on LinkedIn.",
    )
    result = await verification_service.verify_email(email)
    assert result.is_legitimate is True
    assert result.status == "Legitimate"
    assert result.risk_score < 20


@pytest.mark.asyncio
async def test_trusted_microsoft_email(verification_service):
    email = EmailMetadata(
        message_id="microsoft-1",
        sender="Microsoft Account Team <account-security-noreply@accountprotection.microsoft.com>",
        subject="Microsoft account security code",
        body="Use this single-use code to sign in to your Microsoft account.",
    )
    result = await verification_service.verify_email(email)
    assert result.is_legitimate is True
    assert result.status == "Legitimate"


@pytest.mark.asyncio
async def test_trusted_google_email(verification_service):
    email = EmailMetadata(
        message_id="google-1",
        sender="Google <no-reply@accounts.google.com>",
        subject="Security alert for your linked Google Account",
        body="New sign-in on Windows. If this was you, no action is needed.",
    )
    result = await verification_service.verify_email(email)
    assert result.is_legitimate is True
    assert result.status == "Legitimate"
    assert result.risk_score < 20


@pytest.mark.asyncio
async def test_spoofed_amazon_email(verification_service):
    email = EmailMetadata(
        message_id="spoof-amazon-1",
        sender="Amazon Customer Support <xyz@gmail.com>",
        subject="URGENT: Your Amazon Account Suspended",
        body="Your account has been locked. Click here to confirm your credit card and password details.",
    )
    result = await verification_service.verify_email(email)
    assert result.is_legitimate is False
    assert result.status == "Suspicious"
    assert result.risk_score >= 50
    assert result.decision == "Notification Blocked"
    assert "Spoofed Domain" in result.threats


@pytest.mark.asyncio
async def test_typosquatted_microsoft_email(verification_service):
    email = EmailMetadata(
        message_id="typo-ms-1",
        sender="Microsoft Security <support@micros0ft-security.com>",
        subject="Verify your Office 365 credentials",
        body="Please verify your Office 365 login credentials immediately.",
    )
    result = await verification_service.verify_email(email)
    assert result.is_legitimate is False
    assert result.status == "Suspicious"
    assert result.risk_score >= 50
    assert "Typosquatting" in result.triggered_rules or "Spoofed Domain" in result.threats


@pytest.mark.asyncio
async def test_malicious_attachment(verification_service):
    email = EmailMetadata(
        message_id="malicious-att-1",
        sender="Invoice Dept <invoice@vendor-billing.com>",
        subject="Overdue Payment Invoice #82934",
        body="Please see attached invoice.exe for detailed remittance instructions.",
        attachment_text="invoice_attachment.exe",
    )
    result = await verification_service.verify_email(email)
    assert result.is_legitimate is False
    assert result.status == "Suspicious"
    assert "Executable Attachment" in result.threats


@pytest.mark.asyncio
async def test_credential_harvesting(verification_service):
    email = EmailMetadata(
        message_id="cred-harvest-1",
        sender="Webmail Admin <admin@secure-mail-verify.xyz>",
        subject="Webmail Upgrade Required",
        body="Enter your password and confirm your account details immediately to prevent account termination.",
    )
    result = await verification_service.verify_email(email)
    assert result.is_legitimate is False
    assert "Credential Harvesting" in result.threats


@pytest.mark.asyncio
async def test_mixed_legitimate_content(verification_service):
    email = EmailMetadata(
        message_id="mixed-legit-1",
        sender="HR Team <hr@company.com>",
        subject="Urgent Payroll Verification Reminder",
        body="Please review your annual payroll tax forms on the company portal by end of day.",
    )
    result = await verification_service.verify_email(email)
    assert result.is_legitimate is True
    assert result.status == "Legitimate"


@pytest.mark.asyncio
async def test_mixed_malicious_content(verification_service):
    email = EmailMetadata(
        message_id="mixed-mal-1",
        sender="Apple Support <support@tempmail.com>",
        subject="URGENT: Apple ID Suspended - Reset Password",
        body="Your Apple ID is suspended. Share your OTP code and enter your password at http://bit.ly/3apple to unlock.",
    )
    result = await verification_service.verify_email(email)
    assert result.is_legitimate is False
    assert result.risk_score >= 50
    assert len(result.threats) >= 2


@pytest.mark.asyncio
async def test_ai_unavailable_fallback():
    mock_ai = MagicMock()
    mock_ai.verify_email = AsyncMock(side_effect=AIProviderError("API Quota Exceeded"))

    service = EmailVerificationService(ai_provider=mock_ai)

    email = EmailMetadata(
        message_id="ai-fail-1",
        sender="GitHub <notifications@github.com>",
        subject="Security alert: Dependabot alert",
        body="Security update for your repository.",
    )

    # Must NOT crash, fallback to Rule-Based Engine smoothly
    result = await service.verify_email(email)
    assert result.is_legitimate is True
    assert result.status == "Legitimate"


@pytest.mark.asyncio
async def test_false_positive_prevention(verification_service):
    email = EmailMetadata(
        message_id="false-pos-1",
        sender="Google Security <no-reply@accounts.google.com>",
        subject="Security alert: Critical password change confirmation",
        body="Your Google Account password was changed. Verify this login if you did not initiate it.",
    )
    result = await verification_service.verify_email(email)
    assert result.is_legitimate is True
    assert result.status == "Legitimate"
    assert result.decision == "Notification Sent"


@pytest.mark.asyncio
async def test_explainability_output(verification_service):
    email = EmailMetadata(
        message_id="explain-1",
        sender="Fake Bank <security@chase-login-verify.xyz>",
        subject="URGENT: Bank Account Suspended",
        body="Enter your password and confirm credit card details at http://192.168.1.1/login.",
    )
    result = await verification_service.verify_email(email)
    assert hasattr(result, "status")
    assert hasattr(result, "risk_score")
    assert hasattr(result, "decision")
    assert hasattr(result, "triggered_rules")
    assert isinstance(result.risk_score, int)
    assert result.status == "Suspicious"
    assert result.decision == "Notification Blocked"
    assert len(result.triggered_rules) > 0


@pytest.mark.asyncio
async def test_orchestrator_logs_verification_to_database():
    mail_client = MagicMock()
    mail_client.get_unseen_emails = AsyncMock(
        return_value=[
            EmailMetadata(
                message_id="db-test-1",
                sender="GitHub <notifications@github.com>",
                subject="Pull request assigned",
                body="You were assigned to PR #104.",
            )
        ]
    )

    repo = MagicMock()
    repo.is_email_processed.return_value = False

    ai = MagicMock()
    ai.analyze = AsyncMock(
        return_value=AnalysisResult(
            category="Security",
            importance_score=8,
            summary="PR assigned.",
            reasoning="GitHub update.",
            action_required=True,
            confidence_score=0.95,
        )
    )

    notifier = MagicMock()

    orchestrator = EmailOrchestrator(
        mail_clients=[mail_client],
        repository=repo,
        ai_provider=ai,
        notification_services=[notifier],
    )

    await orchestrator.process_inboxes()

    assert repo.log_email.called
    kwargs = repo.log_email.call_args[1]
    assert kwargs["email_id"] == "db-test-1"
    assert kwargs["verification_status"] == "Legitimate"
    assert "risk_score" in kwargs
    assert "risk_level" in kwargs
