import os
import logging
from pymongo import MongoClient
import certifi
from crewai.tasks.task_output import TaskOutput

logger = logging.getLogger(__name__)

def log_conversation_callback(output: TaskOutput):
    """
    Asynchronous callback executed when the final Laura response is generated.
    Saves the interaction securely into the Next.js CRM MongoDB conversations collection.
    """
    try:
        # Avoid blocking standard flows on database connection timeout failures
        client = MongoClient(os.getenv("DATABASE_URL"), tlsCAFile=certifi.where(), serverSelectionTimeoutMS=2000)
        db = client.get_database(os.getenv("MONGODB_DB_NAME", "test"))
        conversations_col = db.get_collection("Conversations")
        
        # For this foundational logging, we persist the raw model output.
        doc = {
            "ai_response": output.raw,
            "status": "completed",
            "source": "crewai_webhook"
        }
        
        conversations_col.insert_one(doc)
        logger.info("Successfully asynchronously logged CrewAI response to MongoDB Conversations.")
    except Exception as e:
        logger.warning(f"Failed to execute conversational logging callback: {e}")
