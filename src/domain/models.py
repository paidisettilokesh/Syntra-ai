from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EmailMetadata(BaseModel):
    message_id: str
    sender: str
    subject: str
    body: str
    attachment_text: Optional[str] = ""

    # Email authentication headers (populated by GmailClient from IMAP message)
    # Keys: "spf", "dkim", "dmarc", "authentication_results"
    # Default empty dict is backward-compatible — existing code ignoring this field is unaffected.
    auth_headers: Dict[str, str] = Field(default_factory=dict)

    # Binary MIME metadata for attachments (populated by GmailClient)
    # Each entry: {"filename": str, "declared_mime": str, "size": int}
    attachment_mime_info: List[Dict[str, Any]] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    category: str = Field(..., description="The category of the email")
    importance_score: int = Field(..., description="Score from 1 to 10")
    summary: str = Field(..., description="2-5 sentence concise overview")
    reasoning: str = Field(
        ..., description="Explanation of why this category and score were assigned"
    )
    action_required: bool = Field(
        ..., description="True if the user needs to take immediate action"
    )
    confidence_score: float = Field(
        ..., description="Confidence in the AI's analysis, from 0.0 to 1.0"
    )


class VerificationResult(BaseModel):
    is_legitimate: bool = Field(
        ..., description="True if email is verified as legitimate, False otherwise"
    )
    status: str = Field(
        "Legitimate", description="Verification Status: 'Legitimate' or 'Suspicious'"
    )
    confidence: float = Field(..., description="Confidence score from 0 to 100")
    risk_score: int = Field(0, description="Risk score from 0 to 100")
    risk_level: str = Field(..., description="Low, Medium, High, or Critical")
    decision: str = Field(
        "Notification Sent", description="Decision: 'Notification Sent' or 'Notification Blocked'"
    )
    reason: str = Field(..., description="Explanation of the verification verdict")
    triggered_rules: List[str] = Field(
        default_factory=list, description="List of triggered verification rules"
    )
    threats: List[str] = Field(
        default_factory=list, description="List of detected threat indicators"
    )
