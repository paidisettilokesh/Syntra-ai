#!/usr/bin/env python3
"""
Syntra AI - Comprehensive Telegram Notification Test Script
Verifies Telegram Bot Token, Chat ID connection, payload delivery, HTML escaping,
and TelegramNotificationService end-to-end integration.
Exits with code 0 on true delivery success, 1 on any failure.
"""

import html
import os
import sys
import requests
from dotenv import load_dotenv

# Load environment configuration
load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")

from src.config.settings import settings
from src.domain.models import AnalysisResult, EmailMetadata
from src.infrastructure.clients.telegram_client import TelegramNotificationService


def mask_token(token: str) -> str:
    if not token or len(token) <= 8:
        return "UNSET"
    return f"{token[:4]}...{token[-4:]}"


def run_telegram_test():
    print("=" * 70)
    print("SYNTRA AI - TELEGRAM NOTIFICATION SERVICE DIAGNOSTIC TEST")
    print("=" * 70)

    bot_token = (
        settings.notify.telegram_bot_token.get_secret_value()
        if settings.notify.telegram_bot_token
        else None
    )
    chat_id = (
        settings.notify.telegram_chat_id.get_secret_value()
        if settings.notify.telegram_chat_id
        else None
    )

    print(f"Loaded Bot Token: {mask_token(bot_token)}")
    print(f"Loaded Chat ID:   {chat_id}")

    if not bot_token or not chat_id:
        print("\n❌ FAILURE: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # [Step 1] Verify Bot Token with getMe API
    # -------------------------------------------------------------------------
    print("\n[Step 1] Verifying Bot Token with Telegram getMe API...")
    getme_url = f"https://api.telegram.org/bot{bot_token}/getMe"
    print(f" Request URL: {getme_url}")

    try:
        r_getme = requests.get(getme_url, timeout=10)
        print(f" HTTP Status: {r_getme.status_code}")
        print(f" Response:    {r_getme.text}")

        if r_getme.status_code != 200:
            print(f" ❌ STEP 1 FAILED: HTTP Status {r_getme.status_code}")
            sys.exit(1)

        data_getme = r_getme.json()
        if not data_getme.get("ok"):
            print(f" ❌ STEP 1 FAILED: {data_getme.get('description')}")
            sys.exit(1)

        bot_info = data_getme.get("result", {})
        print(f" -> SUCCESS: Connected to Bot '@{bot_info.get('username')}' ({bot_info.get('first_name')})")
    except Exception as e:
        print(f" ❌ STEP 1 ERROR: {e}")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # [Step 2] Test Simple Unformatted Message Payload
    # -------------------------------------------------------------------------
    print("\n[Step 2] Testing Simple Message Payload Delivery...")
    send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    simple_payload = {
        "chat_id": chat_id,
        "text": "Syntra AI - Simple Connection Test Message",
    }
    print(f" Request URL: {send_url}")
    print(f" Payload:     {simple_payload}")

    try:
        r_simple = requests.post(send_url, json=simple_payload, timeout=10)
        print(f" HTTP Status: {r_simple.status_code}")
        print(f" Response:    {r_simple.text}")

        if r_simple.status_code != 200:
            print(f" ❌ STEP 2 FAILED: HTTP {r_simple.status_code}")
            sys.exit(1)

        data_simple = r_simple.json()
        if not data_simple.get("ok"):
            print(f" ❌ STEP 2 FAILED: {data_simple.get('description')}")
            sys.exit(1)

        msg_id_simple = data_simple.get("result", {}).get("message_id")
        print(f" -> SUCCESS: Simple message delivered. Message ID: {msg_id_simple}")
    except Exception as e:
        print(f" ❌ STEP 2 ERROR: {e}")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # [Step 3] Test Formatted HTML Message with Angle Brackets Escaping
    # -------------------------------------------------------------------------
    print("\n[Step 3] Testing HTML Formatted Message with Escaped Entities...")
    test_sender = "Alex Rivera <alex.rivera@enterprise.com>"
    formatted_html = (
        "🚨 <b>Syntra AI Diagnostic Alert</b>\n\n"
        f"📧 <b>Sender:</b>\n{html.escape(test_sender)}\n\n"
        "📝 <b>Subject:</b>\nTelegram HTML Payload Test"
    )
    html_payload = {
        "chat_id": chat_id,
        "text": formatted_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    print(f" Request URL: {send_url}")
    print(f" Payload:     {html_payload}")

    try:
        r_html = requests.post(send_url, json=html_payload, timeout=10)
        print(f" HTTP Status: {r_html.status_code}")
        print(f" Response:    {r_html.text}")

        if r_html.status_code != 200:
            print(f" ❌ STEP 3 FAILED: HTTP {r_html.status_code}")
            sys.exit(1)

        data_html = r_html.json()
        if not data_html.get("ok"):
            print(f" ❌ STEP 3 FAILED: {data_html.get('description')}")
            sys.exit(1)

        msg_id_html = data_html.get("result", {}).get("message_id")
        print(f" -> SUCCESS: Formatted HTML message delivered. Message ID: {msg_id_html}")
    except Exception as e:
        print(f" ❌ STEP 3 ERROR: {e}")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # [Step 4] End-to-End Test via TelegramNotificationService
    # -------------------------------------------------------------------------
    print("\n[Step 4] Testing TelegramNotificationService End-to-End Delivery...")
    try:
        service = TelegramNotificationService()
        mock_email = EmailMetadata(
            message_id="test-msg-002",
            sender="SmartBridge <noreply@thesmartbridge.com>",
            subject="Syntra AI Production Triage Verification",
            body="This is an automated end-to-end integration test email for Syntra AI.",
        )
        mock_analysis = AnalysisResult(
            category="Interview",
            importance_score=9,
            summary="Autonomous triage alert verification for Telegram Bot API integration.",
            reasoning="Diagnostic verification test run.",
            action_required=True,
            confidence_score=0.99,
        )

        service.send_alert(mock_email, mock_analysis)
        print(" -> SUCCESS: TelegramNotificationService delivered alert cleanly.")
    except Exception as e:
        print(f" ❌ STEP 4 FAILED: {e}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("TELEGRAM INTEGRATION VERIFICATION: ALL 4 STEPS PASSED 100% PERFECTLY")
    print("=" * 70)
    sys.exit(0)


if __name__ == "__main__":
    run_telegram_test()
