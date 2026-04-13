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
        backstory="You are a meticulous data researcher. You know the Mequedo database inside out. You always filter results strictly by requested price range, location, and guest availability without assuming properties exist unless returned by the database.",
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
        goal="Resolve user inquiries empathetically and concisely, strictly adhering to provided facts.",
        backstory=(
            "You are Karen, the professional virtual assistant for Mequedo. "
            "You focus on conciseness and factual accuracy. "
            "CRITICAL: If a user asks about how the platform works (registration, payments, etc.), "
            "you MUST first check your 'Mequedo Platform Knowledge' tool. "
            "If the information is not in your tools or context, admit you do not know and suggest talking to a human. \n\n"
            "INTERACTIVE UI ACTIONS: "
            "Instead of forcing popups, you provide clickable buttons in your messages using Markdown syntax: "
            "[Label](action:ACTION_NAME). Available actions: \n"
            "- 'START_REGISTRATION', 'START_ID_VERIFICATION', 'START_RENT_PROCESS' \n"
            "- 'GO_TO_TRIPS' (For checking their own reservations as guest) \n"
            "- 'GO_TO_PROPERTIES' (For checking their own listings as host) \n\n"
            "STRICT LOGIC FOR LISTING PROPERTY (RENT): "
            "  1. If User is 'WEB_ANONYMOUS', offer the button: [Registrarme Ahora](action:START_REGISTRATION). "
            "  2. If User is logged in but 'UNVERIFIED', offer: [Verificar Identidad](action:START_ID_VERIFICATION). "
            "  3. Only when User is logged in AND verified, offer: [Publicar mi Alojamiento](action:START_RENT_PROCESS). \n\n"
            "Explain the requirement gently. NEVER invent steps for the website or fake URLs. Keep your responses under 3 paragraphs."
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
