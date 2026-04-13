from pydantic import BaseModel, Field
from typing import Type
from crewai.tools import BaseTool

class CRMQueryArgs(BaseModel):
    user_id: str = Field(..., description="The phone number or ID of the user requesting help.")

class MequedoInternalCRMTool(BaseTool):
    name: str = "Mequedo CRM Profile Fetcher"
    description: str = (
        "Fetches user reservation history and account status from the internal Mequedo CRM database. "
        "Use this exclusively when a user asks about their specific past bookings or profile status."
    )
    args_schema: Type[BaseModel] = CRMQueryArgs

    def _run(self, user_id: str) -> str:
        # Stub implementation simulating Next.js CRM MongoDB fetch
        return f"User {user_id} is an Active Member with 1 past booking (Casa Margarita) and no current reservations."
