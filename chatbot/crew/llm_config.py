import os
import logging
from dotenv import load_dotenv
from crewai import LLM

load_dotenv()
logger = logging.getLogger(__name__)

# --- Configuración Centralizada (Pinned Versions) ---
# Forzamos 1.5 para evitar el 'limit: 0' de la 3.1 en Free Tier
MODELS = {
    "fast": {
        "openai": os.getenv("OPENAI_FAST_MODEL", "gpt-4o-mini"),
        "nvidia": os.getenv("NVIDIA_FAST_MODEL", "meta/llama-3.1-70b-instruct"),
        "gemini": os.getenv("GOOGLE_FAST_MODEL", "google/gemma-4-31b-it")
    },
    "deep": {
        "openai": os.getenv("OPENAI_DEEP_MODEL", "gpt-4o"),
        "nvidia": os.getenv("NVIDIA_DEEP_MODEL", "deepseek-ai/deepseek-v4-pro"),
        "gemini": os.getenv("GOOGLE_DEEP_MODEL", "google/diffusiongemma-26b-a4b-it")
    }
}


def _ensure_env():
    """Sincroniza claves y verifica entorno."""
    if os.getenv("NVIDIA_API_KEY") and not os.getenv("NVIDIA_NIM_API_KEY"):
        os.environ["NVIDIA_NIM_API_KEY"] = os.getenv("NVIDIA_API_KEY")


def get_llm(tier='fast'):
    _ensure_env()

    config = {
        'temp': 0.2 if tier == 'fast' else 0.4,
        'tokens': 300 if tier == 'fast' else 800,
        'timeout': 25 if tier == 'fast' else 45
    }

    # 1. Prioridad: NVIDIA (Free, fast)
    if os.getenv("NVIDIA_API_KEY"):
        model_name = MODELS[tier]["nvidia"]
        logger.debug(f"LLM {tier.upper()}: Using NVIDIA NIM {model_name}")
        return LLM(
            model=f"nvidia_nim/{model_name}",
            api_key=os.getenv("NVIDIA_API_KEY"),
            temperature=config['temp'],
            max_tokens=config['tokens'],
            timeout=config['timeout']
        )

    # 2. Prioridad: Gemini (Free tier, moderate RPM)
    if os.getenv("GOOGLE_API_KEY"):
        target_model = "gemini-1.5-flash-latest" if tier == 'fast' else "gemini-1.5-pro-latest"
        logger.warning(
            f"LLM {tier.upper()}: Falling back to native Gemini {target_model}")
        return LLM(
            model=f"gemini/{target_model}",
            api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=config['temp'],
            max_tokens=config['tokens'],
            timeout=config['timeout']
        )

    # 3. Prioridad: OpenAI (Paid, highest quality)
    if os.getenv("OPENAI_API_KEY"):
        model_name = MODELS[tier]["openai"]
        logger.debug(f"LLM {tier.upper()}: Using OpenAI {model_name}")
        return LLM(model=model_name, temperature=config['temp'], max_tokens=config['tokens'], timeout=config['timeout'])

    logger.error(f"No API keys found for tier {tier}")
    return None


# Aliases para mantener compatibilidad con tu código actual


def get_fast_llm(): return get_llm(tier='fast')
def get_deep_llm(): return get_llm(tier='deep')
# Flash es el fallback por excelencia
def get_fallback_llm(): return get_llm(tier='fast')


# --- Marketing crew LLMs (NVIDIA NIM only) ---
# Anthropic/OpenAI/Gemini are NOT used here: Anthropic geo-blocks Venezuela
# (403 "Request not allowed") and the app server runs on a Venezuelan IP. NVIDIA
# NIM is reachable from VE, free, and already proven on Railway. Both models below
# are verified invocable WITH tool-calling support (the copywriter calls a tool).
MARKETING_MODEL = os.getenv("MARKETING_MODEL", "meta/llama-3.3-70b-instruct")
MARKETING_FALLBACK_MODEL = os.getenv(
    "MARKETING_FALLBACK_MODEL", "meta/llama-3.1-70b-instruct")
# Low temperature keeps the copy FAITHFUL to the DB facts. High temperature (0.7)
# made llama-3.3 invent geography (e.g. a "beach" for inland Barbacoas) and drift
# on the price. Tone/warmth comes from the prompt, not from temperature.
MARKETING_TEMPERATURE = float(os.getenv("MARKETING_TEMPERATURE", "0.2"))


def _build_marketing_llm(model_name: str):
    """Build the NVIDIA NIM LLM for the marketing crew.

    Falls back to the chatbot fast tier if ``NVIDIA_API_KEY`` is missing. Uses a
    low temperature so generated copy stays grounded in the source facts.
    """
    _ensure_env()
    if not os.getenv("NVIDIA_API_KEY"):
        logger.warning(
            "NVIDIA_API_KEY not set; marketing crew falling back to fast tier LLM.")
        return get_fast_llm()

    logger.debug(f"Marketing LLM: Using NVIDIA NIM {model_name}")
    return LLM(
        model=f"nvidia_nim/{model_name}",
        api_key=os.getenv("NVIDIA_API_KEY"),
        temperature=MARKETING_TEMPERATURE,
        max_tokens=2000,
        timeout=60
    )


def get_marketing_llm():
    """Primary LLM for the marketing content crew (NVIDIA NIM)."""
    return _build_marketing_llm(MARKETING_MODEL)


def get_marketing_fallback_llm():
    """Fallback LLM for the marketing crew — a different, proven NVIDIA model."""
    return _build_marketing_llm(MARKETING_FALLBACK_MODEL)
