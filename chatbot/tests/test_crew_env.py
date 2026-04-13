from django.test import TestCase
from unittest.mock import patch
import os

from chatbot.crew.llm_config import get_fast_llm, get_deep_llm

class CrewEnvTests(TestCase):
    @patch('chatbot.crew.llm_config.os.getenv')
    def test_get_fast_llm_openai(self, mock_getenv):
        def side_effect(key):
            if key == "OPENAI_API_KEY":
                return "sk-mock-key"
            return None
        mock_getenv.side_effect = side_effect
        
        llm = get_fast_llm()
        self.assertIsNotNone(llm)
        self.assertEqual(llm.model, "gpt-4o-mini")

    @patch('chatbot.crew.llm_config.os.getenv')
    def test_get_deep_llm_openai(self, mock_getenv):
        def side_effect(key):
            if key == "OPENAI_API_KEY":
                return "sk-mock-key"
            return None
        mock_getenv.side_effect = side_effect
        
        llm = get_deep_llm()
        self.assertIsNotNone(llm)
        self.assertEqual(llm.model, "gpt-4o")

    @patch('chatbot.crew.llm_config.os.getenv')
    def test_fallback_nvidia(self, mock_getenv):
        def side_effect(key):
            if key == "NVIDIA_API_KEY":
                return "sk-mock-nvidia-key"
            return None
        mock_getenv.side_effect = side_effect
        
        fast_llm = get_fast_llm()
        self.assertIsNotNone(fast_llm)
        # Langchain ChatNVIDIA models have a `model` attribute usually
        self.assertTrue(hasattr(fast_llm, 'model'))
        
        deep_llm = get_deep_llm()
        self.assertIsNotNone(deep_llm)
        self.assertTrue(hasattr(deep_llm, 'model'))
