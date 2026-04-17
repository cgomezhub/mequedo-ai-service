import os
import logging
from crewai.tools import BaseTool
from pydantic import Field
from typing import Type

logger = logging.getLogger(__name__)


class PlatformActionTool(BaseTool):
    name: str = "Platform Action Trigger"
    description: str = (
        "Triggers UI actions in the Next.js frontend. "
        "Use this when the user needs to register, verify ID, start a listing, or open search. "
        "Valid actions: 'START_REGISTRATION', 'START_LOGIN', 'OPEN_SEARCH', 'START_ID_VERIFICATION', 'START_RENT_PROCESS', 'START_ABOUT_US', 'START_FAQ', 'START_TERMS'. "
        "Requires the current session_id."
    )

    def _run(self, session_id: str, action_name: str) -> str:
        """
        Updates the MongoDB ChatSession with the requested UI action.
        """
        try:
            from chatbot.crew.tools.search_accommodation import get_db
            db = get_db()
            if db is None:
                return "Error: Database unavailable."

            # Map user-friendly descriptions to internal action keys
            action_map = {
                "START_REGISTRATION": "START_REGISTRATION",
                "START_LOGIN": "START_LOGIN",
                "OPEN_SEARCH": "OPEN_SEARCH",
                "START_ID_VERIFICATION": "START_ID_VERIFICATION",
                "START_RENT_PROCESS": "START_RENT_PROCESS",
                "START_ABOUT_US": "START_ABOUT_US",
                "START_FAQ": "START_FAQ",
                "START_TERMS": "START_TERMS",
            }

            clean_action = action_map.get(action_name.upper())
            if not clean_action:
                return f"Error: '{action_name}' is not a valid action. Use START_REGISTRATION, START_LOGIN, OPEN_SEARCH, START_ID_VERIFICATION, START_RENT_PROCESS, START_ABOUT_US, START_FAQ, or START_TERMS."

            result = db.get_collection("ChatSessions").update_one(
                {"session_id": session_id},
                {"$set": {"ui_action": clean_action}}
            )

            if result.modified_count > 0 or result.matched_count > 0:
                logger.info(
                    f"UI Action '{clean_action}' triggered for session {session_id}")
                return f"Success: UI action '{clean_action}' has been queued for the user."
            else:
                return f"Error: Session {session_id} not found."

        except Exception as e:
            logger.error(f"Error triggering UI action: {e}")
            return f"Error: {str(e)}"
