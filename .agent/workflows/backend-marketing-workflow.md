---
description: Build the Marketing Content Generation engine inside Karen (CrewAI + Claude + Meta/Cloudinary) — backend half of the Mequedo Growth feature
---

# Marketing Content Generation — Backend Workflow (Karen AI Service)

> **Contextual Agent Protocol**
>
> - **Identity:** You are a **Senior AI Agent Engineer** specializing in CrewAI, LangChain/litellm, Django, and the Meta Graph API.
> - **Purpose:** Add a **marketing content generation pipeline** to the existing Karen service that turns a single Mequedo `TourismPackage` (or `Listing`) into a post-ready, human-reviewable draft: Instagram caption + hashtags, YouTube title + description, an in-app announcement, and a branded still image composed from the package's real photos.
> - **Process:** Reuse Karen's proven patterns verbatim — the async-thread + Mongo-status job model (`ChatbotAsyncView`/`ChatbotStatusView`), the `MequedoCrew` orchestrator shape, the `X-Internal-Secret` guard, the `WhatsAppService` Graph API client, and the `ScheduledTask` scheduler. Do **not** invent new infrastructure.
> - **Constraints:** Generation is automated; **publishing to Instagram/YouTube is deferred to Phase 2** (gated behind Meta App Review). Phase 1 ends at a reviewable draft. Never generate synthetic property images — compose from existing Cloudinary photos only.
> - **Objective:** A fault-tolerant `marketing` Django app exposing async generate + status endpoints, writing `MarketingContent` documents to the shared MongoDB that the Next.js admin reviews, edits, and posts.

> **Cognitive Framework**
>
> 1. **Identify and Analyze:** Source data is **structured** (`TourismPackage`, `Listing`, `TourismOperatorProfile`, departures) read via `get_db()`. This is structured-data-grounded generation, not document RAG.
> 2. **Extract Key Principles:** AIDA copywriting, brand consistency, Venezuelan Spanish, factual grounding (never invent price, dates, inclusions, or amenities not in the DB record).
> 3. **Ensure Consistency:** All facts must come from the Mongo record. If a field is missing, omit it — never fabricate.
> 4. **Edge Cases:** LLM/provider failure (fallback chain), missing images (skip image composition, still return text), oversized captions (IG 2200-char limit), missing operator phone.
> 5. **Utilize Provided Data Exclusively:** The crew's only source of truth is the `MarketingSourceTool` output.

---

## Decisions locked (do not re-litigate)

- **Phase 1 = generate → reviewable draft.** No auto-posting to IG/YouTube yet. Human posts from the Next.js admin.
- **Storage = new `MarketingContent` Mongo collection** in the shared DB (same `DATABASE_URL` Karen already uses).
- **Marketing LLM = Claude Opus 4.8** (`anthropic/claude-opus-4-8`) via litellm, for the marketing crew **only**. Karen's chatbot crew stays on NVIDIA/Gemini.
- **Images = composed from real Cloudinary photos** via URL transformations (text/price/logo overlay). No AI image generation, no video.

---

## Phase 1: LLM & Environment Setup

1. **Add Claude to `chatbot/crew/llm_config.py`**
   - [ ] Add a `get_marketing_llm()` returning `LLM(model="anthropic/claude-opus-4-8", api_key=os.getenv("ANTHROPIC_API_KEY"), temperature=0.7, max_tokens=2000, timeout=60)`. litellm (already a dependency) routes `anthropic/*` natively — no new SDK.
   - [ ] Keep the existing NVIDIA→Gemini→OpenAI tiering untouched; marketing is a separate, dedicated accessor.
   - [ ] Pin `litellm` in `requirements.txt` if it isn't already (the Anthropic REST call is made through litellm; a standalone `anthropic` package is not required).

2. **Environment variables (`.env`)**
   - [ ] `ANTHROPIC_API_KEY` — for the marketing crew.
   - [ ] `INSTAGRAM_BUSINESS_ACCOUNT_ID` — the IG Business account ID linked to the Meta Business Suite Page (fetch via `GET /{page-id}?fields=instagram_business_account` on the Graph API; Phase 2 needs it, set it now).
   - [ ] Reuse `WHATSAPP_ACCESS_TOKEN` (same Meta app) or introduce `META_GRAPH_ACCESS_TOKEN` if you separate tokens. Reuse `DJANGO_SERVICE_SECRET` for the internal auth guard.
   - [ ] `CLOUDINARY_CLOUD_NAME` — for building transformation URLs (no SDK needed; URL-based).

## Phase 2: The `marketing` Django App

1. **Scaffold** (`python manage.py startapp marketing`), mirroring `whatsapp_integration/`'s shape.
   - [ ] Register in `INSTALLED_APPS`.
   - [ ] Add `path('api/marketing/', include('marketing.urls'))` to `mequedo_ai/urls.py`.

2. **`marketing/services.py`**
   - [ ] **`CloudinaryImageComposer`** — given a source Cloudinary URL + overlay text (e.g. price/destination) + brand logo, return a transformed delivery URL (text + logo overlay via Cloudinary `l_text:`/`l_<logo>` transformations). Pure string building; no upload, no AI.
   - [ ] **`InstagramService`** (Phase 2-ready, built now, **not called in Phase 1**) — mirror `WhatsAppService`: base `https://graph.facebook.com/v24.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}`, Bearer token, `requests.post`. Methods: `create_media_container(image_url, caption)` → `POST /media` (returns `creation_id`); `publish_media(creation_id)` → `POST /media_publish`. Same try/except/logging style as `WhatsAppService`.

3. **`MarketingContent` collection contract** (write via `get_db().get_collection("MarketingContent")`)
   - [ ] Fields: `_id`, `sourceType` (`"package" | "listing"`), `sourceId`, `status` (`"processing" | "draft" | "approved" | "published" | "error"`), `instagramCaption`, `hashtags` (array), `youtubeTitle`, `youtubeDescription`, `announcementHtml`, `imageOverlayText`, `composedImageUrl`, `error`, `createdAt`, `updatedAt`, `scheduledAt` (nullable, Phase 2).
   - [ ] **Keep field names identical** to the Prisma `MarketingContent` model the Next.js repo will add (camelCase), so both sides read/write the same documents.

## Phase 3: The Marketing Crew (`marketing/crew/`)

Mirror `chatbot/crew/` structure (`agents.py`, `tasks.py`, `schemas.py`, `orchestrator.py`, `tools/`).

1. **`marketing/crew/marketing_schemas.py`**
   - [ ] Pydantic `MarketingContentSchema`: `instagram_caption: str`, `hashtags: list[str]`, `youtube_title: str`, `youtube_description: str`, `announcement_html: str`, `image_overlay_text: str`, `chosen_image_url: str`. Used as `output_json` on the final task (same pattern as `IntentSchema`).

2. **`marketing/crew/tools/marketing_source_tool.py`**
   - [ ] `MarketingSourceTool(BaseTool)` reusing `get_db()` from `chatbot.crew.tools.search_accommodation`. Args: `source_type`, `source_id`. Reads `TourismPackage` (title, description, destination, pricePerPerson, durationDays, inclusions, exclusions, imageSrc[]) joined with `TourismOperatorProfile`; or `Listing` equivalent. Returns a clean factual dict — the crew's only source of truth.

3. **`marketing/crew/marketing_agents.py`** (both on `get_marketing_llm()`)
   - [ ] **Copywriter (Karen Marketing)** — role: Venezuelan tourism copywriter. Goal: AIDA captions + hashtags + YT metadata + announcement HTML, **exclusively in Spanish**, grounded in `MarketingSourceTool`. `allow_delegation=False`, `max_iter=3`, `max_execution_time=90`, tools `[MarketingSourceTool()]`.
   - [ ] **Brand/QA Editor** — role: hallucination + brand-voice checker. Rejects invented amenities/prices, enforces IG 2200-char limit and hashtag count (≤30), confirms image overlay text matches a real price/destination. `allow_delegation=False`.

4. **`marketing/crew/marketing_tasks.py`**
   - [ ] `get_generate_content_task(copywriter)` — input `{source_type}`, `{source_id}`; calls the source tool, drafts all channel fields.
   - [ ] `get_qa_marketing_task(editor)` — `context=[generate_task]`, `output_json=MarketingContentSchema`. Final structured output.

5. **`marketing/crew/marketing_orchestrator.py`**
   - [ ] `MarketingCrew` class shaped like `MequedoCrew`: builds agents + chained tasks, `setup_crew()` (`memory=False`, `cache=True`, `verbose=True`), `kickoff(inputs)` returning the validated `MarketingContentSchema` JSON.

## Phase 4: Async Endpoints (mirror `chatbot/views.py`)

1. **`marketing/views.py`**
   - [ ] **`GenerateContentAsyncView(POST /api/marketing/generate/async/)`** — `X-Internal-Secret` guard (copy from `ChatbotAsyncView`). Body: `{ sourceType, sourceId }`. Insert a `MarketingContent` doc `status="processing"`, dispatch `_run_marketing_in_background(content_id, source_type, source_id)` on a `daemon` thread, return `202 { contentId, status: "processing" }`.
   - [ ] **`GenerateContentStatusView(GET /api/marketing/generate/status/?contentId=)`** — copy `ChatbotStatusView`. Return `status` + the draft fields when `draft`/`error`.
   - [ ] **`_run_marketing_in_background(...)`** — copy the structure of `_run_crew_in_background`: run `MarketingCrew().kickoff(...)` via a `_kickoff_with_retry`-style wrapper (Claude primary → `get_deep_llm()` fallback), compose the image via `CloudinaryImageComposer`, then `update_one` the doc to `status="draft"` with all fields; on exception set `status="error"`.

2. **`marketing/urls.py`** — wire the two views.

## Phase 5: Scheduling Hook (Phase-2 stub, build the seam now)

- [ ] Note in code where a future `run_marketing_scheduler` management command (modeled on `run_reservation_scheduler.py`) will poll `ScheduledTask` for `type: "marketing_publish"` and call `InstagramService.publish_media`. Do not build the publish trigger in Phase 1 — just leave the `scheduledAt` field and a TODO.

## Phase 6: Testing & Quality Assurance (MANDATORY)

1. **Test Environment Preparation**
   - [ ] Identify external dependencies (MongoDB, litellm/Anthropic, Cloudinary URL builder, Meta Graph API) and mock them, following existing Karen test patterns.

2. **Automated Test Creation**
   - [ ] Unit-test `MarketingSourceTool` (Pydantic args validate; factual dict shape) with a mocked `get_db()`.
   - [ ] Unit-test `CloudinaryImageComposer` (correct transformation URL given inputs).
   - [ ] Integration-test the async endpoints: 202 + `contentId` on success, 403 without `X-Internal-Secret`, 400 on missing `sourceId`, background thread writes a `draft` doc (mock the crew).
   - [ ] Assert the crew output validates against `MarketingContentSchema` and never exceeds IG limits.

3. **Verification & Validation**
   - [ ] Run `python manage.py test` (or `pytest`).
   - [ ] Manually invoke `/api/marketing/generate/async/` for one real package id; poll status; inspect the `MarketingContent` draft + composed image URL.

---

## Integration contract (shared with the Next.js `frontend-marketing-workflow.md`)

| Direction | Endpoint | Auth | Payload / Response |
|---|---|---|---|
| Next.js → Karen | `POST /api/marketing/generate/async/` | `X-Internal-Secret: $DJANGO_SERVICE_SECRET` | `{ sourceType, sourceId }` → `202 { contentId, status }` |
| Next.js → Karen | `GET /api/marketing/generate/status/?contentId=` | (internal) | `{ status, instagramCaption, hashtags, youtubeTitle, youtubeDescription, announcementHtml, composedImageUrl }` |
| Karen → Mongo | `MarketingContent` collection | — | camelCase fields, mirrored by the Prisma model on the Next.js side |
| (Phase 2) Next.js → Karen | `POST /api/marketing/publish/` | `X-Internal-Secret` | `{ contentId }` → triggers `InstagramService` |
