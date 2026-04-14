import os
from dotenv import load_dotenv
import logging
from crewai import LLM

# Check available providers based on env
load_dotenv()
logger = logging.getLogger(__name__)

# ============================================================
# LLM Provider Priority Order (per tier):
#
#  Fast (8B-class):     OpenAI gpt-4o-mini → Gemini Flash → NVIDIA 8B
#  Deep (70B-class):    OpenAI gpt-4o      → Gemini Pro  → NVIDIA 70B
#
# Gemini is the GCP-backed fallback when NVIDIA NIM rate limits (40 RPM)
# are exhausted. Set GEMINI_API_KEY in your .env / Railway env vars.
# ============================================================


def _ensure_nvidia_env() -> None:
    """LiteLLM expects NVIDIA_NIM_API_KEY — sync it from NVIDIA_API_KEY if needed."""
    if os.getenv("NVIDIA_API_KEY") and not os.getenv("NVIDIA_NIM_API_KEY"):
        os.environ["NVIDIA_NIM_API_KEY"] = os.getenv("NVIDIA_API_KEY")


def get_fast_llm() -> LLM | None:
    """
    Returns a fast reasoning LLM for simple tasks (intent extraction, routing).

    Priority:
        1. OpenAI gpt-4o-mini        (if OPENAI_API_KEY set)
        2. NVIDIA NIM Llama 3 8B     (if NVIDIA_API_KEY set)  ← Primary
        3. Google Gemini 1.5 Flash   (if GEMINI_API_KEY set)  ← Fallback
    """
    _ensure_nvidia_env()

    if os.getenv("OPENAI_API_KEY"):
        logger.debug("Fast LLM: using OpenAI gpt-4o-mini")
        return LLM(
            model="gpt-4o-mini",
            temperature=0.2,
            max_tokens=500,
            timeout=25
        )

    if os.getenv("NVIDIA_API_KEY"):
        logger.debug("Fast LLM: using NVIDIA NIM Llama 3 8B")
        return LLM(
            model="nvidia_nim/meta/llama3-8b-instruct",
            api_key=os.getenv("NVIDIA_API_KEY"),
            temperature=0.2,
            max_tokens=500,
            timeout=25
        )

    if os.getenv("GEMINI_API_KEY"):
        logger.debug("Fast LLM: using Google Gemini Flash Latest")
        return LLM(
            model="gemini/gemini-flash-latest",
            api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.2,
            max_tokens=500,
            timeout=25
        )

    logger.error("No valid API key found for Fast LLM. Set GEMINI_API_KEY, OPENAI_API_KEY, or NVIDIA_API_KEY.")
    return None


def get_deep_llm() -> LLM | None:
    """
    Returns a deep reasoning LLM for complex tasks (Laura's responses, QA, CRM).

    Priority:
        1. OpenAI gpt-4o             (if OPENAI_API_KEY set)
        2. NVIDIA NIM Llama 3 70B    (if NVIDIA_API_KEY set)  ← Primary High-Performance
        3. Google Gemini 1.5 Pro     (if GEMINI_API_KEY set)  ← Robust Fallback
    """
    _ensure_nvidia_env()

    if os.getenv("OPENAI_API_KEY"):
        logger.debug("Deep LLM: using OpenAI gpt-4o")
        return LLM(
            model="gpt-4o",
            temperature=0.4,
            max_tokens=1000,
            timeout=45
        )

    if os.getenv("NVIDIA_API_KEY"):
        logger.debug("Deep LLM: using NVIDIA NIM Llama 3 70B")
        return LLM(
            model="nvidia_nim/meta/llama3-70b-instruct",
            api_key=os.getenv("NVIDIA_API_KEY"),
            temperature=0.4,
            max_tokens=1000,
            timeout=45
        )

    if os.getenv("GEMINI_API_KEY"):
        logger.debug("Deep LLM: using Google Gemini Pro Latest")
        return LLM(
            model="gemini/gemini-pro-latest",
            api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.4,
            max_tokens=1000,
            timeout=45
        )

    logger.error("No valid API key found for Deep LLM. Set GEMINI_API_KEY, OPENAI_API_KEY, or NVIDIA_API_KEY.")
    return None


def get_fallback_llm() -> LLM | None:
    """
    Returns the best available fallback LLM when the primary provider fails.

    Used by _kickoff_with_retry in views.py when NVIDIA NIM returns 429.
    Prefers Gemini (GCP-billed, high rate limits) over NVIDIA.
    """
    if os.getenv("GEMINI_API_KEY"):
        logger.info("Fallback LLM: switching to Google Gemini Flash Latest due to provider failure.")
        return LLM(
            model="gemini/gemini-flash-latest",
            api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.3,
            max_tokens=800,
            timeout=30
        )

    if os.getenv("OPENAI_API_KEY"):
        logger.info("Fallback LLM: switching to OpenAI gpt-4o-mini due to provider failure.")
        return LLM(
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=800,
            timeout=30
        )

    logger.error("No fallback LLM available. Set GEMINI_API_KEY or OPENAI_API_KEY.")
    return None
