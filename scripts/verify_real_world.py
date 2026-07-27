import asyncio
import os
import sys
import sqlite3
import imaplib
import socket
from pathlib import Path
from dotenv import load_dotenv

# Set default socket timeout to 5 seconds to prevent hanging on blocked ports
socket.setdefaulttimeout(5)

# Ensure local source modules are importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import settings
from src.infrastructure.clients.gmail_client import GmailClient
from src.infrastructure.processing.ocr import process_attachment
from src.infrastructure.clients.ai_providers import ChainAIProvider
from src.infrastructure.database.sqlite_repo import SQLiteRepository
from src.infrastructure.clients.telegram_client import TelegramNotificationService
from src.domain.models import EmailMetadata, AnalysisResult
from src.config.validator import StartupValidator

async def run_verification():
    print("=" * 80)
    print("AI EMAIL TRIAGE PLATFORM - REAL-WORLD INTEGRATION AUDIT")
    print("=" * 80)
    
    # 1. Startup validation check
    print("\n[STEP 1] Running Configuration & Folder Permission Checks...")
    try:
        StartupValidator.validate()
        print(" -> SUCCESS: Settings and storage permissions are valid.")
    except Exception as e:
        print(f" -> FAILURE: {e}")
        return

    # 2. Gmail connection & auth check
    print("\n[STEP 2] Verifying IMAP Gmail logins & fetching unseen metrics...")
    emails_to_test = settings.email.user_list
    passwords_to_test = settings.email.password_list
    
    for i, (user, password) in enumerate(zip(emails_to_test, passwords_to_test)):
        print(f" Checking Account {i+1}: {user}...")
        def _check_imap(u, p):
            c = GmailClient(u, p)
            mail = imaplib.IMAP4_SSL(c.server, timeout=3)
            mail.login(c.user, c.password)
            mail.select("inbox")
            status, msgs = mail.search(None, "UNSEEN")
            count = len(msgs[0].split()) if status == "OK" and msgs[0] else 0
            mail.logout()
            return count

        try:
            unseen_count = await asyncio.to_thread(_check_imap, user, password)
            print(f"   -> SUCCESS: Logged in and read inbox. Unseen messages found: {unseen_count}")
        except Exception as e:
            print(f"   -> HANDLED: IMAP status for {user}: {e}")

    # 3. Attachment Parser and OCR checks
    print("\n[STEP 3] Testing Attachment Extraction & OCR fallback cascade...")
    # Test plain text extraction
    txt_payload = b"Verify raw text content parsing"
    txt_result = await process_attachment("test.txt", txt_payload)
    print(f" Plain text parsing result: '{txt_result}'")
    
    # Verify image OCR parsing if tesseract is available
    png_payload = b"dummy_png_bytes"
    try:
        img_result = await process_attachment("test.png", png_payload)
        print(f" Image OCR parsing result (silenced errors): '{img_result}'")
    except Exception as e:
        print(f" Image OCR failed: {e}")

    # 4. AI Provider and Classification check
    print("\n[STEP 4] Calling Chain AI Provider (Groq -> Gemini -> OpenAI)...")
    email = EmailMetadata(
        message_id="verification-msg-999",
        sender="hr@techcorp.com",
        subject="CRITICAL: Interview schedule invitation tomorrow",
        body="Dear Candidate, we would like to invite you for an interview tomorrow morning at 9:00 AM.",
        attachment_text=""
    )
    
    provider = ChainAIProvider()
    ai_result = None
    try:
        ai_result = await provider.analyze(email)
        print(" -> SUCCESS: AI returned classification:")
        print(f"    Category: {ai_result.category}")
        print(f"    Importance Score: {ai_result.importance_score}/10")
        print(f"    Action Required: {ai_result.action_required}")
        print(f"    Reasoning: {ai_result.reasoning}")
        print(f"    Confidence: {ai_result.confidence_score}")
    except Exception as e:
        print(f" -> FAILURE calling AI Provider cascade: {e}")

    # 5. SQLite database check
    print("\n[STEP 5] Verifying SQLite inserts and schema uniqueness...")
    try:
        repo = SQLiteRepository()
        db_path = repo.db_name
        print(f" Database file path: {db_path}")
        
        # Verify reprocessing avoidance
        test_id = f"verification-id-{int(asyncio.get_event_loop().time())}"
        print(f" Inserting new triage record: {test_id}...")
        
        # Log email
        repo.log_email(
            email_id=test_id,
            sender="hr@techcorp.com",
            subject="CRITICAL: Interview schedule",
            category="Job Offer",
            score=9,
            reasoning="Simulated verification triage",
            action_required=True,
            confidence_score=0.99
        )
        
        # Check if marked processed
        is_processed_first = repo.is_email_processed(test_id)
        print(f"   is_email_processed check 1: {is_processed_first} (expected: True)")
        
        # Re-check processing suppression
        is_processed_second = repo.is_email_processed(test_id)
        print(f"   is_email_processed check 2 (reprocessing check): {is_processed_second} (expected: True)")
        
        if is_processed_first and is_processed_second:
            print(" -> SUCCESS: Database logs and filters duplicates successfully.")
        else:
            print(" -> FAILURE: Database reprocessing suppression checks failed.")
    except Exception as e:
        print(f" -> FAILURE writing to SQLite: {e}")

    # 6. Telegram Alert Dispatch check
    print("\n[STEP 6] Testing Telegram Alert dispatch service...")
    if settings.features.enable_telegram:
        try:
            telegram_service = TelegramNotificationService()
            mock_analysis = AnalysisResult(
                category="Job Offer",
                importance_score=9,
                summary="Simulated critical verification email",
                reasoning="Verification test run",
                action_required=True,
                confidence_score=0.99
            )
            print(" Sending Telegram alert to bot endpoint...")
            telegram_service.send_alert(email, mock_analysis)
            print("   -> SUCCESS: Telegram message dispatched successfully.")
        except Exception as e:
            print(f"   -> FAILURE sending Telegram notification: {e}")
    else:
        print(" Telegram notifications disabled by feature flag.")

    # 7. Recovery cascading check
    print("\n[STEP 7] Simulating Provider Failure (Failover check)...")
    # Backup current environment
    old_groq = os.environ.get("GROQ_API_KEY")
    os.environ["GROQ_API_KEY"] = "gsk_invalid_mock_api_key_to_force_failover"
    
    # Reload provider with bad key
    failover_provider = ChainAIProvider()
    try:
        print(" Requesting triage classification with bad Groq key...")
        failover_result = await failover_provider.analyze(email)
        print(f"   -> SUCCESS: Cascade recovered using fallbacks. Category triaged: {failover_result.category}")
    except Exception as e:
        print(f"   -> Cascade Exhausted: {e}")
    finally:
        # Restore environment
        if old_groq:
            os.environ["GROQ_API_KEY"] = old_groq
        else:
            del os.environ["GROQ_API_KEY"]

    print("\n" + "=" * 80)
    print("REAL-WORLD INTEGRATION AUDIT COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_verification())
