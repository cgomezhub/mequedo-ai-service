from crewai import Task
from textwrap import dedent

from .marketing_schemas import MarketingContentSchema


def get_generate_content_task(agent) -> Task:
    return Task(
        description=dedent("""
            Generate channel-ready marketing content for a single Mequedo source.

            Source Type: {source_type}
            Source ID: {source_id}

            STEP 1: Call the 'Mequedo Marketing Source Fetcher' tool with the exact
            source_type and source_id above to retrieve the factual record. This is
            your ONLY source of truth.

            STEP 2: Using ONLY those facts, draft in Venezuelan Spanish:
            - instagram_caption: an AIDA caption (Atención, Interés, Deseo, Acción),
              warm and vivid, MAX 2200 characters.
            - hashtags: up to 30 relevant hashtags (each starting with '#').
            - youtube_title: a catchy title, MAX 100 characters.
            - youtube_description: a factual, engaging description.
            - announcement_html: a short in-app announcement as safe HTML.
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
        """),
        expected_output=(
            "A complete Spanish marketing draft covering Instagram caption + hashtags, "
            "YouTube title + description, announcement HTML, image overlay text, and a "
            "chosen image URL — all grounded strictly in the source facts."
        ),
        agent=agent,
    )


def get_qa_marketing_task(agent, generate_task) -> Task:
    return Task(
        description=dedent("""
            Critically review the copywriter's marketing draft against the factual
            source record it was built from.

            VALIDATION CHECKLIST:
            - Reject/remove any amenity, price, date, inclusion, or destination NOT
              present in the source facts.
            - PRICE: confirm every price equals the EXACT source price; correct any drift.
            - GEOGRAPHY: delete any landscape/activity (beach, sea, mountain, river,
              diving, etc.) not literally in the facts — this is the most common error.
            - DESTINATION: must match the source destination exactly.
            - Enforce instagram_caption <= 2200 characters (trim if needed).
            - Enforce hashtags count <= 30 (drop the least relevant if over).
            - Confirm image_overlay_text references the real price/destination only.
            - Confirm chosen_image_url is one of the source images (or empty string).
            - Ensure all user-facing text is in Venezuelan Spanish.

            Output the final, corrected content as the structured JSON schema.
        """),
        expected_output=(
            "The final validated marketing content as JSON matching MarketingContentSchema, "
            "free of hallucinations and within all channel limits."
        ),
        agent=agent,
        context=[generate_task],
        output_json=MarketingContentSchema,
    )
