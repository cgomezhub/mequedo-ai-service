# Marketing AI Agents — Flow & Logic Context

> **Purpose of this file:** Capture the _why_ behind the `marketing` app's AI logic — the
> end-to-end flow, the LLM strategy, the anti-hallucination guards, and the hard-won
> decisions/gotchas from the build session. This is context for future agents/devs so the
> reasoning isn't re-derived from scratch. The step-by-step _build plan_ lives in
> `.agent/workflows/backend-marketing-workflow.md`; this file documents what was actually
> implemented and the lessons learned.

---

## 1. What the feature does

Turns a single Mequedo `TourismPackage` (or `Listing`) into a **human-reviewable, multi-channel
marketing draft**: Instagram caption + hashtags, YouTube title + description, an in-app
announcement (plain text — see §7), an image-overlay text, and a branded image composed from the
package's real Cloudinary photos.

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
   │  1. MarketingCrew().kickoff via _kickoff_marketing_with_retry(...),
   │     wrapped in _run_with_hard_timeout(..., MARKETING_JOB_TIMEOUT)  (see §12)
   │  2. parse the crew's JSON output
   │  3. fetch source facts ONCE (MarketingSourceTool.fetch_facts)
   │  4. overlay text  = _overlay_from_facts(facts)   (deterministic, never the LLM)
   │  4b. image_url    = _select_image_url(chosen_image_url, facts)  (DB image, not the LLM's)
   │  5. warnings      = _assess_source_quality(facts)  (junk-source guard)
   │  6. composedImageUrl = CloudinaryImageComposer().compose(image_url, overlay)
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

| Component                      | File                                                      | Notes                                                                                                                                |
| ------------------------------ | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `MarketingCrew`                | `marketing_orchestrator.py`                               | builds agents+tasks; `setup_crew()` → `memory=False, cache=True`; `kickoff()` returns the final task's `json_dict` serialized        |
| Copywriter ("Karen Marketing") | `marketing_agents.py:get_copywriter_agent`                | `tools=[MarketingSourceTool()]`, `allow_delegation=False`, `max_iter=3`, `max_execution_time=MARKETING_TASK_TIMEOUT` (default 180s)  |
| Brand/QA Editor                | `marketing_agents.py:get_brand_qa_agent`                  | no tools; hallucination + brand-voice checker                                                                                        |
| Generate task                  | `marketing_tasks.py:get_generate_content_task`            | Step 1 call source tool, Step 2 draft all fields in Venezuelan Spanish                                                               |
| QA task                        | `marketing_tasks.py:get_qa_marketing_task`                | `context=[generate_task]`, `output_json=MarketingContentSchema` → forces clean JSON                                                  |
| Output schema                  | `marketing_schemas.py:MarketingContentSchema`             | 7 fields: `instagram_caption, hashtags, youtube_title, youtube_description, announcement_html (plain text — see §7), image_overlay_text, chosen_image_url` |
| Source tool                    | `crew/tools/marketing_source_tool.py:MarketingSourceTool` | reads `TourismPackage`/`Listing` via shared `get_db()`; the crew's ONLY source of truth                                              |

**`MarketingSourceTool`** has two entry points:

- `_run(source_type, source_id)` → the formatted "FACTUAL SOURCE RECORD" text the agent reads.
- `fetch_facts(source_type, source_id)` → the raw dict, used by the background worker for the
  deterministic overlay + the junk guard (so we don't trust the LLM for the price on the image).

---

## 4. LLM strategy — NVIDIA NIM only (this is the single most important decision)

Defined in `chatbot/crew/llm_config.py`:

- `get_marketing_llm()` → primary, `MARKETING_MODEL` (default `meta/llama-3.3-70b-instruct`)
- `get_marketing_fallback_llm()` → `MARKETING_FALLBACK_MODEL` (default `meta/llama-3.1-70b-instruct`)
- `_build_marketing_llm(model)` → `nvidia_nim/<model>`, `temperature=MARKETING_TEMPERATURE` (0.2),
  `num_retries=MARKETING_LLM_NUM_RETRIES` (default 1 — keep the litellm/SDK retry layer SHALLOW; see §12)
- `_kickoff_marketing_with_retry` (`marketing/views.py`) → primary → fallback NVIDIA model on
  rate-limit/provider failure **or task timeout**; logs each agent's active model. Backoff is
  `MARKETING_RATE_LIMIT_BACKOFF` (default 30s) on a real 429 — the free tier is **per-minute**, so a
  1–2s backoff just re-trips the window — and quick `2**attempt` for other failures. Per-agent budget
  is `MARKETING_TASK_TIMEOUT` (default 180s); the crew runs in a background thread so it is NOT bound
  by the ~30s Vercel gateway timeout — 90s was too tight for a 70B pass under load. The whole job is
  additionally capped by `_run_with_hard_timeout` / `MARKETING_JOB_TIMEOUT` (default 240s) so it can
  never hang on `processing` (see §12).

### Why NOT Anthropic / OpenAI / Gemini

**Anthropic geo-blocks Venezuela.** The marketing crew was originally specced on Claude Opus 4.8.
Calls from a Venezuelan IP return `403 {'error': {'type': 'forbidden', 'message': 'Request not
allowed'}}`. The app server runs on a VE IP (it can't sit behind a US VPN because MongoDB Atlas
blocks the VPN exit IP). NVIDIA NIM is reachable from VE, free, and already proven on Railway, so
the marketing crew was switched to NVIDIA NIM. (See §6 for the geo-block diagnosis trail.)

---

## 5. Anti-hallucination grounding system

**The problem we hit:** for the "Barbacoas" package, the source tool returned _perfect_ facts
(`Barbacoas / $40 / 2 días / real inclusions`), but the model still invented a **beach** and a
**wrong price**. Root causes: `temperature=0.7` (creative) + a **gibberish description** in the DB
(`"wjdjwjdj dwqd…"`) which the model "filled in" with tourism clichés; the QA agent (same model,
same temp) rubber-stamped it.

**The fix is five layers — keep all of them:**

1. **Low temperature** — `MARKETING_TEMPERATURE` default `0.2` (was 0.7). Biggest lever against
   fact-drift. Tone/warmth comes from the prompt, not temperature.
2. **Hardened prompts** (`marketing_agents.py` + `marketing_tasks.py`): forbid inventing
   geography/activities (playa, mar, montaña, río…), forbid changing the price, and — critically —
   "if the description is empty/noise, write a _generic_ warm invitation; do NOT invent attractions."
3. **Stricter QA editor** — explicit price/destination/geography checks, not vague "don't hallucinate."
4. **Deterministic image overlay** — `_overlay_from_facts(facts)` builds the overlay text
   (`"Barbacoas · 2 días · $40/persona"`) straight from DB facts. **The LLM is never trusted for the
   price burned onto the graphic** — a wrong price on an image is the worst failure mode.
5. **Deterministic image SELECTION** — `_select_image_url(chosen_image_url, facts)` picks the photo
   to compose over from `facts["images"]`, NOT from the LLM. The crew's `chosen_image_url` is only
   honoured when it is an EXACT match for a real source image; otherwise it falls back to
   `facts["images"][0]`. A Cloudinary `public_id` is a random string the model silently invents
   (observed: real `jm9z…` → non-existent `is6b…` → a 404 image URL shipped to Next.js). This was the
   last LLM-trusted field that could produce a broken artifact; treat it like the price.

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
- **The NVIDIA model _list_ lies.** `GET integrate.api.nvidia.com/v1/models` returns 121 models, but
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
- **90s task timeout was too tight.** A 70B NVIDIA NIM generate pass (tool call + ~2500 chars of
  Spanish) overran `max_execution_time=90` under load. The budget is now `MARKETING_TASK_TIMEOUT`
  (default 180s) and a timeout is retryable in `_kickoff_marketing_with_retry` (it was previously
  NOT in the signature list, so a timeout re-raised immediately → `status="error"` without even
  trying the fallback model). Safe to raise because the crew runs in a background thread, not the
  HTTP request path.
- **Retry storm → stuck on `processing` (see §12).** A burst rate-limit (NVIDIA free tier is
  per-minute, not just a total quota — a single probe call can return 200 while a full crew burst
  429s) was amplified by THREE stacked retry layers (litellm/SDK + CrewAI ReAct loop +
  `_kickoff_marketing_with_retry`) into a multi-minute hang. `max_execution_time` does NOT save you:
  it is checked between iterations, not during a blocking SDK retry-sleep. The job sat at
  `status="processing"` until the Next.js poller gave up (and DRF's `anon: 10/min` throttle 429'd the
  `/status/` polls — a symptom, not the cause). 100+ `/chat/completions` requests came from the
  stacked retries, NOT from the `inputs` to `_kickoff_marketing_with_retry`.
- **Listing `destination` needs ObjectId coercion.** `Listing.locationId` may be stored as a string
  while `Location._id` is an ObjectId; the lookup in `_fetch_listing` now coerces (guarded) like the
  package operator lookup. Previously a string id silently returned `None` destination — which both
  produced an empty image overlay/quality warning AND lengthened the ReAct loop (the prompts demand a
  destination), pushing listing runs into the rate-limit storm faster than packages.

---

## 7. Data contract — `MarketingContent` (shared Mongo, camelCase, mirrored by Next.js Prisma)

`_id, sourceType ("package"|"listing"), sourceId, status ("processing"|"draft"|"approved"|
"published"|"error"), instagramCaption, hashtags[], youtubeTitle, youtubeDescription,
announcementHtml, imageOverlayText, composedImageUrl, dataQualityWarnings[], error,
scheduledAt (nullable, Phase 2), createdAt, updatedAt`

**`announcementHtml` holds PLAIN TEXT, not HTML.** The field name is kept (camelCase contract,
must match the Next.js Prisma model) but the Next.js frontend manages its own tag elements, so it
expects a clean string. The crew is prompted for plain text and the worker strips any stray tags
via `_strip_html()` (regex tag removal + `html.unescape`) before persisting — defensive, since the
LLM can ignore the prompt.

Status endpoint returns: `status, instagramCaption, hashtags, youtubeTitle, youtubeDescription,
announcementHtml, imageOverlayText, composedImageUrl, dataQualityWarnings, error`.

---

## 8. Images — `marketing/services.py`

- `CloudinaryImageComposer.compose(source_url, overlay_text)` — pure URL transformation (text +
  logo overlay) over an existing Cloudinary photo. No upload, no AI image generation. Returns
  `None` for non-Cloudinary URLs or when `CLOUDINARY_CLOUD_NAME` is unset.
- **Single-cloud assumption:** the source photo, the logo (`CLOUDINARY_LOGO_PUBLIC_ID`), and the
  output all live in ONE cloud (`CLOUDINARY_CLOUD_NAME`) — an `l_logo` overlay must be in the same
  cloud as the base image, so they cannot be mixed in one URL. `CLOUDINARY_CLOUD_NAME` must be the
  cloud that actually hosts the listing photos (the cloud segment after `res.cloudinary.com/` in a
  real `imageSrc`), and the logo must be uploaded there too. A cloud mismatch → `404 Resource not
  found` (a transformation URL only fails on a missing *piece*; probe each via the `x-cld-error`
  response header).
- `compose()` is fed a **DB-validated** image URL via `_select_image_url` (see §5 layer 5), never the
  raw LLM `chosen_image_url` — an invented `public_id` would otherwise ship a 404 URL to the frontend.
- `InstagramService` — Phase-2-ready (mirrors `WhatsAppService`), **built but NOT called in Phase 1**.

---

## 9. Phase 2 seam (not active)

`marketing/management/commands/run_marketing_scheduler.py` is a documented stub. Phase 2 will poll
`ScheduledTask` for `type:"marketing_publish"` (driven by the `scheduledAt` field) and call
`InstagramService.create_media_container` → `publish_media`, then set `status="published"`. Model it
on `whatsapp_integration/.../run_reservation_scheduler.py` (mask credentials in logs).

---

## 10. Tests & verification

- `marketing/tests/` — 26 tests: source tool, Cloudinary composer, schema, async endpoints
  (202 / 403 / 400), background worker (draft + error), deterministic overlay, deterministic image
  selection (incl. the hallucinated-URL fallback), and the junk-source guard. Run:
  `venv/bin/python manage.py test marketing`.
- The grounding fix was validated by running the **real crew against the real Barbacoas facts**
  (DB stubbed because Atlas is geo-blocked from a VPN'd session): correct destination, correct $40,
  zero invented geography.

---

## 11. Relevant env vars

`NVIDIA_API_KEY` (shared with chatbot), `MARKETING_MODEL`, `MARKETING_FALLBACK_MODEL`,
`MARKETING_TEMPERATURE`, `MARKETING_TASK_TIMEOUT` (per-agent budget, default 180s),
`MARKETING_LLM_NUM_RETRIES` (litellm/SDK retry depth, default 1),
`MARKETING_RATE_LIMIT_BACKOFF` (seconds to wait after a 429 before re-kickoff, default 30),
`MARKETING_JOB_TIMEOUT` (hard wall-clock cap for the whole background job, default 240s),
`CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_LOGO_PUBLIC_ID`,
`INSTAGRAM_BUSINESS_ACCOUNT_ID` (Phase 2), `META_GRAPH_ACCESS_TOKEN` (or reuse
`WHATSAPP_ACCESS_TOKEN`), `DJANGO_SERVICE_SECRET`.

---

## 12. Rate-limit retry storm → "stuck on processing" (resilience hardening)

**Symptom:** generation never finished. The doc sat at `status="processing"` forever (never
`error`), the Next.js admin polled `/status/` 100+ times and gave up, and the server logged 100+
`/chat/completions` requests plus a DRF `429` on `/status/`. Reproduced with BOTH `package` and
`listing` — so it is environmental, not data-shaped.

**Root cause — a transient rate limit amplified into a multi-minute hang:**

1. **Trigger.** NVIDIA NIM free tier is **per-minute / concurrency** limited, not just a total
   quota. A single probe call returns `200`, but a full crew run is a *burst* (tool call + ReAct
   iterations × 2 agents) that trips a `429`.
2. **Amplifier — three stacked retry layers**, all re-hitting the same limited endpoint:
   (a) the litellm/OpenAI-SDK auto-retry (the `_base_client … Retrying request to /chat/completions`
   log line); (b) the CrewAI ReAct loop (`max_iter=3` × 2 agents, re-prompting on malformed output);
   (c) `_kickoff_marketing_with_retry` re-running the whole crew. Multiplied → 100+ calls.
3. **Hang.** The SDK retry backoff sleeps **inside a single blocking call**, which CrewAI's
   `max_execution_time` cannot interrupt (it is checked *between* iterations). So the job never
   failed fast and never reached a terminal state.
4. **Symptom 429 (red herring).** The `/status/` `429` was DRF's `anon: 10/minute` throttle on the
   poller, not NVIDIA — it just meant the job hadn't finished.

**The five fixes (all env-tunable, defaults in §11):**

1. **Shallow the SDK retry layer** — `num_retries=MARKETING_LLM_NUM_RETRIES` (default 1) on the
   marketing `LLM` (`_build_marketing_llm`). This kills the uninterruptible deep retry-sleep.
2. **Back off for the rate-limit window** — `_kickoff_marketing_with_retry` sleeps
   `MARKETING_RATE_LIMIT_BACKOFF` (default 30s) on a real 429 instead of 1–2s; a per-minute window
   needs time to reset. Other failures keep quick `2**attempt`.
3. **Hard wall-clock cap (the actual cure for stuck-`processing`)** — `_run_with_hard_timeout`
   runs the kickoff in a worker thread and `join(MARKETING_JOB_TIMEOUT)` (default 240s). On overrun
   it raises `TimeoutError`, the orphaned daemon thread is abandoned, and the worker forces
   `status="error"`. The doc now **always** reaches `draft`/`error`.
4. **Exempt internal endpoints from the anon throttle** — both marketing views set
   `throttle_classes = []` (they are `X-Internal-Secret`-guarded), so the poller is never masked by a
   DRF `429`.
5. **Listing `destination` ObjectId coercion** (`_fetch_listing`) — see §6.

**Known trade-off:** under active rate-limiting, a run now fails fast to `error` (≤ ~`MARKETING_JOB_TIMEOUT`)
rather than hanging — but it may still not produce a draft before the user gives up. To make drafts
survive heavy rate-limiting, reduce burst (lower `max_iter`) or move to a paid NVIDIA tier. Confirmed
the Next.js admin only **polls** `/status/` on failure (it does NOT re-POST `/generate/`), so there
is no duplicate-crew multiplier — if that ever changes, make `/generate/` idempotent.
