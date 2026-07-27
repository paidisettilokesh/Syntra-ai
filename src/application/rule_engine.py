from typing import Optional

from src.domain.models import AnalysisResult, EmailMetadata


class RuleEngine:
    def evaluate(self, email: EmailMetadata) -> Optional[AnalysisResult]:
        """
        Deterministically evaluates an email. Returns AnalysisResult if bypassed,
        otherwise None (meaning AI should process it).
        """
        sender_lower = email.sender.lower()
        subject_lower = email.subject.lower()
        body_lower = email.body.lower()

        # Rule 1: Marketing, Newsletters
        if (
            "unsubscribe" in body_lower
            or "view in browser" in body_lower
            or "manage preferences" in body_lower
        ):
            return AnalysisResult(
                category="Newsletter",
                importance_score=1,
                summary="This appears to be an automated newsletter or promotional email.",
                reasoning="Detected keywords ('unsubscribe', 'view in browser') indicative of automated marketing campaigns.",
                action_required=False,
                confidence_score=0.95,
            )

        # Rule 2: Social Media Digests
        if any(
            domain in sender_lower
            for domain in ["facebookmail.com", "linkedin.com", "twitter.com", "instagram.com"]
        ):
            if "message" not in subject_lower and "invitation" not in subject_lower:
                return AnalysisResult(
                    category="Social",
                    importance_score=2,
                    summary="Automated social media notification or digest.",
                    reasoning="Sender domain matches known social media automated addresses without indicators of direct personal interaction.",
                    action_required=False,
                    confidence_score=0.90,
                )

        # Rule 3: Calendar auto-responses
        if "accepted:" in subject_lower or "declined:" in subject_lower:
            return AnalysisResult(
                category="Informational",
                importance_score=3,
                summary="Calendar event response.",
                reasoning="Subject line matches standard calendar automated responses.",
                action_required=False,
                confidence_score=0.95,
            )

        return None
