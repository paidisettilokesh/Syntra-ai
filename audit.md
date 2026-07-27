# Syntra AI – Autonomous Email Intelligence Platform - Architecture Audit

## 1. System Overview
An autonomous, localized Python agent designed to securely connect to multiple Gmail accounts via IMAP, read unread emails, and utilize Groq's LLaMA-3.3-70b/8b model cascade to triage them. If an email is deemed "High Priority", requires action, or has an importance score >= 7, it dispatches an immediate notification alert via the **Telegram Bot API**.

## 2. File Architecture

### `src/infrastructure/database/sqlite_repo.py`
- **Role**: Database operations and idempotency.
- **Details**: Uses `sqlite3` to maintain a local `agent_logs.db` file in WAL mode. The `processed_emails` table prevents duplicate processing and duplicate notifications by logging the `email_id`, `sender`, `subject`, `category`, and `score`.

### `src/infrastructure/clients/ai_providers.py`
- **Role**: Artificial Intelligence engine.
- **Details**: Connects to the Groq API securely. Uses strict JSON-mode formatting to guarantee the model outputs a specific schema (`category`, `importance_score`, `summary`, `action_required`). 
- **Features added**: Gracefully handles API rate limits (HTTP 429) via automatic fallback to `llama-3.1-8b-instant` and secondary Gemini/OpenAI cascades.

### `src/infrastructure/clients/telegram_client.py`
- **Role**: Telegram Alerting Gateway.
- **Details**: Dispatches structured HTML alerts via Telegram Bot API using the lightweight `requests` HTTP client.
- **Features added**: Implements 10s timeouts, network retries, and silent exception handling to ensure email processing is never halted by network issues.

### `main.py`
- **Role**: Central Entrypoint & Dependency Injection.
- **Details**:
  - Validates configuration via `StartupValidator`.
  - Binds abstractions in IoC `container`.
  - Launches `AgentScheduler` polling loop.

### `.env`
- **Role**: Secure Credentials Storage.
- **Details**: Holds `GROQ_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and comma-separated `EMAIL_USERS` and `EMAIL_PASSWORDS`.

## 3. Libraries & Dependencies
- `requests`: HTTP REST API client for Telegram notifications.
- `groq`: Official SDK for AI integration.
- `python-dotenv`: Environment variable parsing.
- `pydantic`: Structured validation models.
- Built-in libraries used: `imaplib`, `email`, `sqlite3`, `asyncio`, `os`, `sys`, `json`.
