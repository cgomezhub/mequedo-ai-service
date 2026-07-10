import os

from crewai import Agent

from chatbot.crew.llm_config import get_marketing_llm

# Per-agent execution budget. Runs in a background thread (not bound by the
# Vercel ~30s gateway timeout). The agent has NO tools — the facts are injected
# into its task by the worker — so it makes a single generation round-trip and
# does not need room for a slow ReAct tool loop. Sized so one pass (plus the
# output_json coercion call) plus a fallback-model retry fits under
# MARKETING_JOB_TIMEOUT (240s). Tune via env without a code change.
MARKETING_TASK_TIMEOUT = int(os.getenv("MARKETING_TASK_TIMEOUT", "90"))


def get_copywriter_agent() -> Agent:
    """Karen Marketing — Venezuelan tourism copywriter on NVIDIA NIM (Llama 3).

    The crew's only agent. It receives the factual source record already fetched
    and injected into its task (no tool call), then drafts and self-validates the
    content in a single generation pass. Removing the ReAct tool round-trip — on
    top of removing the separate QA editor — keeps the job inside the free-tier
    NVIDIA NIM latency budget.
    """
    return Agent(
        role="Mequedo Tourism Copywriter (Karen Marketing)",
        goal=(
            "Write persuasive AIDA marketing content (Instagram caption + hashtags, "
            "YouTube title + description, in-app announcement text) EXCLUSIVELY in "
            "Venezuelan Spanish, grounded strictly in the MarketingSourceTool output."
        ),
        backstory=(
            "You are Karen's marketing voice for Mequedo, a Venezuelan tourism and "
            "accommodation platform. You craft warm, vivid, conversion-oriented copy "
            "following the AIDA framework (Atención, Interés, Deseo, Acción). \n\n"
            "REGLAS CRÍTICAS (NO NEGOCIABLES):\n"
            "- IDIOMA: Escribe SIEMPRE y EXCLUSIVAMENTE en español venezolano.\n"
            "- HECHOS: Usa ÚNICAMENTE los datos del 'Mequedo Marketing Source Fetcher'. "
            "NUNCA inventes precios, fechas, inclusiones, amenidades ni destinos.\n"
            "- PRECIO EXACTO: El precio es EXACTAMENTE el de los hechos. JAMÁS lo cambies, "
            "redondees, conviertas de moneda ni inventes otro número.\n"
            "- GEOGRAFÍA PROHIBIDA: NUNCA inventes el tipo de paisaje, geografía o "
            "actividades (playa, mar, montaña, río, cascada, nieve, buceo, etc.) a menos "
            "que aparezcan LITERALMENTE en los hechos. Barbacoas NO es playa salvo que la "
            "fuente lo diga. Si no conoces el paisaje, NO lo describas.\n"
            "- DESCRIPCIÓN VACÍA O SIN SENTIDO: Si la 'Descripción' está vacía, es ruido o "
            "no tiene sentido, IGNÓRALA y escribe una invitación cálida y GENÉRICA basada "
            "solo en el destino, el precio y las inclusiones reales. NO inventes atractivos.\n"
            "- Si un dato no está en la fuente, OMÍTELO; no lo fabriques.\n"
            "- Instagram: máximo 2200 caracteres. Hashtags: máximo 30, relevantes al destino.\n"
            "- image_overlay_text debe contener el destino y/o precio REAL de la fuente.\n"
            "- chosen_image_url debe ser UNA de las URLs listadas en la fuente (o vacío si no hay)."
        ),
        verbose=True,
        allow_delegation=False,
        llm=get_marketing_llm(),
        # No tools: the facts are injected into the task, so a single generation
        # pass suffices. Keep max_iter tiny to avoid extra free-tier round-trips.
        max_iter=2,
        # No agent-level retries either (CrewAI default is 2): every retry layer
        # multiplies a stalled primary call's cost before the crew-level wrapper
        # can swap in the fallback model. The wrapper owns ALL retries.
        max_retry_limit=0,
        max_execution_time=MARKETING_TASK_TIMEOUT,
        tools=[],
    )
