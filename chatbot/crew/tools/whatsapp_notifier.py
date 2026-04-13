from pydantic import BaseModel, Field
from typing import Type
from crewai.tools import BaseTool
import logging

logger = logging.getLogger(__name__)

class WhatsAppNotifierArgs(BaseModel):
    phone_number: str = Field(..., description="Target phone number in international format without the + sign.")
    message: str = Field(..., description="The message content to send via WhatsApp.")

class WhatsAppNotifierTool(BaseTool):
    name: str = "WhatsApp Proactive Notifier"
    description: str = (
        "Sends a direct WhatsApp message to the user asynchronously. "
        "Useful for out-of-band proactive notifications or follow-ups requested by the system."
    )
    args_schema: Type[BaseModel] = WhatsAppNotifierArgs

    def _run(self, phone_number: str, message: str) -> str:
        # Stub tracking WhatsApp Webhook routing logic
        logger.info(f"Mocking WhatsApp dispatch to {phone_number}: {message}")
        return f"Successfully queued WhatsApp message dispatch to {phone_number}."
