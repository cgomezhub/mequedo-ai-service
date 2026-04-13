import os
from crewai.tools import BaseTool
from pydantic import Field
from typing import Type

class MequedoPlatformKnowledgeTool(BaseTool):
    name: str = "Mequedo Platform Knowledge"
    description: str = "Query this tool for official procedures (registration, support, rules) of the Mequedo platform. Use this before answering any 'how to' questions about the website."

    def _run(self, query: str) -> str:
        """
        Reads the official mequedo_rules.md file.
        """
        try:
            # Resolve path relative to this file
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            knowledge_path = os.path.join(base_path, "knowledge", "mequedo_rules.md")
            
            if not os.path.exists(knowledge_path):
                return "Error: Official knowledge file not found."
                
            with open(knowledge_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            return content
        except Exception as e:
            return f"Error reading knowledge: {str(e)}"
