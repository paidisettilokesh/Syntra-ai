# OpenRouter Fallback Integration & Architecture

## Overview

The Syntra AI Mail Agent uses an infrastructure-level LLM provider architecture (`ILLMProvider`) to manage primary model execution and automatic provider fallback.

Primary Provider: **Groq** (`GroqProvider`)  
Fallback Provider: **OpenRouter** (`OpenRouterProvider`)  

---

## Fallback Flow Architecture

```text
                     ┌───────────────────────────┐
                     │    ChainAIProvider        │
                     │    (Domain Level)         │
                     └─────────────┬─────────────┘
                                   │ complete(system, user)
                     ┌─────────────▼─────────────┐
                     │    FallbackLLMProvider    │
                     │    (Orchestrator)         │
                     └─────────────┬─────────────┘
                                   │
             ┌─────────────────────┴─────────────────────┐
             │                                           │
  ┌──────────▼──────────┐                     ┌──────────▼──────────┐
  │    GroqProvider     │                     │ OpenRouterProvider  │
  │    (Primary)        │                     │    (Fallback)       │
  └──────────┬──────────┘                     └──────────┬──────────┘
             │                                           │
  1. llama-3.3-70b-versatile                 1. google/gemini-2.5-flash
     (retries: 2, backoff + jitter)             (OpenAI SDK @ OpenRouter endpoint)
             │                                           │
  2. llama-3.1-8b-instant                    2. deepseek/deepseek-chat-v3
     (retries: 2, backoff + jitter)                      │
                                             3. qwen/qwen3-32b
```

---

## Error Handling & Retry Policy

### Groq Retry Strategy
- **Max Retries:** 2 retries (3 total attempts per model).
- **Backoff:** Exponential backoff with uniform random jitter ($1.0 \times 2^{\text{attempt}} + \text{jitter}$).
- **Retriable Errors:**
  - `RateLimitError` (HTTP 429)
  - `APITimeoutError`
  - `APIConnectionError`
  - `InternalServerError` (HTTP 5xx)

### Provider Switch Trigger
If all Groq retries fail or if an unhandled error occurs on Groq:
1. `FallbackLLMProvider` catches `AIProviderError`.
2. Emits structured log: `WARNING [LLM] Provider=Groq Status=Failed after retries. Activating OpenRouter fallback.`
3. Swaps execution to `OpenRouterProvider`.

### OpenRouter Cascade
- Uses official `AsyncOpenAI` SDK configured with `base_url="https://openrouter.ai/api/v1"`.
- Iterates through candidate models until one succeeds:
  1. `google/gemini-2.5-flash`
  2. `deepseek/deepseek-chat-v3`
  3. `qwen/qwen3-32b`
- Stops immediately on first success.

---

## Configuration

Set the environment variable in `.env`:

```env
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-v1-...
```

---

## Structured Logging Examples

Successful Groq call:
```text
INFO [LLM] Provider=Groq Model=llama-3.3-70b-versatile Status=Success latency=0.82s retries=0
```

Groq Rate Limit:
```text
WARNING [LLM] Provider=Groq Model=llama-3.3-70b-versatile Status=RateLimited retry=1/2 latency=0.20s
```

Switching to OpenRouter:
```text
WARNING [LLM] Provider=Groq Status=Failed after retries. Activating OpenRouter fallback.
INFO [LLM] Switching to OpenRouter
```

OpenRouter Success:
```text
INFO [LLM] Provider=OpenRouter Model=google/gemini-2.5-flash Status=Success latency=1.15s
```
