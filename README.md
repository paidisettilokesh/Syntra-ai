# Syntra AI – Autonomous Email Intelligence Platform

Syntra AI is a production-grade, autonomous email intelligence and triage platform built using **Clean Architecture** and SOLID principles. It continuously monitors multiple Gmail inboxes via IMAP, cleans HTML bodies and attachments using multi-engine OCR, evaluates fast-path rules, classifies message importance using an AI Provider Cascade (Groq Llama-3.3-70b/8b $\rightarrow$ Gemini $\rightarrow$ OpenAI), persists records to SQLite (WAL mode), and dispatches structured real-time alerts to Telegram via the **Telegram Bot API**.

---

## 🏗️ Clean Architecture Overview

Syntra AI enforces strict dependency inversion across four decoupled layers:

- **Domain Layer (`src/domain/`)**: Pure entity models, exceptions, and abstract interfaces (`IRepository`, `IMailClient`, `IAIProvider`, `INotificationService`).
- **Application Layer (`src/application/`)**: Business logic orchestration (`EmailOrchestrator`) and deterministic triage (`RuleEngine`).
- **Infrastructure Layer (`src/infrastructure/`)**: Concrete service implementations (`SQLiteRepository`, `GmailClient`, `ChainAIProvider`, `TelegramNotificationService`, OCR engine).
- **Presentation Layer (`src/presentation/`)**: Polling daemon loop (`AgentScheduler`) and CLI entrypoints (`main.py`).

---

## 🛠️ Technology Stack

- **Core Engine**: Python 3.11+
- **Storage Engine**: SQLite3 (Write-Ahead Logging mode enabled)
- **AI Provider Cascade**: Groq (Llama-3.3-70b-versatile & Llama-3.1-8b-instant) $\rightarrow$ Google Gemini $\rightarrow$ OpenAI
- **OCR Engine**: Tesseract OCR, `pdfplumber`, PyMuPDF (`fitz`), Python-Docx
- **Notification Engine**: Telegram Bot API (`requests` HTTP REST Client)
- **Dependency Injection**: IoC Container (`src/utils/di.py`)

---

## 📱 Telegram Bot Setup Guide

### Step 1: Create your Telegram Bot with BotFather
1. Open **Telegram** and search for **[@BotFather](https://t.me/BotFather)**.
2. Send `/newbot` to BotFather.
3. Choose a friendly name (e.g., `Syntra AI Notifier`) and a unique username ending in `bot` (e.g., `SyntraAINotifierBot`).
4. BotFather will output your **`TELEGRAM_BOT_TOKEN`** (e.g., `7123456789:AAFx...`). Copy this token.

### Step 2: Obtain your TELEGRAM_CHAT_ID
1. Search for your newly created bot on Telegram and click **Start** (or send `/start`).
2. Search for **[@userinfobot](https://t.me/userinfobot)** or **[@GetMyChatID_Bot](https://t.me/GetMyChatID_Bot)** on Telegram.
3. Send any message to retrieve your numerical **Chat ID** (e.g., `987654321` or `-100...` for groups).

---

## ⚙️ Environment Configuration (`.env`)

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```env
# AI Providers
GROQ_API_KEY="your_groq_api_key_here"

# Dual Email Configurations
EMAIL_USERS="paidisettilokesh@gmail.com"
EMAIL_PASSWORDS="app_password_1"

# Telegram Notifications
TELEGRAM_BOT_TOKEN="7123456789:AAFx..."
TELEGRAM_CHAT_ID="987654321"

# Feature Flags
FEATURE_ENABLE_TELEGRAM=True
```

---

## 🧪 Testing Telegram Integration

Syntra AI includes a standalone verification script to test Telegram connection before launching the main service:

```bash
python test_telegram.py
```

Expected output on success:
```text
============================================================
Syntra AI - Telegram Notification Service Test
============================================================
TELEGRAM_BOT_TOKEN: [SET]
TELEGRAM_CHAT_ID:   [SET]

[Step 1] Verifying Bot Token with Telegram API...
 -> SUCCESS: Connected to Bot '@SyntraAINotifierBot' (Syntra AI Notifier)

[Step 2] Sending test notification via TelegramNotificationService...
 -> SUCCESS: Telegram test message sent successfully.

============================================================
TELEGRAM INTEGRATION TEST: PASSED
============================================================
```

---

## 🚀 Running Syntra AI

### 1. Run Complete Test Suite (Pytest)
```bash
python -m pytest tests/
```

### 2. Run Real-World Audit Script
```bash
python scripts/verify_real_world.py
```

### 3. Launch Syntra AI Autonomous Service
```bash
python main.py
```

---

## 🔧 Troubleshooting Guide

| Issue / Symptom | Potential Cause | Solution |
| :--- | :--- | :--- |
| `HTTP 401 Unauthorized` | Invalid `TELEGRAM_BOT_TOKEN` | Verify bot token format provided by @BotFather. |
| `HTTP 400 Bad Request` | Invalid `TELEGRAM_CHAT_ID` | Send a message to your bot and retrieve chat ID using @userinfobot. |
| `ConfigurationError` on startup | Missing Telegram environment variables | Ensure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` exist in `.env`. |
| Groq 429 Rate Limit | 70B daily token limit reached | Syntra AI automatically engages `llama-3.1-8b-instant` fallback. |

---

## 📄 License
MIT License. Syntra AI Enterprise Edition.
