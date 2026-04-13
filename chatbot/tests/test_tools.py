from django.test import TestCase
from pydantic import ValidationError
from chatbot.crew.tools.search_accommodation import SearchAccommodationTool, SearchAccommodationArgs
from chatbot.crew.tools.crm_tool import MequedoInternalCRMTool, CRMQueryArgs
from chatbot.crew.tools.whatsapp_notifier import WhatsAppNotifierTool

class ToolInitializationTests(TestCase):
    def test_search_tool_initialization(self):
        tool = SearchAccommodationTool()
        self.assertEqual(tool.name, "Search Accommodation Database")
        self.assertEqual(tool.args_schema, SearchAccommodationArgs)

    def test_crm_tool_initialization(self):
        tool = MequedoInternalCRMTool()
        self.assertIn("Mequedo CRM", tool.name)

    def test_notifier_tool_initialization(self):
        tool = WhatsAppNotifierTool()
        self.assertIn("WhatsApp Proactive Notifier", tool.name)

    def test_search_accommodation_args_validation(self):
        args = SearchAccommodationArgs(city="Caracas", max_price=100.0, guests=2)
        self.assertEqual(args.city, "Caracas")
        
        with self.assertRaises(ValidationError):
            SearchAccommodationArgs(city="Caracas", max_price="expensive")

    def test_crm_query_args_validation(self):
        args = CRMQueryArgs(user_id="1234567")
        self.assertEqual(args.user_id, "1234567")
        
        with self.assertRaises(ValidationError):
            CRMQueryArgs()
