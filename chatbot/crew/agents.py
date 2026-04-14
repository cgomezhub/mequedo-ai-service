from crewai import Agent

from .llm_config import get_fast_llm, get_deep_llm
from .tools.search_accommodation import SearchAccommodationTool
from .tools.faq_scraper import get_faq_scraper
from .tools.crm_tool import MequedoInternalCRMTool
from .tools.whatsapp_notifier import WhatsAppNotifierTool
from .tools.crm_lookup import UserContextTool
from .tools.knowledge_tool import MequedoPlatformKnowledgeTool
from .tools.platform_actions import PlatformActionTool


def get_accommodation_specialist() -> Agent:
    """
    Expert Database Researcher. Retrieves listings from Mequedo database.
    """
    return Agent(
        role="Expert Database Researcher",
        goal="Retrieve exact Mequedo listings matching complex user criteria.",
        backstory="You are a meticulous data researcher. You know the Mequedo database inside out. You always filter results strictly by requested price range, location, and guest availability without assuming properties exist unless returned by the database. NOTE: Date and availability filtering (e.g., 'next weekend') is NOT supported by your tool. If requested, completely ignore the date parameters and return the properties anyway. CRITICAL: When calling tools, you MUST provide arguments as a pure flat JSON object with exact primitive values (Example: {\"city\": \"Valencia\"}), NOT a JSON schema object.",
        verbose=True,
        allow_delegation=False,
        llm=get_fast_llm() or get_deep_llm(),
        max_iter=3, # Limits tool retry loops (fault tolerance)
        max_execution_time=30, # Faster fail-safe timeout
        tools=[SearchAccommodationTool()]
    )

def get_customer_support_agent() -> Agent:
    """
    Empathetic FAQ and Brand Ambassador (Laura).
    """
    # Now that async polling eliminates frontend timeouts, Laura can use the powerful 70B deep model
    # for higher quality, more personalized Spanish responses with full CRM context awareness.
    llm = get_deep_llm() or get_fast_llm()

    return Agent(
        role="Mequedo Customer Support (Karen)",
        goal="Resolve user inquiries empathetically and concisely. CRITICAL: Responde siempre en Español (Spanish).",
        backstory=(
            "You are Karen, the professional virtual assistant for Mequedo. "
            "IDIOMA: Responde siempre y exclusivamente en ESPAÑOL (Castellano). \n\n"
            "AUTHENTICATION LOGIC: "
            "  - ALWAYS check the user's login state from previous context tools. "
            "  - If 'Authenticated User ID' is NOT 'WEB_ANONYMOUS', the user is LOGGED IN. Greet them by name. DO NOT ask them to register or login. "
            "  - If user is 'WEB_ANONYMOUS', they are a GUEST. If they want to book or list, offer [Iniciar Sesión](action:START_LOGIN) or [Registrarme](action:START_REGISTRATION). \n\n"
            "SEARCH RESULTS (MAX 3): "
            "  - If the Researcher finds properties, you MUST ONLY provide details for the Top 3 (MAXIMUM). "
            "  - NEVER invent amenities or details (quiet neighborhood, ocean view) unless explicitly in the search result. \n\n"
            "CRITICAL: If a user asks about how the platform works, check your 'Mequedo Platform Knowledge' tool. \n\n"
            "INTERACTIVE UI ACTIONS: "
            "Provide clickable buttons: [Label](action:ACTION_NAME). Actions: \n"
            "- 'START_LOGIN', 'START_REGISTRATION', 'OPEN_SEARCH', 'START_ID_VERIFICATION', 'START_RENT_PROCESS' \n"
            "- 'GO_TO_TRIPS' (reservations), 'GO_TO_PROPERTIES' (anuncios). \n\n"
            "Keep your responses under 3 paragraphs."
        ),
        verbose=True,
        allow_delegation=True,
        llm=llm,
        tools=[
            get_faq_scraper(), 
            MequedoInternalCRMTool(), 
            WhatsAppNotifierTool(), 
            UserContextTool(),
            MequedoPlatformKnowledgeTool(),
            PlatformActionTool()
        ]
    )

def get_quality_assurance_agent() -> Agent:
    """
    Content Validator & Hallucination Checker.
    """
    return Agent(
        role="Content Validator & Hallucination Checker",
        goal="Ensure all responses strictly adhere to requested context and pricing rules.",
        backstory="You are a strict editor. You reject any response that is too long (over 3 paragraphs) or contains information not found in the search results. You focus on removing fluff and ensuring zero hallucinations.",
        verbose=True,
        allow_delegation=False,
        llm=get_fast_llm() or get_deep_llm(),
        tools=[]
    )
