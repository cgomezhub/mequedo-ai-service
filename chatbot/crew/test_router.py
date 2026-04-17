import os
from dotenv import load_dotenv

load_dotenv()

from chatbot.crew.llm_config import get_fast_llm
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_llm():
    llm = get_fast_llm()
    print("Testing LLM:", llm.model)
    # How does CrewAI LLM work under the hood? It exposes a call method
    try:
        if hasattr(llm, 'call'):
            response = llm.call([{"role": "user", "content": "Hello! Reply with just the word YES."}])
            print("Response:", response)
            return True
    except Exception as e:
        print("Call failed:", e)
    return False

if __name__ == "__main__":
    test_llm()
