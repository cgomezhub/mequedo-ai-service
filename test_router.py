import os
import time
from dotenv import load_dotenv

load_dotenv()

from chatbot.crew.intent_router import classify_intent_with_retry

def test():
    test_cases = [
        ("quiero ir a caracas", "SEARCH_PROPERTIES"),
        ("busca mi ultima reservacion", "LAST_RESERVATION"),
        ("Hablame del Cardenales de Lara", "OUT_OF_SCOPE"),
        ("busca en Barquisimeto", "SEARCH_PROPERTIES"),
        ("que es la inflacion", "OUT_OF_SCOPE"),
    ]

    for msg, expected in test_cases:
        start = time.time()
        intent = classify_intent_with_retry(msg)
        elapsed = time.time() - start
        status = "✅" if intent.intent_type == expected else "❌"
        print(f"{status} [{elapsed:.1f}s] '{msg}' → {intent.intent_type} (expected: {expected})")
        if intent.search_city:
            print(f"   └── city={intent.search_city}")

if __name__ == "__main__":
    test()
