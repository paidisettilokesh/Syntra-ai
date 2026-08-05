import asyncio
import email
import hashlib
import imaplib
from email.header import decode_header
from typing import List

from src.config.settings import settings
from src.domain.interfaces import IMailClient
from src.domain.models import EmailMetadata
from src.infrastructure.processing.ocr import process_attachment
from src.infrastructure.processing.parser import clean_email_body
from src.utils.circuit_breaker import CircuitBreaker
from src.utils.logger import get_logger

logger = get_logger(__name__)


class GmailClient(IMailClient):
    def __init__(self, user: str, password: str):
        self.user = user
        self.password = password
        self.server = settings.email.imap_server
        self.circuit_breaker = CircuitBreaker(
            name=f"Gmail-{self.user}",
            failure_threshold=3,
            recovery_timeout=300.0,
        ) if settings.features.enable_circuit_breaker else None

    def _decode_mime_words(self, s: str) -> str:
        if not s:
            return ""
        decoded_bytes, charset = decode_header(s)[0]
        if isinstance(decoded_bytes, bytes):
            return decoded_bytes.decode(charset if charset else "utf-8", errors="ignore")
        return str(decoded_bytes)

    def _fetch_emails_sync(self) -> List[dict]:
        """
        Synchronous method to fetch emails from IMAP.
        This must be run in a separate thread to avoid blocking the asyncio event loop.
        """
        raw_results = []
        mail = imaplib.IMAP4_SSL(self.server, timeout=15)
        try:
            mail.login(self.user, self.password)
            mail.select("inbox")

            status, messages = mail.search(None, "ALL")
            if status != "OK" or not messages[0]:
                return raw_results

            # Limit to 25 most recent inbox emails (deduplicated by SQLite repository)
            email_ids = messages[0].split()[-25:]
            for e_id in email_ids:
                status, msg_data = mail.fetch(e_id, "(BODY.PEEK[])")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        raw_message_id = msg.get("Message-ID", "").strip()
                        subject = self._decode_mime_words(msg.get("Subject", ""))
                        sender = self._decode_mime_words(msg.get("From", ""))
                        date_str = str(msg.get("Date", ""))

                        # Issue #5: Deterministic fallback ID using content hash.
                        # IMAP sequence numbers (e_id) are session-scoped and non-persistent,
                        # so we compute a stable hash if Message-ID header is absent.
                        if raw_message_id:
                            message_id = raw_message_id
                        else:
                            fingerprint = f"{sender}|{subject}|{date_str}"
                            message_id = "hash-" + hashlib.sha256(fingerprint.encode()).hexdigest()[:32]
                            logger.debug(
                                f"No Message-ID header found. Using deterministic hash ID: {message_id}"
                            )

                        auth_headers = {
                            "authentication_results": str(msg.get("Authentication-Results", "")),
                            "received_spf": str(msg.get("Received-SPF", "")),
                            "dkim_signature": str(msg.get("DKIM-Signature", "")),
                        }

                        body = ""
                        attachments = []
                        attachment_mime_info = []

                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))

                                if content_type == "text/html" and "attachment" not in content_disposition:
                                    body_html = part.get_payload(decode=True).decode(errors="ignore")
                                    body += clean_email_body(body_html) + "\n"
                                elif content_type == "text/plain" and "attachment" not in content_disposition:
                                    body_plain = part.get_payload(decode=True).decode(errors="ignore")
                                    body += clean_email_body(body_plain) + "\n"
                                elif "attachment" in content_disposition:
                                    filename = part.get_filename()
                                    if filename:
                                        payload = part.get_payload(decode=True)
                                        if payload:
                                            if len(payload) > 5 * 1024 * 1024:
                                                logger.warning(
                                                    f"Attachment {filename} exceeds 5MB limit. Skipping."
                                                )
                                                continue
                                            attachments.append((filename, payload))
                                            attachment_mime_info.append({
                                                "filename": filename,
                                                "declared_mime": content_type,
                                                "payload": payload,
                                                "size": len(payload)
                                            })
                        else:
                            try:
                                raw_body = msg.get_payload(decode=True).decode(errors="ignore")
                                body = clean_email_body(raw_body)
                            except Exception:
                                pass

                        # Explicitly mark as seen (Server-side Idempotency)
                        mail.store(e_id, "+FLAGS", "\\Seen")

                        raw_results.append({
                            "message_id": message_id,
                            "sender": sender,
                            "subject": subject,
                            "body": body.strip(),
                            "attachments": attachments,
                            "auth_headers": auth_headers,
                            "attachment_mime_info": attachment_mime_info
                        })
        finally:
            try:
                mail.logout()
            except Exception:
                pass

        return raw_results

    async def get_unseen_emails(self) -> List[EmailMetadata]:
        emails = []
        try:
            if self.circuit_breaker:
                raw_emails = await self.circuit_breaker.call(
                    asyncio.to_thread, self._fetch_emails_sync
                )
            else:
                raw_emails = await asyncio.to_thread(self._fetch_emails_sync)
                
            for raw in raw_emails:
                attachment_text = ""
                for filename, payload in raw["attachments"]:
                    extracted = await process_attachment(filename, payload)
                    if extracted:
                        attachment_text += f"\n[Attachment: {filename}]\n{extracted}\n"

                emails.append(
                    EmailMetadata(
                        message_id=raw["message_id"],
                        sender=raw["sender"],
                        subject=raw["subject"],
                        body=raw["body"],
                        attachment_text=attachment_text.strip(),
                        auth_headers=raw["auth_headers"],
                        attachment_mime_info=raw["attachment_mime_info"]
                    )
                )
        except RuntimeError as e:
            # Circuit breaker is OPEN
            logger.warning(str(e))
        except Exception as e:
            logger.error(f"Gmail error for {self.user}: {e}")
            
        return emails
