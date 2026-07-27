"""
Email Authentication Header Validator for Syntra AI Mail Agent.

Parses SPF, DKIM, and DMARC results from IMAP email headers and
returns structured authentication results for use as risk signals
in the EmailVerificationService.

Supported headers:
- Authentication-Results: contains SPF/DKIM/DMARC results in RFC 7601 format
- Received-SPF: dedicated SPF result header
- DKIM-Signature: presence indicates DKIM signing attempted

This module uses only Python standard library — no new dependencies.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class EmailAuthResult:
    """Parsed email authentication results."""

    spf: str = "none"    # "pass" | "fail" | "softfail" | "neutral" | "none" | "permerror"
    dkim: str = "none"   # "pass" | "fail" | "none"
    dmarc: str = "none"  # "pass" | "fail" | "none"
    raw_results: Dict[str, str] = field(default_factory=dict)

    @property
    def all_pass(self) -> bool:
        return self.spf == "pass" and self.dkim == "pass"

    @property
    def any_fail(self) -> bool:
        return "fail" in (self.spf, self.dkim, self.dmarc)

    @property
    def risk_contribution(self) -> int:
        """
        Additive risk score contribution based on authentication failures.

        SPF fail:   +20 points
        DKIM fail:  +15 points
        DMARC fail: +15 points
        SPF softfail: +10 points

        Returns a value between 0 and 50.
        """
        score = 0
        if self.spf == "fail":
            score += 20
        elif self.spf == "softfail":
            score += 10
        if self.dkim == "fail":
            score += 15
        if self.dmarc == "fail":
            score += 15
        return min(score, 50)

    def triggered_rules(self) -> list:
        """Return list of failed authentication checks for triggered_rules reporting."""
        rules = []
        if self.spf in ("fail", "softfail"):
            rules.append(f"SPF {self.spf.upper()}: sending server not authorized")
        if self.dkim == "fail":
            rules.append("DKIM FAIL: signature verification failed")
        if self.dmarc == "fail":
            rules.append("DMARC FAIL: domain alignment check failed")
        return rules


# Regex patterns for Authentication-Results header parsing (RFC 7601)
_SPF_PATTERN = re.compile(r"\bspf=(\w+)", re.IGNORECASE)
_DKIM_PATTERN = re.compile(r"\bdkim=(\w+)", re.IGNORECASE)
_DMARC_PATTERN = re.compile(r"\bdmarc=(\w+)", re.IGNORECASE)

# Received-SPF header result extraction
_RECEIVED_SPF_PATTERN = re.compile(r"^(pass|fail|softfail|neutral|none|permerror|temperror)", re.IGNORECASE)


def parse_auth_results(auth_headers: Dict[str, str]) -> EmailAuthResult:
    """
    Parse email authentication headers into a structured EmailAuthResult.

    Args:
        auth_headers: Dict extracted from IMAP message headers by GmailClient.
                      Expected keys: "authentication_results", "received_spf", "dkim_signature"

    Returns:
        EmailAuthResult with parsed spf/dkim/dmarc values.
    """
    result = EmailAuthResult()

    if not auth_headers:
        return result

    # 1. Parse Authentication-Results header (most comprehensive — contains all three)
    auth_results_header = auth_headers.get("authentication_results", "")
    if auth_results_header:
        spf_match = _SPF_PATTERN.search(auth_results_header)
        if spf_match:
            result.spf = spf_match.group(1).lower()

        dkim_match = _DKIM_PATTERN.search(auth_results_header)
        if dkim_match:
            result.dkim = dkim_match.group(1).lower()

        dmarc_match = _DMARC_PATTERN.search(auth_results_header)
        if dmarc_match:
            result.dmarc = dmarc_match.group(1).lower()

    # 2. Received-SPF as fallback for SPF if not found in Authentication-Results
    if result.spf == "none":
        received_spf = auth_headers.get("received_spf", "").strip()
        if received_spf:
            spf_match = _RECEIVED_SPF_PATTERN.match(received_spf)
            if spf_match:
                result.spf = spf_match.group(1).lower()

    # 3. DKIM-Signature presence indicates signing was attempted
    # (actual pass/fail comes from Authentication-Results — this is just a fallback signal)
    if result.dkim == "none" and auth_headers.get("dkim_signature"):
        # Signature present but not verified in Authentication-Results — treat as unknown
        result.dkim = "none"

    result.raw_results = dict(auth_headers)
    return result
