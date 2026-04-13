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
            they requested. Include any relevant user context (name, pending reservations) if available. 
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
        """),
        expected_output="A validated, strictly factual array of accommodations perfectly matching the user's formatting logic without hallucinations.",
        agent=agent,
        human_input=False  # Toggled manually for dev mode
    )


def get_format_reply_task(agent: Task) -> Task:
    return Task(
        description=dedent("""
            Synthesize the validated listings or answers into a beautifully formatted, conversational 
            Spanish message as Karen. Use the previous history ({conversation_history}) to ensure
            your tone and answers are consistent with the current dialogue.
            Current Session ID: '{session_id}'
            
            CONSTRAINTS:
            - Max length: 3 paragraphs (approx 150 words).
            - Only use information from the Specialist's findings or your 'Mequedo Platform Knowledge' tool.
            - If the user needs to register/verify/list/navigate, include the appropriate Interactive Button syntax:
                - Registration: [Registrarme](action:START_REGISTRATION)
                - ID Verification: [Verificar Identidad](action:START_ID_VERIFICATION)
                - New Listing: [Publicar Alojamiento](action:START_RENT_PROCESS)
                - Check own My Trips/Reservations: [Ver mis reservaciones](action:GO_TO_TRIPS)
                - Check own Listings/Properties: [Ver mis anuncios](action:GO_TO_PROPERTIES)
            - If the user asks about platform features (like registration) and the tool gives no info, ADMIT you don't know and offer human help.
            - Be polite and use emojis sparsely.
            - NEVER include any internal reasoning, pre-text like 'Thought:', or 'Final Answer:' in your output. Your response MUST be solely and exclusively the direct message intended for the user.
        """),
        expected_output="A concise conversational string (max 3 paragraphs) including interactive buttons if necessary.",
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
