from src.application.rule_engine import RuleEngine
from src.domain.models import EmailMetadata


def test_rule_engine_newsletter():
    engine = RuleEngine()
    email = EmailMetadata(
        message_id="123",
        sender="promo@marketing.com",
        subject="Super Deal!",
        body="If you no longer wish to receive these emails, unsubscribe here.",
        attachment_text="",
    )
    res = engine.evaluate(email)
    assert res is not None
    assert res.category == "Newsletter"
    assert res.importance_score == 1
    assert res.action_required is False


def test_rule_engine_social():
    engine = RuleEngine()
    email = EmailMetadata(
        message_id="124",
        sender="notifications@linkedin.com",
        subject="Weekly Digest",
        body="Here are your updates this week.",
        attachment_text="",
    )
    res = engine.evaluate(email)
    assert res is not None
    assert res.category == "Social"
    assert res.importance_score == 2


def test_rule_engine_calendar():
    engine = RuleEngine()
    email = EmailMetadata(
        message_id="125",
        sender="invite@google.com",
        subject="Accepted: Project Sync",
        body="Meeting details...",
        attachment_text="",
    )
    res = engine.evaluate(email)
    assert res is not None
    assert res.category == "Informational"
    assert res.importance_score == 3


def test_rule_engine_no_match():
    engine = RuleEngine()
    email = EmailMetadata(
        message_id="126",
        sender="recruiter@techcorp.com",
        subject="Job interview request",
        body="Hello, we'd like to schedule an interview with you.",
        attachment_text="",
    )
    res = engine.evaluate(email)
    assert res is None
