from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.orchestrator import EmailOrchestrator
from src.domain.models import AnalysisResult, EmailMetadata


@pytest.mark.asyncio
async def test_orchestrator_processed_skip():
    mail_client = MagicMock()
    mail_client.get_unseen_emails = AsyncMock(
        return_value=[EmailMetadata(message_id="id1", sender="s1", subject="sub1", body="body1")]
    )

    repo = MagicMock()
    repo.is_email_processed.return_value = True

    ai = MagicMock()
    notifier = MagicMock()

    orchestrator = EmailOrchestrator([mail_client], repo, ai, [notifier])
    await orchestrator.process_inboxes()

    assert not ai.analyze.called
    assert not notifier.send_alert.called
    assert not repo.log_email.called


@pytest.mark.asyncio
async def test_orchestrator_rule_engine_bypass():
    mail_client = MagicMock()
    mail_client.get_unseen_emails = AsyncMock(
        return_value=[
            EmailMetadata(
                message_id="id1",
                sender="s1",
                subject="Unsubscribe promo",
                body="unsubscribe now",
                attachment_text="",
            )
        ]
    )

    repo = MagicMock()
    repo.is_email_processed.return_value = False

    ai = MagicMock()
    notifier = MagicMock()

    orchestrator = EmailOrchestrator([mail_client], repo, ai, [notifier])
    await orchestrator.process_inboxes()

    assert not ai.analyze.called
    assert not notifier.send_alert.called
    assert repo.log_email.called
    kwargs = repo.log_email.call_args[1]
    assert kwargs["email_id"] == "id1"
    assert kwargs["sender"] == "s1"
    assert kwargs["subject"] == "Unsubscribe promo"
    assert kwargs["category"] == "Newsletter"
    assert kwargs["score"] == 1


@pytest.mark.asyncio
async def test_orchestrator_ai_high_priority_trigger():
    mail_client = MagicMock()
    mail_client.get_unseen_emails = AsyncMock(
        return_value=[
            EmailMetadata(
                message_id="id2",
                sender="hr@tech.com",
                subject="Interview Schedule",
                body="Body text",
            )
        ]
    )

    repo = MagicMock()
    repo.is_email_processed.return_value = False
    # Issue #10: has_notification_been_sent must return False so notification proceeds
    repo.has_notification_been_sent.return_value = False

    ai = MagicMock()
    ai_result = AnalysisResult(
        category="Interview",
        importance_score=9,
        summary="Interview Invitation.",
        reasoning="Key scheduling details.",
        action_required=True,
        confidence_score=0.98,
    )
    ai.analyze = AsyncMock(return_value=ai_result)

    notifier = MagicMock()

    orchestrator = EmailOrchestrator([mail_client], repo, ai, [notifier])
    await orchestrator.process_inboxes()

    ai.analyze.assert_called_once()
    notifier.send_alert.assert_called_once()
    repo.log_email.assert_called_once()
