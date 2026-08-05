import email.utils
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from src.config.settings import settings
from src.domain.interfaces import IAIProvider
from src.domain.models import EmailMetadata, VerificationResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EmailVerificationService:
    """
    Production-Grade Email Verification Service for Syntra AI.
    Features:
    - Configurable Trusted Sender Allowlist (Two-Tier Trust Model)
    - Weighted Risk Scoring Engine (0-100)
    - Urgency Word Detection (Emergency, Immediate, Action Required, etc.)
    - Free Email Provider Baseline Risk
    - Job Offer from Personal Gmail Detection
    - Contextual False-Positive Prevention
    - Smart AI Routing & Resilient Fallbacks
    - Full Explainability Output (Status, Risk Score, Decision, Rationale, Rules)
    - Granular Detailed Stage Logging
    """

    DISPOSABLE_DOMAINS = {
        "mailinator.com",
        "10minutemail.com",
        "tempmail.com",
        "guerrillamail.com",
        "trashmail.com",
        "yopmail.com",
        "sharklasers.com",
        "dispostable.com",
        "getnada.com",
        "throwawaymail.com",
    }

    FREE_EMAIL_DOMAINS = {
        "gmail.com",
        "yahoo.com",
        "hotmail.com",
        "outlook.com",
        "aol.com",
        "icloud.com",
        "mail.com",
        "zoho.com",
        "protonmail.com",
        "proton.me",
        "live.com",
        "msn.com",
        "ymail.com",
        "rediffmail.com",
    }

    BRAND_DOMAINS = {
        "amazon": ["amazon.com", "amazon.co.uk", "amazon.in", "aws.amazon.com"],
        "google": ["google.com", "accounts.google.com", "notifications.google.com"],
        "paypal": ["paypal.com", "paypal.co.uk"],
        "apple": ["apple.com", "icloud.com"],
        "microsoft": ["microsoft.com", "office365.com", "live.com", "outlook.com"],
        "netflix": ["netflix.com"],
        "facebook": ["facebook.com", "meta.com"],
        "meta": ["meta.com", "facebook.com", "instagram.com"],
        "instagram": ["instagram.com"],
        "linkedin": ["linkedin.com", "licdn.com"],
        "github": ["github.com"],
        "chase": ["chase.com"],
        "bank of america": ["bankofamerica.com"],
        "wells fargo": ["wellsfargo.com"],
        "citi": ["citi.com", "citibank.com"],
    }

    DANGEROUS_EXTENSIONS = {
        ".exe",
        ".js",
        ".scr",
        ".bat",
        ".cmd",
        ".vbs",
        ".ps1",
        ".vbe",
        ".jse",
        ".wsf",
        ".wsh",
        ".pif",
        ".application",
        ".gadget",
        ".msi",
        ".msp",
        ".hta",
        ".cpl",
        ".jar",
    }

    MACRO_EXTENSIONS = {".docm", ".xlsm", ".pptm", ".dotm", ".xltm"}

    URL_SHORTENERS = {
        "bit.ly",
        "tinyurl.com",
        "t.co",
        "is.gd",
        "buff.ly",
        "ow.ly",
        "rb.gy",
        "cutt.ly",
        "goo.gl",
        "shorturl.at",
    }

    SUSPICIOUS_TLDS = {
        ".xyz",
        ".top",
        ".work",
        ".click",
        ".link",
        ".download",
        ".racing",
        ".club",
        ".info",
    }

    # Subject/body urgency keyword patterns with weighted scores
    # These fire on both subject AND body separately
    SUBJECT_FLAG_WORDS = [
        (r"\burgent:?\b", 10),
        (r"\bverify now\b", 15),
        (r"\baccount suspended\b", 20),
        (r"\bclick immediately\b", 20),
        (r"\bfinal warning\b", 15),
        (r"\bwinner!?\b|\bcongratulations!? you won\b", 25),
        (r"\breset password immediately\b", 15),
        (r"\bunauthorized access detected\b", 15),
        (r"\bclaim your reward\b", 20),
        # New urgency terms — Issues #2
        (r"\bemergency\b", 15),
        (r"\bimmediate(ly)?\b", 12),
        (r"\baction required\b", 12),
        (r"\bact now\b", 12),
        (r"\bresponse required\b", 10),
        (r"\btime.?sensitive\b", 10),
        (r"\bimmediate action\b", 15),
        (r"\byour account (will be|has been) (closed|suspended|locked|terminated)\b", 20),
        (r"\bconfirm your identity\b", 15),
        (r"\bvalidate your account\b", 15),
        (r"\bunusual (sign.?in|activity|login)\b", 12),
        (r"\byou have been selected\b", 10),
        (r"\bcongratulations? you (have )?won\b", 25),
        (r"\bwarning:?\b", 8),
        (r"\balert:?\b", 8),
    ]

    # Body-only urgency patterns (separate from subject — applied after subject check)
    BODY_URGENCY_PATTERNS = [
        (r"\bemergency\b", 8),
        (r"\bimmediate(ly)?\b", 6),
        (r"\baction required\b", 8),
        (r"\bact now\b", 8),
        (r"\btime.?sensitive\b", 6),
        (r"\brespond within \d+ (hours?|days?|minutes?)\b", 8),
        (r"\bdeadline.{0,20}(today|tonight|now|immediately)\b", 10),
        (r"\byour (account|access) (will be|is being) (suspended|terminated|deleted|closed)\b", 15),
        (r"\bverify (your )?(account|identity|information|details) (now|immediately|today)\b", 15),
    ]

    # Job-offer signals used to detect fake recruiters from free email domains
    JOB_OFFER_SIGNALS = [
        r"\b(job|employment|position|role|vacancy|opening|career|opportunity)\b",
        r"\b(hiring|recruit(er|ment|ing)?|headhunt(er|ing)?)\b",
        r"\bwork from home\b",
        r"\b(salary|compensation|package|ctc|lpa|per annum)\b",
        r"\b(apply now|apply today|send your (resume|cv))\b",
        r"\b(interview|onboarding|joining|offer letter)\b",
        r"\bwe are looking for\b",
        r"\bexciting opportunity\b",
    ]

    SCAM_CONTENT_PATTERNS = {
        "Credential Harvesting": (
            [
                r"enter your password",
                r"confirm your account",
                r"confirm your account details",
                r"verify your login credentials",
                r"update security credentials",
                r"login to verify account",
            ],
            35,
        ),
        "OTP Scam": (
            [
                r"share your otp",
                r"verification code required to unlock",
                r"provide 6-digit code to support",
                r"send otp immediately",
            ],
            25,
        ),
        "Bank Scam": (
            [
                r"urgent wire transfer required",
                r"unauthorized bank transaction freeze",
                r"verify credit card details immediately",
            ],
            25,
        ),
        "Crypto Scam": (
            [
                r"send bitcoin to wallet",
                r"crypto investment double your money",
                r"crypto wallet compromised",
                r"btc transfer required",
            ],
            25,
        ),
        "Job Scam": (
            [
                r"work from home \$?\d+.*(?:hr|hour|day) no experience",
                r"telegram interview for job",
                r"pay fee for training equipment",
                r"pay for equipment upfront",
                r"pay.*before.*start(ing)? (work|job)",
                r"earn \$?\d{3,}.{0,10}(per day|daily|weekly) from home",
            ],
            20,
        ),
        "Lottery Scam": (
            [
                r"you won million dollars",
                r"claim prize money lottery",
                r"inheritance beneficiary transfer",
                r"unclaimed funds? (in your name|for you)",
            ],
            25,
        ),
        "Fake Invoice Scam": (
            [
                r"fake invoice attached overdue",
                r"remittance advice payment past due to unknown account",
            ],
            20,
        ),
        "Gift Card Scam": (
            [
                r"buy apple gift cards for (ceo|boss|manager|hr)",
                r"purchase google play cards for team",
                r"buy steam gift cards immediately",
                r"send gift card (numbers?|codes?|pins?) (to|via)",
            ],
            20,
        ),
        "Social Engineering / Fake HR": (
            [
                r"urgent direct deposit update required via link",
                r"ceo request confidential wire transfer",
                r"update payroll deposit details immediately",
                r"executive request.*wire transfer",
                r"strictly confidential.*transfer funds",
            ],
            20,
        ),
    }

    def __init__(self, ai_provider: Optional[IAIProvider] = None):
        self.ai_provider = ai_provider
        self.allowlist: Dict[str, List[str]] = self._load_allowlist()

    def _load_allowlist(self) -> Dict[str, List[str]]:
        allowlist_path = getattr(
            settings.verification, "allowlist_file", "data/trusted_domains.json"
        )
        path = Path(allowlist_path)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load allowlist file {allowlist_path}: {e}")
        # Default fallback allowlist — ONLY verified corporate domains
        # Free providers (gmail, yahoo, etc.) are intentionally excluded from here
        return {
            "github.com": ["github.com", "notifications.github.com"],
            "linkedin.com": ["linkedin.com", "licdn.com"],
            "google.com": ["google.com", "accounts.google.com", "notifications.google.com"],
            "microsoft.com": ["microsoft.com", "office365.com"],
            "amazon.com": ["amazon.com", "aws.amazon.com"],
            "oracle.com": ["oracle.com"],
            "apple.com": ["apple.com"],
            "meta.com": ["meta.com", "facebook.com", "instagram.com"],
            "tcs.com": ["tcs.com"],
            "infosys.com": ["infosys.com"],
            "accenture.com": ["accenture.com"],
            "deloitte.com": ["deloitte.com"],
            "ibm.com": ["ibm.com"],
            "cisco.com": ["cisco.com"],
            "naukri.com": ["naukri.com"],
            "indeed.com": ["indeed.com"],
            "internshala.com": ["internshala.com"],
        }

    def _extract_sender_parts(self, sender: str) -> Tuple[str, str, str]:
        display_name, email_addr = email.utils.parseaddr(sender)
        email_addr = email_addr.lower().strip()
        display_name = display_name.strip()
        domain = email_addr.split("@")[-1] if "@" in email_addr else ""
        return display_name, email_addr, domain

    def _is_free_email_domain(self, domain: str) -> bool:
        """Check if domain is a free consumer email provider."""
        return domain in self.FREE_EMAIL_DOMAINS

    def _check_trusted_allowlist(self, sender: str) -> Tuple[bool, bool, Optional[str]]:
        """
        Two-tier trust model:
        - Tier 1 (Verified Corporate): Domain is in allowlist and is NOT a free email provider.
                                       Returns (True, True, org_name).
        - Tier 2 (Free Provider):      Domain is a free provider like gmail.com.
                                       Returns (False, False, None) — no trust discount.
        """
        display_name, email_addr, domain = self._extract_sender_parts(sender)

        if not settings.verification.enable_trusted_senders:
            return False, False, None

        # Explicitly reject free providers from receiving corporate trust credit
        if self._is_free_email_domain(domain):
            return False, False, None

        for org, valid_domains in self.allowlist.items():
            if any(domain == vd or domain.endswith("." + vd) for vd in valid_domains):
                # Verify display name consistency to ensure no brand mismatch
                display_lower = display_name.lower()
                mismatched = False
                for other_brand in self.BRAND_DOMAINS:
                    if other_brand not in org and other_brand in display_lower:
                        mismatched = True
                        break
                if not mismatched:
                    return True, True, org

        return False, False, None

    def _verify_sender_and_domain(self, sender: str) -> Tuple[int, List[str], List[str], List[str]]:
        score = 0
        rules = []
        threats = []
        findings = []

        display_name, email_addr, domain = self._extract_sender_parts(sender)

        # 1. Malformed Email Address
        if (
            not email_addr
            or "@" not in email_addr
            or "." not in domain
            or len(domain.split(".")[-1]) < 2
        ):
            score += 40
            rules.append("Malformed Email Address")
            threats.append("Malformed Email Address")
            findings.append(f"Invalid or malformed sender syntax: '{sender}'")
            return score, rules, threats, findings

        # 2. Trusted Sender & Domain Verification (Tier 1 — Corporate Only)
        is_trusted, is_verified_domain, org_name = self._check_trusted_allowlist(sender)
        if is_trusted:
            score -= 20
            rules.append("Trusted Sender Allowlist")
            findings.append(f"Sender domain '{domain}' matches trusted allowlist for '{org_name}'.")
        if is_verified_domain:
            score -= 15
            rules.append("Verified Domain")

        # 3. Free Email Domain Baseline Risk (Issue #4)
        # Free providers get a small baseline because they're unverified as organizations
        if self._is_free_email_domain(domain) and not is_trusted:
            score += 5
            rules.append("Free Email Provider")
            findings.append(
                f"Sender uses free email provider '{domain}'. "
                "Cannot verify organizational identity."
            )

        # 4. Disposable Email Domain
        if domain in self.DISPOSABLE_DOMAINS:
            score += 35
            rules.append("Disposable Email Domain")
            threats.append("Disposable Email Domain")
            findings.append(f"Sender domain '{domain}' is a known disposable mail provider.")

        # 5. Spoofed Sender & Domain Impersonation
        display_lower = display_name.lower()
        for brand, official_domains in self.BRAND_DOMAINS.items():
            if brand in display_lower or any(word in display_lower for word in brand.split()):
                matches_brand = any(
                    domain == od or domain.endswith("." + od) for od in official_domains
                )
                if not matches_brand:
                    score += 35
                    rules.append("Spoofed Domain")
                    threats.append("Spoofed Domain")
                    findings.append(
                        f"Display name '{display_name}' impersonates '{brand.title()}' but sender domain is '{domain}'."
                    )

        impersonation_keywords = [
            "support",
            "security",
            "admin",
            "service",
            "hr",
            "payroll",
            "helpdesk",
            "verification",
            "account",
            "webmail",
            "noreply",
            "no-reply",
            "alert",
            "team",
        ]
        if any(kw in display_lower for kw in impersonation_keywords):
            if self._is_free_email_domain(domain) or any(
                domain.endswith(tld) for tld in self.SUSPICIOUS_TLDS
            ):
                if "Spoofed Domain" not in threats:
                    score += 35
                    rules.append("Spoofed Domain")
                    threats.append("Spoofed Domain")
                    findings.append(
                        f"Role display name '{display_name}' sent from untrusted domain '{domain}'."
                    )

        # 6. Suspicious Sender TLD
        if any(domain.endswith(tld) for tld in self.SUSPICIOUS_TLDS):
            if "Suspicious Sender TLD" not in rules:
                score += 20
                rules.append("Suspicious Sender TLD")
                threats.append("Suspicious Domain")
                findings.append(f"Sender domain '{domain}' uses high-risk TLD.")

        # 7. Typosquatting
        typos = [r"amaz0n", r"paypa1", r"goog1e", r"rnicrosoft", r"micros0ft"]
        for typo in typos:
            if re.search(typo, domain, re.IGNORECASE) or re.search(typo, display_lower):
                score += 20
                rules.append("Typosquatting")
                threats.append("Spoofed Domain")
                findings.append(f"Typosquatting detected in domain: '{domain}'")

        if domain.count(".") > 3 or re.search(r"paypal.*\.com\.", domain):
            score += 20
            rules.append("Suspicious Domain Structure")
            threats.append("Suspicious Domain Structure")
            findings.append(f"Suspicious double extension domain: '{domain}'")

        return score, rules, threats, findings

    def _check_job_offer_from_free_domain(
        self, sender: str, subject: str, body: str
    ) -> Tuple[int, List[str], List[str], List[str]]:
        """
        Issue #3: Detect job offers sent from personal free email domains.
        Legitimate recruiters use corporate domains. A personal Gmail account
        advertising a job opportunity is a significant red flag.
        """
        score = 0
        rules = []
        threats = []
        findings = []

        _, _, domain = self._extract_sender_parts(sender)

        if not self._is_free_email_domain(domain):
            return score, rules, threats, findings

        combined = f"{subject} {body}".lower()
        job_signal_count = 0
        for pattern in self.JOB_OFFER_SIGNALS:
            if re.search(pattern, combined, re.IGNORECASE):
                job_signal_count += 1

        if job_signal_count >= 2:
            score += 20
            rules.append("Unverified Job Offer")
            threats.append("Unverified Job Offer")
            findings.append(
                f"Job offer signals detected ({job_signal_count} indicators) from free email domain "
                f"'{domain}'. Legitimate recruiters use corporate email addresses."
            )

        return score, rules, threats, findings

    def _extract_urls(self, text: str) -> List[str]:
        url_pattern = r"https?://[^\s<>\"']+|www\.[^\s<>\"']+"
        return re.findall(url_pattern, text)

    def _inspect_urls(
        self, body: str, is_trusted_sender: bool
    ) -> Tuple[int, List[str], List[str], List[str]]:
        score = 0
        rules = []
        threats = []
        findings = []

        urls = self._extract_urls(body)
        for url_str in urls:
            parsed = urlparse(url_str if url_str.startswith("http") else "http://" + url_str)
            hostname = (parsed.hostname or "").lower()

            # Shortened URL
            if hostname in self.URL_SHORTENERS:
                score += 25
                rules.append("Shortened URL")
                threats.append("Shortened URL")
                findings.append(f"Shortened link detected: '{url_str}'")

            # IP Address URL
            if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", hostname):
                score += 25
                rules.append("IP Address URL")
                threats.append("IP Address URL")
                findings.append(f"Raw IP address URL detected: '{url_str}'")

            path = (parsed.path + "?" + parsed.query).lower()
            if any(hostname.endswith(tld) for tld in self.SUSPICIOUS_TLDS):
                sensitive_terms = [
                    "login",
                    "signin",
                    "bank",
                    "verify",
                    "account",
                    "wallet",
                    "secure",
                ]
                if any(term in path or term in hostname for term in sensitive_terms):
                    score += 25
                    rules.append("Suspicious Domain TLD")
                    threats.append("Suspicious Domain")
                    findings.append(f"Suspicious TLD with sensitive path: '{url_str}'")

            fake_login_keywords = [
                "account-update",
                "webmail",
                "secure-login",
                "banking-verify",
                "login-verify",
            ]
            if any(kw in path for kw in fake_login_keywords):
                score += 25
                rules.append("Fake Login Page")
                threats.append("Fake Login Page")
                findings.append(f"Suspicious login path in URL: '{url_str}'")

        # Link Text Mismatch
        mismatch_pattern = (
            r"<a\s+[^>]*href=[\"'](https?://[^\"']+)[\"'][^>]*>(https?://[^<]+|www\.[^<]+)</a>"
        )
        for href, text_url in re.findall(mismatch_pattern, body, re.IGNORECASE):
            href_domain = urlparse(href).hostname or ""
            text_domain = (
                urlparse(text_url if text_url.startswith("http") else "http://" + text_url).hostname
                or ""
            )
            if href_domain.lower() != text_domain.lower() and not is_trusted_sender:
                score += 20
                rules.append("Mismatched Link Text")
                threats.append("Mismatched Link Text")
                findings.append(f"Anchor text '{text_url}' differs from destination '{href}'.")

        return score, rules, threats, findings

    def _validate_attachments(
        self, email: EmailMetadata
    ) -> Tuple[int, List[str], List[str], List[str]]:
        score = 0
        rules = []
        threats = []
        findings = []

        combined_text = f"{email.subject} {email.body} {email.attachment_text}".lower()

        for ext in self.DANGEROUS_EXTENSIONS:
            if ext in combined_text:
                score += 50
                rules.append("Executable Attachment")
                threats.append("Executable Attachment")
                findings.append(f"Executable file attachment reference '{ext}'")

        for ext in self.MACRO_EXTENSIONS:
            if ext in combined_text:
                score += 20
                rules.append("Macro-Enabled Office Document")
                threats.append("Macro-Enabled Office File")
                findings.append(f"Macro-enabled document reference '{ext}'")

        if any(
            term in combined_text
            for term in [
                "password is",
                "zip password",
                "encrypted zip",
                "password-protected archive",
            ]
        ):
            score += 15
            rules.append("Password Protected Archive")
            threats.append("Password Protected Archive")
            findings.append("Password-protected archive reference detected.")

        if email.attachment_mime_info:
            from src.infrastructure.processing.attachment_validator import validate_attachments

            mime_results = validate_attachments(email.attachment_mime_info)
            for res in mime_results:
                if res.is_dangerous:
                    score += 50
                    rules.append("Dangerous Binary Payload")
                    threats.append("Executable Attachment")
                    findings.append(res.risk_note)
                elif res.is_mismatch:
                    score += 35
                    rules.append("Attachment Type Spoofing")
                    threats.append("File Extension Mismatch")
                    findings.append(res.risk_note)

        return score, rules, threats, findings

    def _check_email_authentication(
        self, email: EmailMetadata
    ) -> Tuple[int, List[str], List[str], List[str]]:
        from src.infrastructure.processing.auth_validator import parse_auth_results

        score = 0
        rules = []
        threats = []
        findings = []

        if not email.auth_headers:
            return score, rules, threats, findings

        auth_result = parse_auth_results(email.auth_headers)

        if auth_result.risk_contribution > 0:
            score += auth_result.risk_contribution
            rules.extend(auth_result.triggered_rules())
            threats.append("Email Authentication Failed")
            findings.extend(
                [f"Authentication check failed: {rule}" for rule in auth_result.triggered_rules()]
            )

        return score, rules, threats, findings

    def _analyze_subject(
        self, subject: str, is_trusted_sender: bool
    ) -> Tuple[int, List[str], List[str], List[str]]:
        score = 0
        rules = []
        threats = []
        findings = []

        # Trusted corporate senders: subject urgency alone doesn't add score
        if is_trusted_sender:
            return score, rules, threats, findings

        subject_lower = subject.lower()
        for pattern, points in self.SUBJECT_FLAG_WORDS:
            if re.search(pattern, subject_lower):
                matched = re.search(pattern, subject_lower).group(0)
                score += points
                rules.append("Suspicious Subject Keyword")
                threats.append("Suspicious Subject Keyword")
                findings.append(f"Subject contains urgency/scam keyword: '{matched.upper()}'")

        return score, rules, threats, findings

    def _analyze_body_urgency(
        self, body: str, is_trusted_sender: bool
    ) -> Tuple[int, List[str], List[str], List[str]]:
        """
        Issue #2: Separate urgency analysis on email body.
        Body urgency is scored lower than subject urgency (more false positives),
        and capped at 30 to prevent a single email body from dominating the score.
        """
        score = 0
        rules = []
        threats = []
        findings = []

        if is_trusted_sender:
            return score, rules, threats, findings

        body_lower = body.lower()
        body_urgency_total = 0
        for pattern, points in self.BODY_URGENCY_PATTERNS:
            if re.search(pattern, body_lower):
                matched = re.search(pattern, body_lower).group(0)
                body_urgency_total += points
                findings.append(f"Body contains urgency phrase: '{matched}'")

        if body_urgency_total > 0:
            capped = min(body_urgency_total, 30)
            score += capped
            rules.append("Urgency Language in Body")
            threats.append("Urgency Language")
            if body_urgency_total > 30:
                findings.append(f"Body urgency score capped at 30 (raw: {body_urgency_total}).")

        return score, rules, threats, findings

    def _analyze_content(
        self, body: str, is_trusted_sender: bool
    ) -> Tuple[int, List[str], List[str], List[str]]:
        score = 0
        rules = []
        threats = []
        findings = []

        body_lower = body.lower()
        for threat_category, (patterns, points) in self.SCAM_CONTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, body_lower):
                    # Reduce weight if email is from a verified trusted sender (e.g. GitHub security alert)
                    actual_points = points // 2 if is_trusted_sender else points
                    score += actual_points
                    rules.append(threat_category)
                    threats.append(threat_category)
                    findings.append(f"Content pattern matched for {threat_category}: '{pattern}'")
                    break

        return score, rules, threats, findings

    async def verify_email(self, email: EmailMetadata) -> VerificationResult:
        logger.info("Verification Started")

        if not settings.verification.enable_email_verification:
            logger.info("Email Verification Disabled via configuration")
            return VerificationResult(
                is_legitimate=True,
                status="Legitimate",
                confidence=100.0,
                risk_score=0,
                risk_level="Low",
                decision="Notification Sent",
                reason="Email verification is disabled in configuration.",
                triggered_rules=[],
                threats=[],
            )

        total_risk_score = 0
        all_rules: List[str] = []
        all_threats: List[str] = []
        all_findings: List[str] = []

        is_trusted_sender = False

        # 1. Rule-Based Checks
        if settings.verification.enable_rule_verification:
            # Check Allowlist (Tier 1 — Corporate Only)
            is_trusted_sender, _, _ = self._check_trusted_allowlist(email.sender)

            # 1a. Sender & Domain Verification
            s_score, s_rules, s_threats, s_findings = self._verify_sender_and_domain(email.sender)
            total_risk_score += s_score
            all_rules.extend(s_rules)
            all_threats.extend(s_threats)
            all_findings.extend(s_findings)
            if s_score <= 0 and "Malformed Email Address" not in s_rules:
                logger.info("Sender Verification Passed")
                logger.info("Domain Verification Passed")

            # 1b. Job Offer from Free Email Domain (Issue #3)
            j_score, j_rules, j_threats, j_findings = self._check_job_offer_from_free_domain(
                email.sender, email.subject, email.body
            )
            total_risk_score += j_score
            all_rules.extend(j_rules)
            all_threats.extend(j_threats)
            all_findings.extend(j_findings)

            # 1c. URL Inspection
            u_score, u_rules, u_threats, u_findings = self._inspect_urls(
                email.body, is_trusted_sender
            )
            total_risk_score += u_score
            all_rules.extend(u_rules)
            all_threats.extend(u_threats)
            all_findings.extend(u_findings)
            if u_score == 0:
                logger.info("URL Inspection Passed")

            # 1d. Attachment Validation
            a_score, a_rules, a_threats, a_findings = self._validate_attachments(email)
            total_risk_score += a_score
            all_rules.extend(a_rules)
            all_threats.extend(a_threats)
            all_findings.extend(a_findings)
            if a_score == 0:
                logger.info("Attachment Validation Passed")

            # 1e. Subject Analysis (Issues #1, #2)
            sub_score, sub_rules, sub_threats, sub_findings = self._analyze_subject(
                email.subject, is_trusted_sender
            )
            total_risk_score += sub_score
            all_rules.extend(sub_rules)
            all_threats.extend(sub_threats)
            all_findings.extend(sub_findings)
            if sub_score == 0:
                logger.info("Subject Analysis Passed")

            # 1f. Body Urgency Analysis (Issue #2)
            bu_score, bu_rules, bu_threats, bu_findings = self._analyze_body_urgency(
                email.body, is_trusted_sender
            )
            total_risk_score += bu_score
            all_rules.extend(bu_rules)
            all_threats.extend(bu_threats)
            all_findings.extend(bu_findings)

            # 1g. Content Scam Pattern Analysis
            c_score, c_rules, c_threats, c_findings = self._analyze_content(
                email.body, is_trusted_sender
            )
            total_risk_score += c_score
            all_rules.extend(c_rules)
            all_threats.extend(c_threats)
            all_findings.extend(c_findings)

            # 1h. Email Authentication (SPF/DKIM/DMARC)
            auth_score, auth_rules, auth_threats, auth_findings = self._check_email_authentication(
                email
            )
            total_risk_score += auth_score
            all_rules.extend(auth_rules)
            all_threats.extend(auth_threats)
            all_findings.extend(auth_findings)
            if auth_score == 0 and email.auth_headers:
                logger.info("Email Authentication Passed")

        # Clamp Risk Score between 0 and 100
        clamped_risk_score = max(0, min(100, total_risk_score))
        all_rules = list(dict.fromkeys(all_rules))
        all_threats = list(dict.fromkeys(all_threats))

        # 2. Smart AI Routing
        # Lowered safe threshold from 20 → 15 to route more ambiguous emails through AI
        should_call_ai = (
            settings.verification.enable_ai_verification and self.ai_provider is not None
        )
        if should_call_ai and getattr(settings.verification, "enable_smart_ai_routing", True):
            if clamped_risk_score <= 15:
                logger.info(
                    f"Smart AI Routing: Risk score {clamped_risk_score} <= 15 (clearly safe). Skipping AI call."
                )
                should_call_ai = False
            elif clamped_risk_score >= 75:
                logger.info(
                    f"Smart AI Routing: Risk score {clamped_risk_score} >= 75 (clearly malicious). Skipping AI call."
                )
                should_call_ai = False

        ai_result: Optional[VerificationResult] = None

        # 3. AI Verification Call with Resilient Fallback
        if should_call_ai and self.ai_provider:
            logger.info("AI Verification Started")
            try:
                if hasattr(self.ai_provider, "verify_email"):
                    ai_result = await self.ai_provider.verify_email(
                        email, rule_findings=all_findings
                    )
                    logger.info("AI Verification Completed")
                else:
                    logger.warning("AI Provider does not implement verify_email. Skipping AI call.")
            except Exception as e:
                logger.warning(
                    f"AI Verification failed due to error: {e}. Falling back seamlessly to Rule-Based Engine."
                )

        # 4. Final Verdict Determination
        rule_is_legitimate = clamped_risk_score < 50

        if clamped_risk_score < 20:
            risk_level = "Low"
        elif clamped_risk_score < 50:
            risk_level = "Medium"
        elif clamped_risk_score < 75:
            risk_level = "High"
        else:
            risk_level = "Critical"

        confidence = 90.0 if is_trusted_sender else (85.0 if rule_is_legitimate else 95.0)
        final_is_legitimate = rule_is_legitimate

        if all_findings:
            triggered_summary = "; ".join(all_findings[:5])  # Limit to top 5 for readability
            if len(all_findings) > 5:
                triggered_summary += f" ... (+{len(all_findings) - 5} more findings)"
        else:
            triggered_summary = "No suspicious patterns detected."

        final_reason = (
            "All security checks passed. Verified legitimate email."
            if rule_is_legitimate and not all_findings
            else (
                f"Risk Score: {clamped_risk_score}/100. Rules triggered: {', '.join(all_rules[:5])}. "
                f"Details: {triggered_summary}"
            )
        )

        if ai_result:
            all_threats = list(dict.fromkeys(all_threats + ai_result.threats))
            confidence = (confidence + ai_result.confidence) / 2.0

            if (
                not ai_result.is_legitimate
                or ai_result.confidence < settings.verification.verification_confidence_threshold
            ):
                final_is_legitimate = False
                if ai_result.risk_level in ["High", "Critical"]:
                    risk_level = ai_result.risk_level
                final_reason = f"Rule/AI Flagged: {final_reason} | AI Reason: {ai_result.reason}"
            else:
                if rule_is_legitimate:
                    final_is_legitimate = True
                    final_reason = (
                        f"Verified Legitimate by Rules and AI. AI Reason: {ai_result.reason}"
                    )

        status = "Legitimate" if final_is_legitimate else "Suspicious"
        decision = "Notification Sent" if final_is_legitimate else "Notification Blocked"

        # 5. Granular Stage Logging Output
        logger.info(f"Verification Result: {status}")
        logger.info(f"Risk Score: {clamped_risk_score}/100 | Level: {risk_level}")
        logger.info(f"Triggered Rules: {all_rules}")
        logger.info(f"Decision: {decision}")
        if not final_is_legitimate or clamped_risk_score > 0:
            logger.info(f"Reason: {final_reason}")

        return VerificationResult(
            is_legitimate=final_is_legitimate,
            status=status,
            confidence=round(confidence, 2),
            risk_score=clamped_risk_score,
            risk_level=risk_level,
            decision=decision,
            reason=final_reason,
            triggered_rules=all_rules,
            threats=all_threats,
        )
