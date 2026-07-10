from crewai import Task
from textwrap import dedent

from .marketing_schemas import MarketingContentSchema


def get_generate_content_task(agent) -> Task:
    """Single-pass draft + self-validation, emitting the final structured JSON.

    This is the crew's only task (the separate QA task was removed to fit the
    free-tier NVIDIA NIM latency budget). The factual source record is injected
    directly as ``{source_facts}`` — the copywriter makes no tool call — so it
    just drafts and self-reviews its own draft against those facts before
    returning.
    """
    return Task(
        description=dedent("""
            Generate channel-ready marketing content for a single Mequedo source.

            Source Type: {source_type}
            Source ID: {source_id}

            STEP 1: These are the ONLY facts you may use — your single source of
            truth. Do not assume anything not listed here:

            {source_facts}

            STEP 2: Using ONLY those facts, draft in Venezuelan Spanish:
            - instagram_caption: an AIDA caption (Atención, Interés, Deseo, Acción),
              warm and vivid, MAX 2200 characters.
            - hashtags: up to 30 relevant hashtags (each starting with '#').
            - youtube_title: a catchy title, MAX 100 characters.
            - youtube_description: a factual, engaging description.
            - announcement_html: a short in-app announcement as PLAIN TEXT only.
              Do NOT include any HTML tags (no <p>, <br>, <b>, etc.) — the frontend
              renders the tags itself. Return a clean string.
            - image_overlay_text: short text containing a REAL price or destination.
            - chosen_image_url: ONE of the image URLs from the source (empty string if none).

            HARD RULES:
            - NEVER invent prices, dates, inclusions, amenities, or destinations.
            - PRICE: use the EXACT price from the facts. Never change/round/convert it.
            - GEOGRAPHY/ACTIVITIES: never mention landscape or activities (beach, sea,
              mountain, river, diving, snow, etc.) unless they appear LITERALLY in the
              facts. An inland destination is NOT a beach.
            - If the description is empty, noise, or nonsensical, IGNORE it and write a
              warm GENERIC invitation from the destination + price + real inclusions only.
              Do NOT invent attractions to fill the gap.
            - If a field is missing from the source, omit it; do not fabricate.
            - Everything user-facing must be in Venezuelan Spanish.

            STEP 3 (SELF-REVIEW before finalizing): re-read your draft against the
            facts and correct it in place:
            - Every price equals the EXACT source price — no drift in any digit.
            - Delete any landscape/activity (beach, sea, mountain, river, diving,
              snow, etc.) NOT literally in the facts — this is the most common error.
            - The destination matches the source destination exactly.
            - instagram_caption <= 2200 characters; hashtags count <= 30.
            - image_overlay_text references the real price/destination only.
            - chosen_image_url is one of the source images (or an empty string).
            - announcement_html is PLAIN TEXT — strip any HTML tags you added.

            Return ONLY the final corrected content as the structured JSON schema.
        """),
        expected_output=(
            "The final validated marketing content as JSON matching MarketingContentSchema: "
            "Instagram caption + hashtags, YouTube title + description, announcement text, "
            "image overlay text, and a chosen image URL — grounded strictly in the source "
            "facts, free of hallucinations, and within all channel limits."
        ),
        agent=agent,
        output_json=MarketingContentSchema,
    )
