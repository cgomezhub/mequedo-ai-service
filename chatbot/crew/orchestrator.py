import os
import logging
from crewai import Crew
from pymongo import MongoClient
import certifi

# Disable CrewAI Telemetry gracefully preventing server DNS blocks natively
os.environ["CREWAI_DISABLE_TELEMETRY"] = "1"

from .agents import (
    get_accommodation_specialist,
    get_customer_support_agent,
    get_quality_assurance_agent
)
from .tasks import (
    get_intent_extraction_task,
    get_database_search_task,
    get_qa_validation_task,
    get_format_reply_task,
    get_background_logging_task
)

logger = logging.getLogger(__name__)

class MequedoCrew:
    """
    Foundational CrewAI Orchestrator for Mequedo AI Service.
    Handles memory, caching, and precise chained task execution logic.
    """
    def __init__(self):
        self.specialist = get_accommodation_specialist()
        self.support_laura = get_customer_support_agent()
        self.qa_agent = get_quality_assurance_agent()
        
        self.agents = [self.specialist, self.support_laura, self.qa_agent]
        
        # Instantiate Tasks dynamically with assigned agents
        self.intent_task = get_intent_extraction_task(self.support_laura)
        
        self.search_task = get_database_search_task(self.specialist)
        self.search_task.context = [self.intent_task] # Inject context mapping natively
        
        self.qa_task = get_qa_validation_task(self.qa_agent)
        self.qa_task.context = [self.search_task]
        
        self.format_task = get_format_reply_task(self.support_laura)
        self.format_task.context = [self.intent_task, self.qa_task]
        
        self.tasks = [
            self.intent_task,
            self.search_task,
            self.qa_task,
            self.format_task
        ]
        
    def setup_crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            # Disable memory systems to prevent OpenAI embedding initializations for NIM
            memory=False,
            # Enable cross-agent caching
            cache=True,
            verbose=True
        )

    def _check_human_bypass(self, user_id: str) -> bool:
        """
        Queries MongoDB securely to see if the admin paused the AI from the Mequedo Dashboard context.
        """
        try:
            from chatbot.crew.tools.search_accommodation import get_db
            db = get_db()
            users_col = db.get_collection("Users")
            user = users_col.find_one({"phoneNumber": user_id})
            if user and user.get("is_human_paused", False):
                return True
        except Exception as e:
            logger.warning(f"Error checking human bypass: {e}")
        return False

    def kickoff(self, inputs: dict):
        user_id = inputs.get("user_id", "")
        if user_id and self._check_human_bypass(user_id):
            logger.info(f"Skipping AI Execution: Human bypass active intelligently for {user_id}")
            return "HUMAN_PAUSED"

        if not self.agents or not self.tasks:
            logger.warning("Crew is empty. Needs agents and tasks.")
            return None

        crew = self.setup_crew()
        try:
            result = crew.kickoff(inputs=inputs)
            # Find the actual executed formatting task (CrewAI uses deepcopies or modifies the internal list)
            for executed_task in crew.tasks:
                if executed_task.description == self.format_task.description:
                    if getattr(executed_task, 'output', None):
                        return getattr(executed_task.output, 'raw_output', str(executed_task.output))
            return str(result)
        except Exception as e:
            logger.error(f"Error executing CrewAI kickoff: {e}")
            raise
