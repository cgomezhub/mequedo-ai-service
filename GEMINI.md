# Gemini Project Context: Mequedo AI Service

This project is a Django-based AI service for **Mequedo**, an accommodation platform in Venezuela. It provides a chatbot (Karen) for searching listings and integrates with WhatsApp for notifications, interactions, and background tasks.

## Tech Stack

- **Framework:** Django with Django Rest Framework (DRF)
- **AI Orchestration:** CrewAI (Multi-Agent System), formerly LangChain
- **LLMs:** OpenAI, NVIDIA AI Endpoints (e.g., Llama 3), and Google Gemini
- **Database:** MongoDB (Listings, Locations, Scheduled Tasks) and SQLite (Django default)
- **Integrations:** WhatsApp Cloud API (Using background threading)

---

## Core Persona: Karen

- **Name:** Karen
- **Role:** Accommodation search assistant for Mequedo in Venezuela.
- **Tone:** Professional, helpful, and concise.
- **Language:** Primarily Spanish for user interactions.
- **Constraint:** Only suggest accommodations found in the provided database context.

---

## Coding Standards & Guidelines

### 1. General Style

- Follow **PEP 8** for Python code.
- Use **Type Hints** for function signatures to improve clarity and maintainability.
- Provide **Docstrings** for classes and important functions.

### 2. Error Handling & Logging

- **No `print()` statements:** Never use `print()` for application logging. Always use the standard `logging` module (`logger = logging.getLogger(__name__)`).
- **Log Levels:** Adhere to appropriate log levels based on the configured `LOG_LEVEL` (e.g., `logger.debug()`, `logger.info()`, `logger.warning()`, `logger.error()`).
- **Credential Masking:** Always mask sensitive credentials (such as database passwords, tokens, API keys) when logging configuration parameters, database connection strings, or system parameters.
- **Graceful Failures:** Implement robust `try-except` blocks around external service calls (MongoDB, LLM endpoints, WhatsApp APIs). Never expose raw exception stack traces or DB errors to final users.

### 3. Security & Validation

- **Sanitize Input:** Always sanitize user-provided strings to prevent injections or malicious payloads.
- **Prompt Injection:** Monitor prompt injection patterns using blocklist/regex patterns (see `chatbot/views.py` for regex matching rules guarding system prompts).
- **Guest Firewall:** Enforce registration rules where CrewAI execution is restricted to logged-in/registered phone numbers. Return a standard conversion prompt for anonymous/unregistered inputs.
- **Rate Limiting:** Use DRF's built-in throttling configurations for public-facing endpoints.

### 4. Database Interactions

- **MongoDB via Pymongo:** Use MongoDB for listings, user status, and scheduler tasks.
- **SSL/TLS Safety:** Always use `certifi.where()` for secure SSL/TLS connections when initializing the `MongoClient`.
- **Validation:** Always validate `ObjectId` formats before executing queries to prevent database injection or runtime casting exceptions.

### 5. Asynchronous Processing & Timeouts

- **WhatsApp Webhook:** WhatsApp webhook views must acknowledge Meta requests immediately with a `200 OK` status and run the parsing/sending logic in background threads.
- **Async Chatbot Views:** To avoid Vercel or gateway timeouts (typically 30 seconds), client searches should use `ChatbotAsyncView` to enqueue the request, and `ChatbotStatusView` to poll for results.

### 6. LLM Fallbacks & Orchestration

- **Fallback Chain:** Orchestrate LLM tasks using the priority cascade: **NVIDIA NIM (primary) -> Gemini (fallback) -> OpenAI (secondary fallback)**.
- **Robust Execution:** Use the wrapper `_kickoff_with_retry` for running CrewAI kicks. This includes automatic provider switching and exponential backoff.
- **Caching:** Cache chatbot outputs for 60 seconds (using the memory cache `_RESPONSE_CACHE` inside `chatbot/views.py`) to handle duplicated retry payloads.

### 7. WhatsApp Interface Constraints

- **Interactive Buttons:** When sending interactive messages, respect Meta's limit of **maximum 3 buttons**.
- **Interactive Lists:** If the number of interactive options exceeds 3, automatically transition to an Interactive List menu. Keep list item labels within Meta's **24-character limit**.
- **Notification Templates:** Programmatic notifications must match registered WhatsApp Cloud templates, including:
  - `reservation_request_notice`
  - `reservation_payment_notice`
  - `host_payment_notice`
  - `guest_payment_notice`
  - `admin_payment_review`
  - Approved rejection templates.

---

## Key Files & Directories

- `chatbot/views.py`: Main AI logic, caching, sanitization, guest firewall, and async views.
- `chatbot/crew/`: CrewAI multi-agent configurations, intent routers, and fallback configuration.
- `whatsapp_integration/views.py`: Webhook endpoints and instant acknowledgement logic.
- `whatsapp_integration/message_handler.py`: Incoming message parser, template/short-circuit router, and interactive button/list builder.
- `whatsapp_integration/services.py`: Meta WhatsApp Cloud API request sender.
- `whatsapp_integration/management/commands/run_reservation_scheduler.py`: Background worker script with credentials masking.

---

## Interaction with Gemini

When assisting with this codebase:

- Maintain the "Karen" persona logic when editing chatbot prompts.
- Prefer clear, modular, and type-hinted code.
- Ensure any new endpoints follow the established DRF patterns used in the project.
- Respect the existing mixture of English (for code/logic) and Spanish (for user-facing content and some comments).
