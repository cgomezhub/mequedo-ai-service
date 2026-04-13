from django.test import TestCase
from unittest.mock import patch, MagicMock
from chatbot.crew.orchestrator import MequedoCrew

# CrewAI's Agent validates llm as either a string model name or BaseLLM instance.
# We return a plain string to satisfy Pydantic without making real API calls.
LLM_PATCH = 'chatbot.crew.llm_config.LLM'
MOCK_MODEL = "openai/gpt-4o-mini"  # Accepted string format — no network call in Agent init


class TaskConfigurationTests(TestCase):

    @patch(LLM_PATCH)
    @patch('chatbot.crew.llm_config.os.getenv', return_value='sk-mock')
    def test_crew_tasks_initialization(self, mock_getenv, mock_llm_cls):
        mock_llm_cls.return_value = MOCK_MODEL
        crew = MequedoCrew()
        self.assertEqual(len(crew.tasks), 4)
        # Verify Context pipelines ensure strict schema bindings automatically
        self.assertEqual(crew.search_task.context[0], crew.intent_task)
        self.assertEqual(crew.qa_task.context[0], crew.search_task)
        self.assertIn(crew.intent_task, crew.format_task.context)
        self.assertIn(crew.qa_task, crew.format_task.context)

    @patch(LLM_PATCH)
    @patch('chatbot.crew.tools.search_accommodation.get_db')
    @patch('chatbot.crew.llm_config.os.getenv', return_value='sk-mock')
    def test_human_bypass_active(self, mock_getenv, mock_get_db, mock_llm_cls):
        mock_llm_cls.return_value = MOCK_MODEL
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.get_collection.return_value = mock_col
        mock_col.find_one.return_value = {"phoneNumber": "123", "is_human_paused": True}

        crew = MequedoCrew()
        result = crew.kickoff({"user_id": "123", "user_message": "Hello bounds"})
        self.assertEqual(result, "HUMAN_PAUSED")

    @patch(LLM_PATCH)
    @patch('chatbot.crew.orchestrator.Crew')
    @patch('chatbot.crew.tools.search_accommodation.get_db')
    @patch('chatbot.crew.llm_config.os.getenv', return_value='sk-mock')
    def test_human_bypass_inactive(self, mock_getenv, mock_get_db, mock_crew_class, mock_llm_cls):
        mock_llm_cls.return_value = MOCK_MODEL
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.get_collection.return_value = mock_col
        mock_col.find_one.return_value = {"phoneNumber": "123", "is_human_paused": False}

        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = "AI_RESPONSE"
        mock_crew_instance.tasks = []
        mock_crew_class.return_value = mock_crew_instance

        crew = MequedoCrew()
        result = crew.kickoff({"user_id": "123", "user_message": "Hello standard check testing"})
        self.assertEqual(result, "AI_RESPONSE")
