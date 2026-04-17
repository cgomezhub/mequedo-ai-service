import os
import logging
from crewai import Crew
from pymongo import MongoClient
import certifi

# Disable CrewAI Telemetry gracefully preventing server DNS blocks natively
os.environ["CREWAI_DISABLE_TELEMETRY"] = "1"

from .agents import (
    get_accommodation_specialist,
    get_customer_support_agent
)
from .tasks import (
    get_database_search_task,
    get_database_reservation_task,
    get_format_search_reply_task,
    get_format_reservation_reply_task,
    get_background_logging_task
)

logger = logging.getLogger(__name__)

class MequedoCrew:
    """
    Foundational CrewAI Orchestrator for Mequedo AI Service.
    Handles memory, caching, and precise chained task execution logic.
    """
    def __init__(self, intent_type: str = "SEARCH_PROPERTIES"):
        self.intent_type = intent_type
        self.specialist = get_accommodation_specialist()
        self.support_laura = get_customer_support_agent()
        
        self.agents = [self.specialist, self.support_laura]
        
        if self.intent_type == "LAST_RESERVATION":
            self.reservation_task = get_database_reservation_task(self.specialist)
            self.format_task = get_format_reservation_reply_task(self.support_laura)
            self.format_task.context = [self.reservation_task]
            self.tasks = [self.reservation_task, self.format_task]
        else:
            self.search_task = get_database_search_task(self.specialist)
            self.format_task = get_format_search_reply_task(self.support_laura)
            self.format_task.context = [self.search_task]
            self.tasks = [self.search_task, self.format_task]
        
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

    def kickoff(self, inputs: dict, llm_override=None):
        """
        Executes the crew with an optional LLM override (used for fallback).
        """
        if llm_override:
            logger.warning(f"Orchestrator: Applying LLM override -> {getattr(llm_override, 'model', 'unknown')}")
            for agent in self.agents:
                agent.llm = llm_override

        user_id = inputs.get("user_id", "")
        if user_id and self._check_human_bypass(user_id):
            logger.info(f"Skipping AI Execution: Human bypass active intelligently for {user_id}")
            return "HUMAN_PAUSED"

        if not self.agents or not self.tasks:
            logger.warning("Crew is empty. Needs agents and tasks.")
            return None

        # --- WORKFLOW OPTIMIZATION: Guest Skip ---
        original_tasks = self.tasks
        original_format_context = self.format_task.context
        
        if user_id == "WEB_ANONYMOUS" and self.intent_type == "SEARCH_PROPERTIES":
            logger.info("⚡ [OPTIMIZED] Pruning Search & QA tasks for Guest user.")
            self.tasks = [self.format_task]
            self.format_task.context = []

        crew = self.setup_crew()
        try:
            result = crew.kickoff(inputs=inputs)
            # Find the actual executed formatting task (CrewAI uses deepcopies or modifies the internal list)
            for executed_task in crew.tasks:
                if (getattr(executed_task, 'description', '') == self.format_task.description or 
                    getattr(executed_task, 'expected_output', '') == self.format_task.expected_output):
                    if getattr(executed_task, 'output', None):
                        return getattr(executed_task.output, 'raw_output', str(executed_task.output))
            return str(result)
        except Exception as e:
            logger.error(f"Error executing CrewAI kickoff: {e}")
            raise
        finally:
            # Restore state for the next instance/call
            self.tasks = original_tasks
            self.format_task.context = original_format_context
