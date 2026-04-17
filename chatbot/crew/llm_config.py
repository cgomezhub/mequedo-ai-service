import os
import logging
from dotenv import load_dotenv
from crewai import LLM
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()
logger = logging.getLogger(__name__)

# --- Configuración Centralizada (Pinned Versions) ---
# Forzamos 1.5 para evitar el 'limit: 0' de la 3.1 en Free Tier
MODELS = {
    "fast": {
        "openai": os.getenv("OPENAI_FAST_MODEL", "gpt-4o-mini"),
        "nvidia": os.getenv("NVIDIA_FAST_MODEL", "meta/llama-3.1-70b-instruct"),
        "gemini": os.getenv("GEMINI_FAST_MODEL", "gemini-1.5-flash")
    },
    "deep": {
        "openai": os.getenv("OPENAI_DEEP_MODEL", "gpt-4o"),
        "nvidia": os.getenv("NVIDIA_DEEP_MODEL", "deepseek-ai/deepseek-v3.2"),
        "gemini": os.getenv("GEMINI_DEEP_MODEL", "gemini-1.5-pro")
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
    if os.getenv("GEMINI_API_KEY"):
        target_model = "gemini-1.5-flash-latest" if tier == 'fast' else "gemini-1.5-pro-latest"
        logger.warning(
            f"LLM {tier.upper()}: Falling back to native Gemini {target_model}")
        return LLM(
            model=f"gemini/{target_model}",
            api_key=os.getenv("GEMINI_API_KEY"),
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
