from crewai import Task
from textwrap import dedent

from .schemas import IntentSchema
from .callbacks import log_conversation_callback


def get_intent_extraction_task(agent) -> Task:
    return Task(
        description=dedent("""
            Previous Conversation Context:
            {conversation_history}
            ---
            
            Analyze the user's current message intricately to extract their exact intent and any 
            structured parameters (like city, max price, bedrooms, etc.).
            User Message: '{user_message}'
            Session ID: '{session_id}'
            
            Authenticated User ID: '{user_id}'
            Note: If the User ID is NOT 'WEB_ANONYMOUS' or 'WEB_FRONTEND', the user is logged in to the Mequedo platform.
            In that case, you SHOULD use your User Context Lookup tool to fetch their name and reservation details
            to personalize the conversation before proceeding.
            
            CRITICAL INSTRUCTION: Output a clean, concise text summary of what the user wants and the specific parameters 
            they requested. 
            - VERIFY LOCATION: If the user provides a city name with obvious typos (e.g., 'barqusimeto', 'valensia', 'caraka'), 
              YOU MUST CORRECT IT to the standard Venezuelan spelling (e.g., 'Barquisimeto', 'Valencia', 'Caracas') 
              in your summary for the Specialist.
            Include any relevant user context (name, pending reservations) if available. 
            Do NOT output JSON. Do NOT wrap items in arrays. Just provide a clear set of instructions 
            for the next agent (the Specialist) to read.
        """),
        expected_output="A concise text summary of the user's intent, search parameters, and any personalized user context if authenticated.",
        agent=agent
    )


def get_database_search_task(agent) -> Task:
    return Task(
        description=dedent("""
            Using the conversational context and parsed parameters from the intent extraction task mapping, 
            execute the SearchAccommodationTool securely exactly as queried to retrieve real listings natively from MongoDB.
            If the intent is 'faq' or 'crm' or 'other', you may gracefully skip database searches and pass the request forward.
        """),
        expected_output="A raw list of potential accommodations fetched natively from the database matching the strict criteria.",
        agent=agent,
        context=[]  # Dynamically mapped in Orchestrator
    )


def get_qa_validation_task(agent) -> Task:
    return Task(
        description=dedent("""
            Critically review the retrieved database listings from the Specialist and ensure they align explicitly 
            with the user's previously extracted parameters (like max price, location, bedrooms).
            Flag any accommodations that do not exist or violate rules. Hand off only factual listings.
            
            CRITICAL INSTRUCTION FOR AVAILABILITY: Our database currently does NOT return date or availability 
            information (e.g., 'next weekend'). If the user requests specific dates, you MUST ASSUME the returned 
            listings are available. Do NOT reject or flag listings simply because they lack explicit date confirmation.
        """),
        expected_output="A validated, strictly factual array of accommodations perfectly matching the user's formatting logic without hallucinations.",
        agent=agent,
        human_input=False  # Toggled manually for dev mode
    )


def get_format_reply_task(agent: Task) -> Task:
    return Task(
        description=dedent("""
            Synthesize the validated listings or answers into a beautifully formatted, conversational 
            message as Karen. 
            
            Authenticated User ID: '{user_id}'
            Note: If the User ID is NOT 'WEB_ANONYMOUS' or 'WEB_FRONTEND', the user is logged in. Use their context natively.
            
            IDIOMA: Tu respuesta debe estar EXCLUSIVAMENTE en ESPAÑOL.
            
            CRITICAL - ECOSISTEMA DE DATOS (LISTINGS):
            If the Researcher found properties:
            1. You MUST ONLY include the Top 3 (MAXIMUM) in your conversational text to avoid overwhelming the user.
            2. You MUST include a hidden data block at the very end (containing up to 6 results if found) exactly in this format:
               LISTINGS_JSON:[{{"title": "...", "price": 0, "category": "...", "city": "...", "slug": "...", "guests": 0, "bedrooms": 0, "bathrooms": 0}}]
            3. You MUST ALWAYS include the manual search button: [Buscar Manualmente](action:OPEN_SEARCH).
            
            CONSTRAINTS:
            - Max length: 3 paragraphs (approx 150 words).
            - AUTH: Greeters users by name if authenticated. Use [Iniciar Sesión](action:START_LOGIN) ONLY for guests.
            - Only use information from the Specialist's findings.
            - NO PREAMBLE: Start your response directly with the greeting. NEVER include reasoning like 'Based on the search results...' or 'Since no results were found...'. 
            - NO INTERNAL THOUGHTS: Do not output your thinking process.
            - HALLUCINATION: NUNCA inventes descripciones (ej. "quiet neighborhood", "vistas al mar") si no están en los datos del Researcher.
            - Tu respuesta final debe ser EXCLUSIVAMENTE el mensaje directo al usuario en Español.
        """),
        expected_output="A conversational Spanish string (max 3 paragraphs) with an OPEN_SEARCH button and a hidden LISTINGS_JSON block.",
        agent=agent,
        callback=log_conversation_callback
    )


def get_background_logging_task(agent) -> Task:
    return Task(
        description=dedent("""
            Execute internal background logging and telemetry asynchronously.
            User Message: '{user_message}'
            Analyze the flow secretly.
        """),
        expected_output="Background logging completed.",
        agent=agent,
        async_execution=True
    )
