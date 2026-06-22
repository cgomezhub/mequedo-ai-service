import os

from crewai import Agent

from chatbot.crew.llm_config import get_marketing_llm
from .tools.marketing_source_tool import MarketingSourceTool

# Per-agent execution budget. Runs in a background thread (not bound by the
# Vercel ~30s gateway timeout), so a 70B NVIDIA NIM pass needs generous room;
# 90s was too tight under load. Tune via env without a code change.
MARKETING_TASK_TIMEOUT = int(os.getenv("MARKETING_TASK_TIMEOUT", "180"))


def get_copywriter_agent() -> Agent:
    """Karen Marketing — Venezuelan tourism copywriter on Claude Opus 4.8."""
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
        max_iter=3,
        max_execution_time=MARKETING_TASK_TIMEOUT,
        tools=[MarketingSourceTool()],
    )


def get_brand_qa_agent() -> Agent:
    """Brand/QA Editor — hallucination + brand-voice checker on Claude Opus 4.8."""
    return Agent(
        role="Mequedo Brand & QA Editor",
        goal=(
            "Reject any invented amenity, price, date, or inclusion not present in the "
            "source facts; enforce the Instagram 2200-character limit and a hashtag "
            "count of 30 or fewer; confirm the image overlay text references a real "
            "price or destination; output the final validated structured JSON."
        ),
        backstory=(
            "You are a meticulous Spanish-language brand editor for Mequedo. You compare "
            "every claim in the draft against the factual source record and strip anything "
            "unsupported. \n\n"
            "VERIFICACIONES OBLIGATORIAS:\n"
            "- PRECIO: el precio mencionado debe ser EXACTAMENTE el de los hechos. Si "
            "difiere en cualquier dígito, corrígelo al precio real.\n"
            "- GEOGRAFÍA: elimina toda mención de paisaje o actividad (playa, mar, montaña, "
            "río, buceo, etc.) que NO aparezca literalmente en los hechos. Es un error grave.\n"
            "- DESTINO: el destino debe coincidir exactamente con el de los hechos.\n"
            "- Mantén el español venezolano y respeta los límites (IG ≤2200, hashtags ≤30).\n"
            "You produce clean, final marketing JSON, free of hallucinations."
        ),
        verbose=True,
        allow_delegation=False,
        llm=get_marketing_llm(),
        max_iter=3,
        max_execution_time=MARKETING_TASK_TIMEOUT,
        tools=[],
    )
