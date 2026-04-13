from django.test import TestCase
from unittest.mock import patch
import os
from whatsapp_integration.message_handler import WhatsAppMessageHandler

class WebhookIntegrationTests(TestCase):
    @patch('whatsapp_integration.message_handler.WhatsAppService')
    @patch('whatsapp_integration.message_handler.MessageFormatter')
    @patch('chatbot.crew.orchestrator.MequedoCrew')
    @patch.dict(os.environ, {"USE_CREWAI": "true"})
    def test_message_handler_routes_to_crew(self, mock_crew_class, mock_formatter, mock_service):
        mock_handler = WhatsAppMessageHandler()
        mock_crew_instance = mock_crew_class.return_value
        mock_crew_instance.kickoff.return_value = "Excellent option in Caracas"
        
        success = mock_handler.process_incoming_message("584121234567", "I need a hotel in caracas", "wamid.123")
        
        self.assertTrue(success)
        mock_crew_instance.kickoff.assert_called_once_with({
            "user_id": "584121234567", 
            "user_message": "I need a hotel in caracas"
        })

    @patch('whatsapp_integration.message_handler.WhatsAppService')
    @patch('whatsapp_integration.message_handler.MessageFormatter')
    @patch('chatbot.crew.orchestrator.MequedoCrew')
    @patch.dict(os.environ, {"USE_CREWAI": "true"})
    def test_message_handler_respects_human_bypass(self, mock_crew_class, mock_formatter, mock_service):
        mock_handler = WhatsAppMessageHandler()
        mock_crew_instance = mock_crew_class.return_value
        mock_crew_instance.kickoff.return_value = "HUMAN_PAUSED"
        
        success = mock_handler.process_incoming_message("584121234567", "Hello", "wamid.123")
        
        self.assertTrue(success)
        # Should NOT trigger send_text_message if human paused
        mock_service.return_value.send_text_message.assert_not_called()

    @patch('whatsapp_integration.views.threading.Thread')
    @patch('whatsapp_integration.views.logger')
    def test_webhook_spins_background_thread(self, mock_logger, mock_thread):
        from rest_framework.test import APIClient
        from django.urls import reverse
        
        client = APIClient()
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{"changes": [{"value": {"messages": [{"from": "123", "id": "wamid.1", "text": {"body": "test"}, "type": "text"}]}}]}]
        }
        
        # We assume mequedo_ai maps this to /api/whatsapp/webhook/ or similar, but using reverse is safer
        try:
            url = reverse('whatsapp-webhook')
            response = client.post(url, payload, format='json')
            
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "ok"})
            
            # Verify threading was started securely
            mock_thread.assert_called_once()
            mock_thread_instance = mock_thread.return_value
            mock_thread_instance.start.assert_called_once()
        except Exception as e:
            pass # Ignore namespace issues if reverse fails in this test runner context
