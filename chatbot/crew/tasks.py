from crewai import Task
from textwrap import dedent

from .schemas import IntentSchema
from .callbacks import log_conversation_callback


def get_database_search_task(agent) -> Task:
    return Task(
        description=dedent("""
            Using the conversational context and parsed intent matching properties below, 
            execute the SearchAccommodationTool securely exactly as queried to retrieve real listings natively from MongoDB.
            
            User Message & Routed Data:
            {user_message}
            
            Authenticated User ID:
            {user_id}

            GUEST RESTRICTION: Dynamic searching is an EXCLUSIVE feature for registered members. If the User ID is exactly 'WEB_ANONYMOUS', you MUST skip the SearchAccommodationTool. 
            Instead, explicitly report that property searching requires registration and the next agent (Karen) will offer the buttons.
        """),
        expected_output="A raw list of strictly up to 3 potential accommodations fetched natively from the database. IF the database tool returns no results, you MUST explicitly output: 'NO_PROPERTIES_FOUND'.",
        agent=agent
    )

def get_database_reservation_task(agent) -> Task:
    return Task(
        description=dedent("""
            The user wants to investigate their specific last reservation. 
            Use the 'Mequedo CRM Profile Fetcher' tool passing the User ID '{user_id}'.
            Fetch the data and output the raw CRM record.
        """),
        expected_output="A plaintext summary of the user's single most recent reservation.",
        agent=agent
    )

def get_qa_validation_task(agent) -> Task:
    return Task(
        description=dedent("""
            Critically review the retrieved database listings from the Specialist and ensure they align explicitly 
            with the user's previously extracted parameters.
            
            Original User Context:
            {user_message}

            Flag any accommodations that do not exist or violate rules. Hand off only factual listings.
            
            CRITICAL INSTRUCTION FOR AVAILABILITY: Our database currently does NOT return date or availability 
            information (e.g., 'next weekend'). If the user requests specific dates, you MUST ASSUME the returned 
            listings are available. Do NOT reject or flag listings simply because they lack explicit date confirmation.
        """),
        expected_output="A validated, strictly factual array of accommodations perfectly matching the user's formatting logic without hallucinations.",
        agent=agent,
        human_input=False  # Toggled manually for dev mode
    )


def get_format_search_reply_task(agent) -> Task:
    return Task(
        description=dedent("""
            Format the search results from the Specialist into a SHORT introductory message as Karen,
            plus a structured LISTINGS_JSON data block for the frontend to render.
            
            Authenticated User ID: '{user_id}'
            Note: If the User ID is NOT 'WEB_ANONYMOUS' or 'WEB_FRONTEND', the user is logged in.
            
            IDIOMA: Tu respuesta debe estar EXCLUSIVAMENTE en ESPAÑOL.
            
            CRITICAL RESPONSE FORMAT:
            1. Write a SHORT greeting (1-2 sentences MAX). Mention the actual number of properties found. Example: "¡Hola! Encontré [N] opciones en [ciudad] para ti:"
            2. DO NOT list or describe each property in the text. The frontend renders them as a visual table.
            3. You MUST append the manual search button: [Buscar Manualmente](action:OPEN_SEARCH)
            4. You MUST append a hidden data block at the very end exactly in this format:
            LISTINGS_JSON:[{{"title": "...", "price": 0, "category": "...", "city": "...", "slug": "...", "guests": 0, "bedrooms": 0, "bathrooms": 0}}]
            
            CONSTRAINTS:
            - IF the Specialist returned 'NO_PROPERTIES_FOUND' or found 0 options: Your greeting MUST apologize politely indicating there are no accommodations in that city right now, do NOT invent any properties, and output EXACTLY `LISTINGS_JSON:[]`.
            - MAX 2 sentences of text + the action button + the LISTINGS_JSON block.
            - AUTH: Use [Iniciar Sesión](action:START_LOGIN) ONLY for guests.
            - HALLUCINATION: NUNCA inventes datos que no estén en los resultados del Specialist. Si no hay, debes usar LISTINGS_JSON:[].
            - NO PREAMBLE, NO INTERNAL THOUGHTS.
            - Tu respuesta final debe ser EXCLUSIVAMENTE el mensaje directo al usuario en Español.
        """),
        expected_output="A short Spanish greeting (1-2 sentences) + [Buscar Manualmente] button + LISTINGS_JSON block.",
        agent=agent,
        callback=log_conversation_callback
    )

def get_format_reservation_reply_task(agent) -> Task:
    return Task(
        description=dedent("""
            Synthesize the CRM reservation records into a beautifully formatted, conversational 
            message as Karen. 
            
            Authenticated User ID: '{user_id}'
            Note: If the User ID is NOT 'WEB_ANONYMOUS' or 'WEB_FRONTEND', the user is logged in. Use their context natively.
            
            IDIOMA: Tu respuesta debe estar EXCLUSIVAMENTE en ESPAÑOL.
            
            CRITICAL - ECOSISTEMA DE DATOS (RESERVATIONS):
            Provide the details clearly without exposing raw database IDs.
            You MUST ALWAYS append this exactly at the end of your response to route them:
            🔗 Puedes ver tus viajes y reservas en Mequedo aquí:
            [Ver Mis Viajes](action:GO_TO_TRIPS)
            
            CONSTRAINTS:
            - Max length: 3 paragraphs (approx 150 words).
            - AUTH: Greet users by name if authenticated.
            - Only use information from the Specialist's CRM findings.
            - NO PREAMBLE: Start your response directly with the greeting.
            - NO INTERNAL THOUGHTS: Do not output your thinking process.
            - Tu respuesta final debe ser EXCLUSIVAMENTE el mensaje directo al usuario en Español.
        """),
        expected_output="A conversational Spanish string (max 3 paragraphs) answering the reservation query with the [Ver Mis Viajes] action link.",
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
