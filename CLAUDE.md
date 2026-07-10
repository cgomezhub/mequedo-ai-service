# Mequedo AI Service: Developer Guide

**Project:** Django-based AI service for Mequedo (accommodation platform in Venezuela)  
**Core Product:** Karen chatbot for searching listings, integrated with WhatsApp  
**Current Status:** Transitioning from deterministic pipeline to CrewAI multi-agent architecture

---

## Quick Start

- **Framework:** Django + Django Rest Framework (DRF)
- **AI Orchestration:** CrewAI (multi-agent system)
- **LLMs:** OpenAI, NVIDIA AI Endpoints (Llama 3), Google Gemini; **Claude Opus 4.8 (Anthropic, marketing crew only)**
- **Database:** MongoDB (listings, locations, tasks, marketing content) + SQLite (Django)
- **Key Integration:** WhatsApp Cloud API; Meta Graph / Instagram API (Phase 2), Cloudinary (image composition)

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

- **Chatbot fallback chain:** NVIDIA NIM (primary) → Gemini (fallback) → OpenAI (secondary)
- **Marketing crew:** NVIDIA NIM only — primary `MARKETING_MODEL` (default `meta/llama-3.3-70b-instruct`) via `get_marketing_llm()`, fallback `MARKETING_FALLBACK_MODEL` (default `meta/llama-3.1-70b-instruct`) via `get_marketing_fallback_llm()`. **Anthropic/OpenAI/Gemini are intentionally NOT used for marketing:** Anthropic geo-blocks Venezuela (403 "Request not allowed") and the server runs on a VE IP. The copywriter agent has **no tools** (the source facts are fetched in `views.py` and injected into its task as `{source_facts}`), so marketing models no longer need tool-calling support — but verify new model IDs against `GET integrate.api.nvidia.com/v1/models` *and* a real invocation probe, since the catalog over-reports (many listed IDs 404 on invocation).
- **Robust execution:** Use `_kickoff_with_retry` wrapper for CrewAI tasks (includes provider switching, exponential backoff). Marketing uses `_kickoff_marketing_with_retry` (primary NVIDIA model → different NVIDIA fallback model); it retries on rate-limit/provider-failure, **on task timeout** (a slow 70B pass switches to the fallback model), **and on empty generation** — NIM free-tier models occasionally return the JSON skeleton with every text field `""` (hashtags/URL filled but `instagram_caption` blank); `_generation_is_empty` treats blank-caption or non-JSON output as a failed attempt so a blank `draft` is never persisted. Per-agent budget is `MARKETING_TASK_TIMEOUT` (default `180`s) — the crew runs in a background thread, so it is **not** bound by the ~30s Vercel gateway timeout.
- **Rate-limit/stall storm hardening (marketing):** NVIDIA NIM free tier is **per-minute** (a single probe call can `200` while a full crew burst `429`s), and free-tier model endpoints can **stall outright** (observed: `llama-3.3-70b` >90s for a small completion while `llama-3.1-70b` answered in ~6s). Stacked retry layers (litellm/SDK + CrewAI agent `max_retry_limit` + `_kickoff_marketing_with_retry`) once amplified a transient failure into a multi-minute hang that left the doc stuck at `status="processing"` (CrewAI's `max_execution_time` can't interrupt a blocking SDK retry-sleep). Mitigations — **only the crew-level wrapper retries; every inner layer fails fast**: per-call `timeout=MARKETING_LLM_TIMEOUT` (default `30`s), `num_retries=MARKETING_LLM_NUM_RETRIES` (default `0`), agent `max_retry_limit=0` — but **do not trust these SDK knobs**: verified empirically that they don't reliably reach the HTTP layer (a stalled call blocked ~300s and was retried by the OpenAI client despite `timeout=30, num_retries=0`). The enforced ceilings are thread-join based: each kickoff attempt is capped at `MARKETING_ATTEMPT_TIMEOUT` (default `75`s) inside `_kickoff_marketing_with_retry` — on timeout the crew is **rebuilt** (never share Agent/Task objects with the abandoned zombie thread) and the fallback model takes over — the wrapper backs off `MARKETING_RATE_LIMIT_BACKOFF` (default `30`s) on a real 429, and `_run_with_hard_timeout` caps the whole job at `MARKETING_JOB_TIMEOUT` (default `240`s) so it **always** reaches `draft`/`error`. The marketing views set `throttle_classes = []` (internal, `X-Internal-Secret`-guarded) so the poller isn't masked by DRF's `anon: 10/min` throttle. See `.agent/agent-logic-context/markenting_AIagents_flow_context.md` §12.

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

## Feature: Marketing Content Generation (`marketing` app)

A dedicated CrewAI pipeline that turns a single Mequedo `TourismPackage` or `Listing` into a reviewable, multi-channel marketing draft (Instagram caption + hashtags, YouTube title/description, in-app announcement text, and a branded image composed from real Cloudinary photos).

- **Phase 1 (current) = generate → reviewable `draft`.** No auto-posting. A human reviews/edits/posts from the Next.js admin. Publishing to IG/YouTube is **deferred to Phase 2** (gated behind Meta App Review).
- **LLM:** NVIDIA NIM only (see LLM Orchestration above) — Anthropic is geo-blocked from Venezuela.
- **Storage:** `MarketingContent` collection in the shared MongoDB (same `DATABASE_URL`). **Field names are camelCase and must stay identical to the Next.js Prisma model** so both sides read/write the same documents.
- **Grounding:** All facts come from `MarketingSourceTool` (the crew's only source of truth). Never fabricate price, dates, inclusions, or amenities; omit missing fields.
- **Images:** Composed from existing Cloudinary photos via URL transformations only — **never generate synthetic property images**, no video.
- **Async pattern:** Mirrors `ChatbotAsyncView`/`ChatbotStatusView` — `X-Internal-Secret` guard, insert `processing` doc, run crew on a daemon thread (wrapped in `_run_with_hard_timeout` so it can never hang on `processing`), poll for `draft`/`error`. The marketing views are exempt from the public anon throttle (`throttle_classes = []`).

**Endpoints (internal, `X-Internal-Secret: $DJANGO_SERVICE_SECRET`):**
- `POST /api/marketing/generate/async/` — body `{ sourceType, sourceId }` → `202 { contentId, status }`
- `GET /api/marketing/generate/status/?contentId=` → `{ status, instagramCaption, hashtags, youtubeTitle, youtubeDescription, announcementHtml, composedImageUrl, dataQualityWarnings }`

**`announcementHtml` is plain text, not HTML.** The field name stays `announcementHtml` (camelCase data contract, must match the Next.js Prisma model), but its value is a clean string — the Next.js frontend wraps/renders its own tag elements. Prompts ask for plain text and the background worker strips any stray tags via `_strip_html()` as a defensive guarantee.

**Grounding & guards (anti-hallucination):** marketing LLM runs at low temperature (`MARKETING_TEMPERATURE`, default `0.2`); prompts forbid inventing geography/activities or altering the price. The **image overlay text is built deterministically from DB facts** (never the LLM) so a wrong price is never burned onto the graphic, and the **source photo is selected deterministically from DB facts** via `_select_image_url` (the LLM's `chosen_image_url` is only honored on an exact match, else falls back to the first real image) — an invented Cloudinary `public_id` would otherwise ship a 404 image URL to Next.js. A **junk-source guard** (`_assess_source_quality` / `_looks_like_junk_description`) flags empty/gibberish descriptions and missing price/destination into `dataQualityWarnings` so the admin is told to fix the source data instead of trusting a vague auto-draft.

**Required env:** `NVIDIA_API_KEY` (shared with the chatbot), `MARKETING_MODEL`, `MARKETING_FALLBACK_MODEL`, `MARKETING_TEMPERATURE`, `MARKETING_TASK_TIMEOUT`, `MARKETING_LLM_TIMEOUT`, `MARKETING_LLM_NUM_RETRIES`, `MARKETING_RATE_LIMIT_BACKOFF`, `MARKETING_JOB_TIMEOUT`, `INSTAGRAM_BUSINESS_ACCOUNT_ID` (Phase 2), `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_LOGO_PUBLIC_ID`; reuses `WHATSAPP_ACCESS_TOKEN` (or `META_GRAPH_ACCESS_TOKEN`) and `DJANGO_SERVICE_SECRET`.

**Phase 2 seam (not yet active):** `InstagramService` (built, uncalled), the `scheduledAt` field, and the `run_marketing_scheduler` management-command stub (will poll `ScheduledTask` for `type: "marketing_publish"` → `InstagramService.publish_media`).

---

## Key Files & Directories

| Path | Purpose |
|------|---------|
| `chatbot/views.py` | AI logic, caching, sanitization, guest firewall, async views |
| `chatbot/crew/` | CrewAI agents, intent router, fallback config |
| `chatbot/crew/llm_config.py` | LLM accessors incl. `get_marketing_llm()` (Claude Opus 4.8) |
| `whatsapp_integration/views.py` | Webhook endpoints, instant ack logic |
| `whatsapp_integration/message_handler.py` | Message parser, template router, button/list builder |
| `whatsapp_integration/services.py` | WhatsApp Cloud API request sender |
| `whatsapp_integration/management/commands/run_reservation_scheduler.py` | Background scheduler (credentials masked) |
| `marketing/views.py` | Marketing async generate + status views, background worker, retry wrapper |
| `marketing/services.py` | `CloudinaryImageComposer` (URL transforms), `InstagramService` (Phase 2) |
| `marketing/crew/` | Marketing crew: schemas, `MarketingSourceTool`, agents, tasks, orchestrator |
| `marketing/management/commands/run_marketing_scheduler.py` | Phase 2 publish scheduler (stub) |

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
- **Marketing Backend Workflow:** See `.agent/workflows/backend-marketing-workflow.md`
- **Marketing AI Logic & Decisions:** See `.agent/agent-logic-context/markenting_AIagents_flow_context.md` (flow, LLM strategy, anti-hallucination guards, gotchas)
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
