import os
import re
import html
import json
import logging
import datetime
import threading

from dotenv import load_dotenv
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .services import CloudinaryImageComposer

logger = logging.getLogger(__name__)
load_dotenv()

# Seconds to wait before re-running the crew after a NVIDIA NIM rate-limit (429).
# The free-tier limit is per-minute, so a 1-2s backoff just re-trips it.
_RATE_LIMIT_BACKOFF = int(os.getenv("MARKETING_RATE_LIMIT_BACKOFF", "30"))

# Hard wall-clock budget for the WHOLE background job. CrewAI's per-agent
# ``max_execution_time`` cannot interrupt a blocking SDK retry-sleep, so without
# this cap a rate-limit storm leaves the doc stuck at ``status="processing"``
# forever. When exceeded, the worker forces ``status="error"``.
_JOB_TIMEOUT = int(os.getenv("MARKETING_JOB_TIMEOUT", "240"))

# Hard wall-clock budget for ONE kickoff attempt. Verified empirically: the
# ``timeout``/``num_retries`` knobs on the CrewAI ``LLM`` do NOT reliably reach
# the underlying HTTP call (a stalled NVIDIA NIM request was observed blocking
# ~300s and then being retried by the OpenAI client despite timeout=30,
# num_retries=0). This cap is enforced with the same thread-join pattern as
# ``_run_with_hard_timeout`` so a stalled primary model is abandoned quickly and
# the fallback model still has most of MARKETING_JOB_TIMEOUT left. A healthy
# attempt (fact sheet already injected, no tool calls) completes in well under
# a minute, so 75s only triggers on a genuinely stalled endpoint.
_ATTEMPT_TIMEOUT = int(os.getenv("MARKETING_ATTEMPT_TIMEOUT", "75"))


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _run_with_hard_timeout(fn, timeout_s: int, label: str = "job"):
    """Run ``fn`` in a worker thread, raising ``TimeoutError`` if it overruns.

    CrewAI/litellm retries can block uninterruptibly (a 429 backoff sleeps inside
    a single call), so ``max_execution_time`` is not a reliable ceiling. This
    bounds the whole job in wall-clock time; on timeout the worker thread is
    abandoned (it is a daemon) and the caller forces a terminal ``error`` state.
    """
    result: dict = {}

    def _target() -> None:
        try:
            result["value"] = fn()
        except Exception as exc:  # noqa: BLE001 - re-raised on the caller thread
            result["error"] = exc

    worker = threading.Thread(target=_target, daemon=True)
    worker.start()
    worker.join(timeout_s)
    if worker.is_alive():
        raise TimeoutError(
            f"Marketing {label} exceeded hard timeout of {timeout_s}s")
    if "error" in result:
        raise result["error"]
    return result.get("value")


def _generation_is_empty(raw_output) -> bool:
    """True when the crew output is unusable: non-JSON or a blank caption.

    NVIDIA NIM free-tier models occasionally return the JSON skeleton with
    empty strings for every text field (observed with the copywriter task:
    hashtags + image URL filled, ``instagram_caption`` and every other text
    field ``""``). Such an output must count as a FAILED attempt so the retry
    wrapper regenerates it, instead of persisting a blank ``draft``.
    """
    try:
        data = json.loads(raw_output)
    except (json.JSONDecodeError, TypeError):
        return True
    if not isinstance(data, dict):
        return True
    return not str(data.get("instagram_caption") or "").strip()


def _kickoff_marketing_with_retry(crew, inputs: dict, max_retries: int = 2) -> str:
    """Run ``MarketingCrew.kickoff`` with backoff + provider fallback.

    The primary marketing model is an NVIDIA NIM model (see ``get_marketing_llm``).
    On a rate-limit/provider failure it switches every agent to a different,
    proven NVIDIA model (``get_marketing_fallback_llm``) and retries with
    exponential backoff. Mirrors ``_kickoff_with_retry`` from ``chatbot/views.py``.
    """
    import time as _time
    from chatbot.crew.llm_config import get_marketing_fallback_llm

    last_exception = None
    fallback_injected = False

    for attempt in range(max_retries + 1):
        if attempt > 0:
            # A timed-out attempt leaves a zombie worker thread still running the
            # old crew's kickoff; rebuild the crew so the retry never shares
            # mutable Agent/Task state with that abandoned thread.
            crew = type(crew)()
        # Log which model each agent is actually using so a primary-model failure
        # is immediately distinguishable from a fallback-model failure.
        active_models = [getattr(getattr(a, "llm", None), "model", "unknown")
                         for a in getattr(crew, "agents", [])]
        logger.warning(
            f"Marketing kickoff attempt {attempt}: agents using models={active_models}")
        try:
            override = get_marketing_fallback_llm() if fallback_injected else None
            # Cap each attempt ourselves: SDK-level timeout knobs do not reliably
            # reach the HTTP call, so a stalled model would otherwise eat the
            # whole job budget before the fallback model ever ran.
            result = _run_with_hard_timeout(
                lambda: crew.kickoff(inputs, llm_override=override),
                _ATTEMPT_TIMEOUT,
                label=f"kickoff attempt {attempt}",
            )
            if _generation_is_empty(result):
                raise ValueError(
                    "empty generation: model returned blank/non-JSON content "
                    f"(snippet: {str(result)[:150]!r})")
            return result
        except Exception as e:
            last_exception = e
            error_str = (str(e) + " " + repr(e)).lower()

            is_rate_limit = (
                "429" in error_str
                or "rate limit" in error_str
                or "too many requests" in error_str
                or "overloaded" in error_str
            )
            is_provider_failure = any(sig in error_str for sig in (
                "403", "forbidden", "request not allowed", "permission",
                "410", "gone", "404", "not found", "500", "502", "503",
                "bad gateway", "service unavailable", "not supported", "400",
            ))
            # A task that overran max_execution_time often means the primary model
            # was slow/stalled; retry (and let the fallback model take over).
            is_timeout = "timed out" in error_str or "timeout" in error_str
            # A syntactically-fine but content-empty generation (blank caption)
            # is a model glitch, not a code bug: regenerate on the other model.
            is_empty_generation = "empty generation" in error_str

            logger.warning(
                f"Marketing fallback diagnostic (attempt {attempt}): "
                f"rate_limit={is_rate_limit} provider_failure={is_provider_failure} "
                f"timeout={is_timeout} empty={is_empty_generation} "
                f"snippet={error_str[:200]}")

            if (is_rate_limit or is_provider_failure or is_timeout
                    or is_empty_generation) and attempt < max_retries:
                if not fallback_injected:
                    fallback_injected = True
                    logger.warning(
                        "Switching MarketingCrew agents to fast-tier fallback LLM.")
                # A NVIDIA NIM rate limit is per-minute: a 1-2s backoff just
                # re-trips the same window. Wait long enough for it to reset on a
                # 429; keep the quick exponential backoff for other failures.
                backoff = _RATE_LIMIT_BACKOFF if is_rate_limit else (2 ** attempt)
                logger.warning(
                    f"Marketing retry backoff: sleeping {backoff}s before attempt {attempt + 1}.")
                _time.sleep(backoff)
            else:
                raise

    raise last_exception


_VOWELS = set("aeiouáéíóúü")


def _looks_like_junk_description(text) -> bool:
    """Heuristic: is a source description empty, too short, or gibberish?

    Catches placeholder junk like ``"wjdjwjdj dwqd 9 wd 0 uwq d"`` — consonant
    soup with almost no vowels and many vowel-less "words" — so the admin can be
    told to fix the source data instead of shipping a vague auto-draft.
    """
    if not text or not isinstance(text, str):
        return True
    cleaned = text.strip()
    if len(cleaned) < 15:
        return True

    letters = [c for c in cleaned.lower() if c.isalpha()]
    if not letters:
        return True
    # Real Spanish/English prose is vowel-rich; gibberish is consonant-heavy.
    vowel_ratio = sum(1 for c in letters if c in _VOWELS) / len(letters)
    if vowel_ratio < 0.20:
        return True

    words = re.findall(r"[a-záéíóúñü]+", cleaned.lower())
    if not words:
        return True
    # Too many "words" with no vowel at all (e.g. "wjdjwjdj", "dwqd") => junk.
    vowelless = sum(1 for w in words if not any(v in w for v in _VOWELS))
    if vowelless / len(words) > 0.4:
        return True

    return False


def _assess_source_quality(facts) -> list:
    """Return admin-facing (Spanish) warnings about poor source data, or []."""
    if not facts:
        return ["No se pudieron leer los datos de origen para evaluar su calidad."]

    warnings = []
    if _looks_like_junk_description(facts.get("description")):
        warnings.append(
            "La descripción de origen está vacía o no es válida. Mejora la "
            "descripción del paquete/anuncio para generar contenido de mayor calidad.")
    if facts.get("price_per_person") in (None, "", 0):
        warnings.append(
            "Falta el precio (pricePerPerson) en los datos de origen.")
    if not facts.get("destination"):
        warnings.append("Falta el destino en los datos de origen.")
    return warnings


def _select_image_url(chosen_image_url, facts) -> str:
    """Pick the image to compose over from authoritative DB facts, never the LLM.

    The crew's ``chosen_image_url`` is LLM output and can be hallucinated or
    corrupted — a Cloudinary ``public_id`` is a random string the model may
    silently invent (observed: a real photo ``jm9z…`` became a non-existent
    ``is6b…`` → a 404 image URL shipped to the frontend). So only honour the
    model's choice when it is an EXACT match for a real source image; otherwise
    fall back to the first real image. Returns ``""`` when the source has none.
    """
    images = [str(u) for u in ((facts or {}).get("images") or []) if u]
    if not images:
        return ""
    if chosen_image_url and chosen_image_url in images:
        return chosen_image_url
    if chosen_image_url:
        logger.warning(
            "Crew chosen_image_url is not among the source images "
            "(likely hallucinated); falling back to the first real image.")
    return images[0]


def _overlay_from_facts(facts) -> str:
    """Build the image-overlay text from authoritative DB facts (never the LLM).

    Returns e.g. ``"Barbacoas · 2 días · $40/persona"``; empty if facts missing.
    """
    if not facts:
        return ""
    parts = []
    if facts.get("destination"):
        parts.append(str(facts["destination"]))
    if facts.get("duration_days"):
        parts.append(f"{facts['duration_days']} días")
    price = facts.get("price_per_person")
    if price is not None:
        try:
            # Drop a trailing ".0" so 40.0 renders as "$40".
            price_str = str(int(price)) if float(
                price) == int(price) else str(price)
            parts.append(f"${price_str}/persona")
        except (TypeError, ValueError):
            pass
    return " · ".join(parts)


def _strip_html(text) -> str:
    """Return plain text for the in-app announcement.

    The Next.js frontend manages its own tag elements, so it expects a clean
    string. The LLM is prompted for plain text, but this strips any stray HTML
    tags (and unescapes entities) as a defensive guarantee.
    """
    if not text:
        return ""
    no_tags = re.sub(r"<[^>]+>", "", str(text))
    return html.unescape(no_tags).strip()


def _build_overlay_text(source_type: str, source_id: str) -> str:
    """Fetch source facts and build the deterministic overlay text from them."""
    try:
        from marketing.crew.tools.marketing_source_tool import MarketingSourceTool
        facts = MarketingSourceTool().fetch_facts(source_type, source_id)
        return _overlay_from_facts(facts)
    except Exception as e:
        logger.warning(f"Could not build deterministic overlay text: {e}")
        return ""


def _run_marketing_in_background(content_id, source_type: str, source_id: str) -> None:
    """Background worker: run the marketing crew, compose the image, persist draft.

    Mirrors ``_run_crew_in_background``: on success the ``MarketingContent`` doc
    moves to ``status="draft"`` with all fields; on any failure it moves to
    ``status="error"`` with a recorded message. Never raises to the caller.
    """
    from chatbot.crew.tools.search_accommodation import get_db
    from bson.objectid import ObjectId

    try:
        from marketing.crew.marketing_orchestrator import MarketingCrew
        from marketing.crew.tools.marketing_source_tool import MarketingSourceTool

        # Read the authoritative facts ONCE, up front. They are injected into the
        # copywriter's task (so the agent needs no slow tool round-trip) AND reused
        # below for the deterministic overlay, image selection, and quality flags.
        source_tool = MarketingSourceTool()
        try:
            facts = source_tool.fetch_facts(source_type, source_id)
        except Exception as facts_err:
            logger.warning(f"Could not fetch source facts: {facts_err}")
            facts = None

        source_facts = source_tool.format_facts(
            facts) if facts else "NO_SOURCE_FOUND"

        crew = MarketingCrew()
        raw_output = _run_with_hard_timeout(
            lambda: _kickoff_marketing_with_retry(crew, {
                "source_type": source_type,
                "source_id": source_id,
                "source_facts": source_facts,
            }),
            _JOB_TIMEOUT,
        )

        try:
            content = json.loads(raw_output)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "Marketing crew returned non-JSON output; storing raw text.")
            content = {}

        chosen_image_url = content.get("chosen_image_url", "")

        # Select the source photo deterministically from DB facts — never trust
        # the LLM's chosen_image_url, which can hallucinate a non-existent
        # Cloudinary public_id and produce a 404 composed URL.
        image_url = _select_image_url(chosen_image_url, facts)

        # Deterministic overlay (never trust the LLM for the price on the graphic);
        # fall back to the model's suggestion only if facts are unavailable.
        overlay_text = _overlay_from_facts(
            facts) or content.get("image_overlay_text", "")

        # Junk-source guard: flag empty/gibberish descriptions etc. so the admin is
        # told to improve the source data instead of trusting a vague auto-draft.
        data_quality_warnings = _assess_source_quality(facts)
        if data_quality_warnings:
            logger.info(
                f"Marketing source {source_type}:{source_id} has data-quality "
                f"warnings: {data_quality_warnings}")

        composed_image_url = ""
        if image_url and overlay_text:
            try:
                composed_image_url = CloudinaryImageComposer().compose(
                    image_url, overlay_text) or ""
            except Exception as compose_err:
                logger.warning(
                    f"Image composition failed (non-fatal): {compose_err}")

        update_fields = {
            "status": "draft",
            "instagramCaption": content.get("instagram_caption", ""),
            "hashtags": content.get("hashtags", []),
            "youtubeTitle": content.get("youtube_title", ""),
            "youtubeDescription": content.get("youtube_description", ""),
            "announcementHtml": _strip_html(content.get("announcement_html", "")),
            "imageOverlayText": overlay_text,
            "composedImageUrl": composed_image_url,
            "dataQualityWarnings": data_quality_warnings,
            "updatedAt": _now(),
        }

        db = get_db()
        if db is not None:
            db.get_collection("MarketingContent").update_one(
                {"_id": content_id if isinstance(
                    content_id, ObjectId) else ObjectId(str(content_id))},
                {"$set": update_fields},
            )
            logger.info(f"Marketing draft completed for content {content_id}")
    except Exception as e:
        logger.error(
            f"Background marketing thread failed for {content_id}: {e}")
        try:
            db = get_db()
            if db is not None:
                db.get_collection("MarketingContent").update_one(
                    {"_id": content_id if isinstance(
                        content_id, ObjectId) else ObjectId(str(content_id))},
                    {"$set": {
                        "status": "error",
                        "error": "Content generation failed. Please retry.",
                        "updatedAt": _now(),
                    }},
                )
        except Exception:
            pass


class GenerateContentAsyncView(APIView):
    """POST /api/marketing/generate/async/ — start an async generation job.

    Guarded by ``X-Internal-Secret`` (the Next.js admin proxies the call).
    Inserts a ``processing`` ``MarketingContent`` doc, dispatches the crew on a
    daemon thread, and returns 202 with the new ``contentId`` immediately.
    """

    # Internal, secret-guarded endpoint — exempt from the public anon throttle so
    # polling is never masked by a DRF 429 (see GenerateContentStatusView).
    throttle_classes: list = []

    def post(self, request, *args, **kwargs):
        secret_key = os.getenv("DJANGO_SERVICE_SECRET")
        if secret_key and request.headers.get("X-Internal-Secret") != secret_key:
            logger.warning(
                f"⛔ Unauthorized marketing generate request from {request.META.get('REMOTE_ADDR')}")
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        source_type = request.data.get("sourceType")
        source_id = request.data.get("sourceId")

        if source_type not in ("package", "listing"):
            return Response(
                {"error": "sourceType must be 'package' or 'listing'."},
                status=status.HTTP_400_BAD_REQUEST)
        if not source_id or not isinstance(source_id, str):
            return Response(
                {"error": "sourceId es requerido."},
                status=status.HTTP_400_BAD_REQUEST)

        from chatbot.crew.tools.search_accommodation import get_db
        db = get_db()
        if db is None:
            return Response(
                {"error": "El servicio está temporalmente no disponible."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)

        now = _now()
        result = db.get_collection("MarketingContent").insert_one({
            "sourceType": source_type,
            "sourceId": source_id,
            "status": "processing",
            "instagramCaption": "",
            "hashtags": [],
            "youtubeTitle": "",
            "youtubeDescription": "",
            "announcementHtml": "",
            "imageOverlayText": "",
            "composedImageUrl": "",
            "dataQualityWarnings": [],
            "error": None,
            # Phase 2: populated when a publish is scheduled.
            "scheduledAt": None,
            "createdAt": now,
            "updatedAt": now,
        })
        content_id = result.inserted_id

        thread = threading.Thread(
            target=_run_marketing_in_background,
            args=(content_id, source_type, source_id),
            daemon=True,
        )
        thread.start()

        logger.info(
            f"Async marketing generation started for {source_type}:{source_id} "
            f"(content {content_id})")

        return Response(
            {"contentId": str(content_id), "status": "processing"},
            status=status.HTTP_202_ACCEPTED)


class GenerateContentStatusView(APIView):
    """GET /api/marketing/generate/status/?contentId= — poll a generation job."""

    # Polled in a tight loop by the Next.js admin; the anon 10/min throttle would
    # otherwise 429 the poller before the draft is ready. Secret context is
    # enforced upstream by the proxy, and reads are side-effect free.
    throttle_classes: list = []

    def get(self, request, *args, **kwargs):
        content_id = request.query_params.get("contentId", "")
        if not content_id:
            return Response({"error": "contentId requerido."}, status=status.HTTP_400_BAD_REQUEST)

        from chatbot.crew.tools.search_accommodation import get_db
        from bson.objectid import ObjectId

        try:
            ObjectId(content_id)
        except Exception:
            return Response({"error": "contentId inválido."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            db = get_db()
            if db is None:
                return Response({"status": "processing"}, status=status.HTTP_200_OK)

            doc = db.get_collection("MarketingContent").find_one(
                {"_id": ObjectId(content_id)},
                {
                    "status": 1, "instagramCaption": 1, "hashtags": 1,
                    "youtubeTitle": 1, "youtubeDescription": 1,
                    "announcementHtml": 1, "imageOverlayText": 1,
                    "composedImageUrl": 1, "dataQualityWarnings": 1,
                    "error": 1, "_id": 0,
                },
            )

            if not doc:
                return Response({"error": "Contenido no encontrado."}, status=status.HTTP_404_NOT_FOUND)

            if doc.get("status") in ("draft", "approved", "published", "error"):
                return Response(doc, status=status.HTTP_200_OK)

            return Response({"status": "processing"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"GenerateContentStatusView error: {e}")
            return Response({"status": "processing"}, status=status.HTTP_200_OK)
