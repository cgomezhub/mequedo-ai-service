# Marketing AI Agents — Flow & Logic Context

> **Purpose of this file:** Capture the *why* behind the `marketing` app's AI logic — the
> end-to-end flow, the LLM strategy, the anti-hallucination guards, and the hard-won
> decisions/gotchas from the build session. This is context for future agents/devs so the
> reasoning isn't re-derived from scratch. The step-by-step *build plan* lives in
> `.agent/workflows/backend-marketing-workflow.md`; this file documents what was actually
> implemented and the lessons learned.

---

## 1. What the feature does

Turns a single Mequedo `TourismPackage` (or `Listing`) into a **human-reviewable, multi-channel
marketing draft**: Instagram caption + hashtags, YouTube title + description, an in-app
announcement (HTML), an image-overlay text, and a branded image composed from the package's
real Cloudinary photos.

**Phase 1 (current) = generate → reviewable `draft`.** No auto-posting; a human posts from the
Next.js admin. Publishing to Instagram/YouTube is deferred to Phase 2 (gated behind Meta App
Review).

---

## 2. End-to-end flow

```
Next.js admin
   │  POST /api/marketing/generate/async/   { sourceType, sourceId }   (X-Internal-Secret)
   ▼
GenerateContentAsyncView.post  (marketing/views.py)
   │  • validates secret + sourceType/sourceId
   │  • inserts MarketingContent doc  status="processing"
   │  • spawns daemon thread, returns 202 { contentId, status:"processing" }
   ▼
_run_marketing_in_background(contentId, sourceType, sourceId)   (background thread)
   │  1. MarketingCrew().kickoff via _kickoff_marketing_with_retry(...)
   │  2. parse the crew's JSON output
   │  3. fetch source facts ONCE (MarketingSourceTool.fetch_facts)
   │  4. overlay text  = _overlay_from_facts(facts)   (deterministic, never the LLM)
   │  5. warnings      = _assess_source_quality(facts)  (junk-source guard)
   │  6. composedImageUrl = CloudinaryImageComposer().compose(chosen_image_url, overlay)
   │  7. update_one  → status="draft" + all fields + dataQualityWarnings
   │     (on any exception → status="error")
   ▼
Next.js admin polls  GET /api/marketing/generate/status/?contentId=
   → GenerateContentStatusView returns the draft fields once status is draft/error
```

The async-thread + Mongo-status-polling shape is copied verbatim from Karen's chatbot
(`ChatbotAsyncView`/`ChatbotStatusView`/`_run_crew_in_background`) so we never block the HTTP
request on the LLM (Vercel ~30s gateway timeout).

---

## 3. The crew (`marketing/crew/`)

Two agents, two chained tasks, sequential — shaped like `MequedoCrew`.

| Component | File | Notes |
|---|---|---|
| `MarketingCrew` | `marketing_orchestrator.py` | builds agents+tasks; `setup_crew()` → `memory=False, cache=True`; `kickoff()` returns the final task's `json_dict` serialized |
| Copywriter ("Karen Marketing") | `marketing_agents.py:get_copywriter_agent` | `tools=[MarketingSourceTool()]`, `allow_delegation=False`, `max_iter=3`, `max_execution_time=90` |
| Brand/QA Editor | `marketing_agents.py:get_brand_qa_agent` | no tools; hallucination + brand-voice checker |
| Generate task | `marketing_tasks.py:get_generate_content_task` | Step 1 call source tool, Step 2 draft all fields in Venezuelan Spanish |
| QA task | `marketing_tasks.py:get_qa_marketing_task` | `context=[generate_task]`, `output_json=MarketingContentSchema` → forces clean JSON |
| Output schema | `marketing_schemas.py:MarketingContentSchema` | 7 fields: `instagram_caption, hashtags, youtube_title, youtube_description, announcement_html, image_overlay_text, chosen_image_url` |
| Source tool | `crew/tools/marketing_source_tool.py:MarketingSourceTool` | reads `TourismPackage`/`Listing` via shared `get_db()`; the crew's ONLY source of truth |

**`MarketingSourceTool`** has two entry points:
- `_run(source_type, source_id)` → the formatted "FACTUAL SOURCE RECORD" text the agent reads.
- `fetch_facts(source_type, source_id)` → the raw dict, used by the background worker for the
  deterministic overlay + the junk guard (so we don't trust the LLM for the price on the image).

---

## 4. LLM strategy — NVIDIA NIM only (this is the single most important decision)

Defined in `chatbot/crew/llm_config.py`:
- `get_marketing_llm()` → primary, `MARKETING_MODEL` (default `meta/llama-3.3-70b-instruct`)
- `get_marketing_fallback_llm()` → `MARKETING_FALLBACK_MODEL` (default `meta/llama-3.1-70b-instruct`)
- `_build_marketing_llm(model)` → `nvidia_nim/<model>`, `temperature=MARKETING_TEMPERATURE` (0.2)
- `_kickoff_marketing_with_retry` (`marketing/views.py`) → primary → fallback NVIDIA model on
  rate-limit/provider failure, with exponential backoff; logs each agent's active model.

### Why NOT Anthropic / OpenAI / Gemini
**Anthropic geo-blocks Venezuela.** The marketing crew was originally specced on Claude Opus 4.8.
Calls from a Venezuelan IP return `403 {'error': {'type': 'forbidden', 'message': 'Request not
allowed'}}`. The app server runs on a VE IP (it can't sit behind a US VPN because MongoDB Atlas
blocks the VPN exit IP). NVIDIA NIM is reachable from VE, free, and already proven on Railway, so
the marketing crew was switched to NVIDIA NIM. (See §6 for the geo-block diagnosis trail.)

---

## 5. Anti-hallucination grounding system

**The problem we hit:** for the "Barbacoas" package, the source tool returned *perfect* facts
(`Barbacoas / $40 / 2 días / real inclusions`), but the model still invented a **beach** and a
**wrong price**. Root causes: `temperature=0.7` (creative) + a **gibberish description** in the DB
(`"wjdjwjdj dwqd…"`) which the model "filled in" with tourism clichés; the QA agent (same model,
same temp) rubber-stamped it.

**The fix is four layers — keep all of them:**

1. **Low temperature** — `MARKETING_TEMPERATURE` default `0.2` (was 0.7). Biggest lever against
   fact-drift. Tone/warmth comes from the prompt, not temperature.
2. **Hardened prompts** (`marketing_agents.py` + `marketing_tasks.py`): forbid inventing
   geography/activities (playa, mar, montaña, río…), forbid changing the price, and — critically —
   "if the description is empty/noise, write a *generic* warm invitation; do NOT invent attractions."
3. **Stricter QA editor** — explicit price/destination/geography checks, not vague "don't hallucinate."
4. **Deterministic image overlay** — `_overlay_from_facts(facts)` builds the overlay text
   (`"Barbacoas · 2 días · $40/persona"`) straight from DB facts. **The LLM is never trusted for the
   price burned onto the graphic** — a wrong price on an image is the worst failure mode.

**Junk-source guard** (`marketing/views.py`):
- `_looks_like_junk_description(text)` — flags empty / <15 chars / vowel-starved (<20% vowels) /
  many vowel-less "words". Catches placeholder junk, passes real Spanish prose.
- `_assess_source_quality(facts)` — returns Spanish admin warnings for junk description + missing
  price + missing destination → persisted as `dataQualityWarnings` on the doc and returned by the
  status endpoint. **Non-blocking**: still produces a (now safe/generic) draft, but tells the admin
  to fix the source data rather than silently shipping vague content.

---

## 6. Hard-won gotchas (don't relearn these)

- **Anthropic = 403 from Venezuela.** Identical `403 "Request not allowed"` from "two providers" is
  the tell that the request never reached a model — it's a region gate, not a code bug. Retries
  can't fix a geo-block.
- **The NVIDIA model *list* lies.** `GET integrate.api.nvidia.com/v1/models` returns 121 models, but
  **many 404 on actual invocation** ("Function not found"). `deepseek-ai/deepseek-v3.2` /
  `deepseek-v4-pro` were never deployed → that was the chatbot deep-tier 404. **Always probe a
  candidate model with a real tool-call request before adopting it** (the copywriter needs
  tool-calling). Verified-good with tools: `meta/llama-3.3-70b-instruct`, `meta/llama-3.1-70b-instruct`,
  `mistralai/mistral-nemotron`, `nvidia/nemotron-3-super-120b-a12b`,
  `mistralai/mistral-large-3-675b-instruct-2512`.
- **CrewAI needs the `anthropic` SDK** for `anthropic/*` (native provider), not just litellm — moot
  now that we're on NVIDIA, but noted.
- **`claude-opus-4-8` rejects `temperature`** (400) — moot now, noted.
- **Stale process trap:** a long-running `runserver`/gunicorn worker does NOT pick up `.env` edits
  until fully restarted. "Works in a fresh CLI run, fails in the server" = stale env. Restart all
  workers after changing keys/models.
- **MongoDB Atlas blocks the VPN exit IP**, which is exactly why the app can't run behind the US VPN
  that would unblock Anthropic — the two constraints are mutually exclusive, which forced the NVIDIA
  decision. (To run diagnostics that touch Atlas, run them OFF the VPN.)
- **`imageSrc` is a real array** in `TourismPackage` (the raw-doc preview just renders the list's
  `str()`); the source tool iterates it correctly.

---

## 7. Data contract — `MarketingContent` (shared Mongo, camelCase, mirrored by Next.js Prisma)

`_id, sourceType ("package"|"listing"), sourceId, status ("processing"|"draft"|"approved"|
"published"|"error"), instagramCaption, hashtags[], youtubeTitle, youtubeDescription,
announcementHtml, imageOverlayText, composedImageUrl, dataQualityWarnings[], error,
scheduledAt (nullable, Phase 2), createdAt, updatedAt`

Status endpoint returns: `status, instagramCaption, hashtags, youtubeTitle, youtubeDescription,
announcementHtml, imageOverlayText, composedImageUrl, dataQualityWarnings, error`.

---

## 8. Images — `marketing/services.py`

- `CloudinaryImageComposer.compose(source_url, overlay_text)` — pure URL transformation (text +
  logo overlay) over an existing Cloudinary photo. No upload, no AI image generation. Returns
  `None` for non-Cloudinary URLs or when `CLOUDINARY_CLOUD_NAME` is unset.
- `InstagramService` — Phase-2-ready (mirrors `WhatsAppService`), **built but NOT called in Phase 1**.

---

## 9. Phase 2 seam (not active)

`marketing/management/commands/run_marketing_scheduler.py` is a documented stub. Phase 2 will poll
`ScheduledTask` for `type:"marketing_publish"` (driven by the `scheduledAt` field) and call
`InstagramService.create_media_container` → `publish_media`, then set `status="published"`. Model it
on `whatsapp_integration/.../run_reservation_scheduler.py` (mask credentials in logs).

---

## 10. Tests & verification

- `marketing/tests/` — 25 tests: source tool, Cloudinary composer, schema, async endpoints
  (202 / 403 / 400), background worker (draft + error), deterministic overlay, and the junk-source
  guard. Run: `venv/bin/python manage.py test marketing`.
- The grounding fix was validated by running the **real crew against the real Barbacoas facts**
  (DB stubbed because Atlas is geo-blocked from a VPN'd session): correct destination, correct $40,
  zero invented geography.

---

## 11. Relevant env vars

`NVIDIA_API_KEY` (shared with chatbot), `MARKETING_MODEL`, `MARKETING_FALLBACK_MODEL`,
`MARKETING_TEMPERATURE`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_LOGO_PUBLIC_ID`,
`INSTAGRAM_BUSINESS_ACCOUNT_ID` (Phase 2), `META_GRAPH_ACCESS_TOKEN` (or reuse
`WHATSAPP_ACCESS_TOKEN`), `DJANGO_SERVICE_SECRET`.
