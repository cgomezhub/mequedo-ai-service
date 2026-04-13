from django.test import TestCase
from unittest.mock import patch
from chatbot.crew.agents import (
    get_accommodation_specialist,
    get_customer_support_agent,
    get_quality_assurance_agent
)

class AgentConfigurationTests(TestCase):
    @patch('chatbot.crew.llm_config.os.getenv')
    def test_specialist_agent_config(self, mock_getenv):
        # Provide a mock key so LLM config doesn't return None and fail
        mock_getenv.return_value = "sk-mock"
        agent = get_accommodation_specialist()
        
        self.assertEqual(agent.role, "Expert Database Researcher")
        self.assertEqual(agent.allow_delegation, False)
        # Checking optional attributes safely via hasattr for dynamic CrewAI versions
        if hasattr(agent, 'max_iter'):
            self.assertEqual(agent.max_iter, 3)

    @patch('chatbot.crew.llm_config.os.getenv')
    def test_laura_agent_config(self, mock_getenv):
        mock_getenv.return_value = "sk-mock"
        agent = get_customer_support_agent()
        
        self.assertTrue(agent.allow_delegation)
        self.assertIn("Laura", agent.role)

    @patch('chatbot.crew.llm_config.os.getenv')
    def test_qa_agent_config(self, mock_getenv):
        mock_getenv.return_value = "sk-mock"
        agent = get_quality_assurance_agent()
        
        self.assertEqual(agent.allow_delegation, False)
        self.assertIn("Content Validator", agent.role)
