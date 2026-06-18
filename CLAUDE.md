# Mequedo AI Service: Developer Guide

**Project:** Django-based AI service for Mequedo (accommodation platform in Venezuela)  
**Core Product:** Karen chatbot for searching listings, integrated with WhatsApp  
**Current Status:** Transitioning from deterministic pipeline to CrewAI multi-agent architecture

---

## Quick Start

- **Framework:** Django + Django Rest Framework (DRF)
- **AI Orchestration:** CrewAI (multi-agent system)
- **LLMs:** OpenAI, NVIDIA AI Endpoints (Llama 3), Google Gemini
- **Database:** MongoDB (listings, locations, tasks) + SQLite (Django)
- **Key Integration:** WhatsApp Cloud API

See `GEMINI.md` for detailed project context. This file covers working patterns and architecture evolution.

---

## Core Persona: Karen

| Attribute | Value |
|-----------|-------|
| **Name** | Karen |
| **Role** | Accommodation search assistant for Mequedo (Venezuela) |
| **Tone** | Professional, helpful, concise |
| **Language** | Spanish (user-facing); English (code/logic) |
| **Constraint** | Only suggest accommodations in the database context |

---

## Coding Standards

### Error Handling & Logging

- **No `print()` statements.** Always use `logging.getLogger(__name__)`.
- **Mask sensitive data** when logging (passwords, tokens, API keys, connection strings).
- **Graceful failures** on external service calls (MongoDB, LLMs, WhatsApp). Never expose raw stack traces to users.
- **Log Levels:** Respect configured `LOG_LEVEL` (`debug`, `info`, `warning`, `error`).

### Code Quality

- Follow **PEP 8**.
- Use **type hints** on all function signatures.
- Provide **docstrings** for classes and important functions.
- Default to no comments; add only if the *why* is non-obvious.

### Security & Validation

- **Sanitize user input** to prevent injection.
- **Monitor prompt injection** using blocklist/regex patterns (see `chatbot/views.py`).
- **Guest firewall:** Restrict CrewAI execution to registered phone numbers; return conversion prompt for guests.
- **Rate limiting:** Use DRF throttling on public endpoints.
- **MongoDB:** Validate `ObjectId` format before queries; use `certifi.where()` for SSL/TLS.

### Asynchronous Processing

- **WhatsApp webhook:** Acknowledge Meta immediately (200 OK), run parsing in background threads.
- **Timeout prevention:** Use `ChatbotAsyncView` + `ChatbotStatusView` polling pattern for searches (Vercel gateway timeout ~30s).
- **Caching:** Cache chatbot outputs for 60 seconds using `_RESPONSE_CACHE` to handle retry payloads.

### LLM Orchestration

- **Fallback chain:** NVIDIA NIM (primary) → Gemini (fallback) → OpenAI (secondary)
- **Robust execution:** Use `_kickoff_with_retry` wrapper for CrewAI tasks (includes provider switching, exponential backoff).

### WhatsApp Constraints

- **Interactive buttons:** Max 3 buttons per message.
- **Interactive lists:** If >3 options, use list menu; keep item labels ≤24 characters.
- **Templates:** Match registered WhatsApp Cloud templates:
  - `reservation_request_notice`
  - `reservation_payment_notice`
  - `host_payment_notice`
  - `guest_payment_notice`
  - `admin_payment_review`

---

## Architecture: Multi-Agent CrewAI Migration

The project is transitioning to a CrewAI multi-agent system with 5 phases:

### Phase 1: Environment & Orchestration Setup

- [ ] Configure LLMs: Fast reasoning model (e.g., `gpt-4o-mini`, Llama 3 8B) + Deep reasoning model (e.g., `gpt-4o`, Llama 3 70B)
- [ ] Enable CrewAI memory systems: Short-Term, Long-Term (SQLite/MongoDB), Entity Memory (user tracking)
- [ ] Enable cross-agent caching to prevent duplicate queries

### Phase 2: Agent Design

**Accommodation Specialist Agent**
- Role: Expert database researcher
- Goal: Retrieve exact Mequedo listings matching user criteria
- Tools: `SearchAccommodationTool`
- Hyperparameters: `max_iter=3`, `allow_delegation=False`

**Customer Support Agent (Laura)**
- Role: Empathetic FAQ, booking assistant, brand ambassador
- Goal: Resolve inquiries and format final output
- Tools: `ScrapeWebsiteTool` (Mequedo FAQ), future `MequedoInternalCRMTool`
- Hyperparameters: `allow_delegation=True`

**Quality Assurance (QA) Agent**
- Role: Content validator & hallucination checker
- Goal: Ensure responses adhere to Mequedo's context and pricing
- Hyperparameters: `allow_delegation=False`

### Phase 3: Tool Engineering

- [ ] **`SearchAccommodationTool`** (custom): PyMongo integration, strict Pydantic schemas for `city`, `max_price`, `guests`
- [ ] **`MequedoFAQScraperTool`** (built-in): Target Mequedo FAQ/docs
- [ ] **`MequedoCRMTool`** (custom): User reservation data, booking history, profile status from internal MongoDB
- [ ] **`WhatsAppNotifierTool`** (custom): Proactive follow-ups

### Phase 4: Task Definition & Execution Strategy

- [ ] **`IntentExtractionTask`:** Route to FAQ, listing search, or CRM support; output structured JSON (`IntentSchema`)
- [ ] **`DatabaseSearchTask`:** Assigned to Specialist; receives context from intent extraction
- [ ] **`QAValidationTask`:** Assigned to QA Agent; validates search data; `human_input=True` only in dev
- [ ] **`FormatReplyTask`:** Assigned to Laura; synthesizes final conversational message

**Advanced Execution Flow**
- [ ] **Human handoff bypass:** Check `is_human_paused=True` in DB before `crew.kickoff()`; admin handles manually if true
- [ ] **Conversational logging:** Save user message + CrewAI output to MongoDB `Conversations` collection
- [ ] **Async logging:** Use task callbacks to decouple generation from HTTP response (maintain 200 OK rule)
- [ ] **Webhook pattern:** Acknowledge immediately, execute in background

### Phase 5: Testing & Quality Assurance

- [ ] Set up test databases (MongoDB, test LLM endpoints)
- [ ] Unit tests for custom agentic tools (Pydantic schema validation)
- [ ] Integration tests for Django API routes (webhook threading, CrewAI timeout handling)
- [ ] Run `python manage.py test` or `pytest`
- [ ] Verify agent execution, caching, memory in logs

---

## Key Files & Directories

| Path | Purpose |
|------|---------|
| `chatbot/views.py` | AI logic, caching, sanitization, guest firewall, async views |
| `chatbot/crew/` | CrewAI agents, intent router, fallback config |
| `whatsapp_integration/views.py` | Webhook endpoints, instant ack logic |
| `whatsapp_integration/message_handler.py` | Message parser, template router, button/list builder |
| `whatsapp_integration/services.py` | WhatsApp Cloud API request sender |
| `whatsapp_integration/management/commands/run_reservation_scheduler.py` | Background scheduler (credentials masked) |

---

## Workflow Development

When contributing to CrewAI workflows:

1. **Maintain Karen persona logic** when editing chatbot prompts.
2. **Follow DRF patterns** for new endpoints.
3. **Respect the English/Spanish split:** English for code logic, Spanish for user-facing content and comments.
4. **Type-hint and modularize** all new code.
5. **Test against the complete chain:** intent extraction → agent execution → WhatsApp delivery.
6. **Document non-obvious constraints** (e.g., Meta limits, retry logic, timeout thresholds).

---

## External References

- **Project Context:** See `GEMINI.md`
- **Architecture Roadmap:** See `.agent/workflows/crewai_architecture_migration.md`
- **Django Settings:** Check `settings.py` for LLM keys, MongoDB connection, WhatsApp config
- **Logging Config:** Ensure `LOG_LEVEL` is set appropriately; sensitive data must be masked

---

## Development Checklist

- [ ] All Python follows PEP 8 with type hints
- [ ] No raw `print()` statements; use logging module
- [ ] Sensitive credentials are masked in logs
- [ ] WhatsApp interactions respect 3-button limit (use lists for >3)
- [ ] MongoDB queries validate `ObjectId` before execution
- [ ] CrewAI tasks include timeout/retry handling
- [ ] Webhook endpoints acknowledge immediately; run AI in background threads
- [ ] Test coverage includes both unit and integration tests
- [ ] Karen persona is consistent in all user-facing content
