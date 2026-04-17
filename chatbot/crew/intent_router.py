import json
import logging
import time as _time
import re
import os

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class IntentSchema(BaseModel):
    intent_type: str = Field(..., description="Classification: 'SEARCH_PROPERTIES', 'LAST_RESERVATION', or 'OUT_OF_SCOPE'.")
    search_city: str | None = Field(None, description="Extracted city name for accommodation searches.")
    search_max_price: int | None = Field(None, description="Extracted strict maximum price limit.")
    search_guests: int | None = Field(None, description="Extracted guest count.")
    search_bedrooms: int | None = Field(None, description="Extracted bedroom requirement.")
    search_bathrooms: int | None = Field(None, description="Extracted bathroom requirement.")


# --- Intent Classification Prompt ---
INTENT_PROMPT = """You are a strict intent classifier for Mequedo, an accommodation rental platform in Venezuela.
Analyze the user's message and classify it into EXACTLY one of three categories.

User Message: '{user_message}'

OUTPUT FORMAT: A raw JSON object (no markdown, no code fences, no explanation):
{{
    "intent_type": "SEARCH_PROPERTIES" | "LAST_RESERVATION" | "OUT_OF_SCOPE",
    "search_city": "City name or null",
    "search_max_price": null or integer,
    "search_guests": null or integer,
    "search_bedrooms": null or integer,
    "search_bathrooms": null or integer
}}

CLASSIFICATION RULES (follow strictly):

1. SEARCH_PROPERTIES — The user EXPLICITLY wants to find, rent, or book accommodation.
   The message MUST contain a clear intent to search for lodging/housing/rooms/apartments/houses to stay in.
   VALID examples: "busco alojamiento en Caracas", "quiero ir a Mérida", "necesito hospedaje para 4 personas",
   "hay apartamentos en Valencia por menos de $50", "busco casa en Margarita".
   
2. LAST_RESERVATION — The user EXPLICITLY asks about their own past bookings, trips, or reservations.
   VALID examples: "mi última reserva", "cuáles son mis reservas", "busca mi último viaje",
   "mis reservaciones", "qué reservé".

3. OUT_OF_SCOPE — EVERYTHING ELSE. This is the DEFAULT. Use it for:
   - Sports, teams, politics, news, entertainment, culture, music, food recipes, history
   - General knowledge questions ("quién es...", "háblame de...", "qué es...")
   - Greetings, goodbyes, compliments, insults
   - Questions about topics unrelated to renting accommodation
   - IMPORTANT: A message mentioning a Venezuelan city or state is NOT automatically a search.
     "Háblame del Cardenales de Lara" → OUT_OF_SCOPE (asking about a baseball team, NOT lodging)
     "La historia de Barquisimeto" → OUT_OF_SCOPE (asking about history, NOT lodging)
     "Quiero ir a Caracas" → SEARCH_PROPERTIES (implies wanting to travel/stay there)

WHEN IN DOUBT, classify as OUT_OF_SCOPE."""


def _parse_intent_output(raw_output: str) -> IntentSchema:
    """Attempts to cleanly parse the intent output string as JSON by extracting the JSON block."""
    try:
        # Extract everything between the first { and last }
        match = re.search(r'\{.*\}', raw_output, re.DOTALL)
        if match:
            clean_json = match.group(0)
            data = json.loads(clean_json)
            return IntentSchema(**data)
        else:
            raise ValueError("No JSON block found")
    except Exception as e:
        logger.warning(f"Failed to cleanly parse intent JSON: {e} - Raw: {raw_output}")
        # Default fallback
        return IntentSchema(intent_type="OUT_OF_SCOPE")


def _call_nvidia(prompt: str, config: dict) -> str | None:
    """Direct call to NVIDIA NIM API via OpenAI-compatible endpoint."""
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        return None
    try:
        import openai
        client = openai.OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        )
        model_name = os.getenv("NVIDIA_FAST_MODEL", "meta/llama-3.1-70b-instruct")
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=config['temp'],
            max_tokens=config['tokens'],
            timeout=config['timeout']
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.warning(f"NVIDIA intent call failed: {e}")
        return None


def _call_gemini(prompt: str, config: dict) -> str | None:
    """Direct call to Gemini API."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_FAST_MODEL", "gemini-1.5-flash-latest")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=config['temp'],
                max_output_tokens=config['tokens']
            )
        )
        return response.text
    except Exception as e:
        logger.warning(f"Gemini intent call failed: {e}")
        return None


def _call_openai(prompt: str, config: dict) -> str | None:
    """Direct call to OpenAI API."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        model_name = os.getenv("OPENAI_FAST_MODEL", "gpt-4o-mini")
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=config['temp'],
            max_tokens=config['tokens'],
            timeout=config['timeout']
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.warning(f"OpenAI intent call failed: {e}")
        return None


def classify_intent_with_retry(user_message: str, max_retries: int = 2) -> IntentSchema:
    """
    Classifies user intent using a direct LLM call (no CrewAI overhead).
    Follows the same provider priority as llm_config.py: NVIDIA → Gemini → OpenAI.
    """
    prompt = INTENT_PROMPT.format(user_message=user_message)
    config = {'temp': 0.1, 'tokens': 200, 'timeout': 15}

    # Provider chain in priority order (matching llm_config.py)
    providers = [
        ("NVIDIA", _call_nvidia),
        ("Gemini", _call_gemini),
        ("OpenAI", _call_openai),
    ]

    for provider_name, call_fn in providers:
        for attempt in range(max_retries + 1):
            logger.info(f"Intent Router: {provider_name} attempt {attempt}...")
            raw_output = call_fn(prompt, config)
            if raw_output:
                intent = _parse_intent_output(raw_output)
                logger.info(f"Intent Router: Classified as {intent.intent_type} via {provider_name}")
                return intent
            # Brief backoff before retry
            if attempt < max_retries:
                _time.sleep(1)
        logger.warning(f"Intent Router: {provider_name} exhausted {max_retries + 1} attempts, trying next provider.")

    logger.error("Intent Router: All providers failed. Defaulting to OUT_OF_SCOPE.")
    return IntentSchema(intent_type="OUT_OF_SCOPE")
