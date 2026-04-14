import re
import logging

logger = logging.getLogger(__name__)

# ============ CONSTANTS ============
MAX_MESSAGE_LENGTH = 500

# ============ SUSPICIOUS PATTERNS (Prompt Injection) ============
SUSPICIOUS_PATTERNS = [
    # Instruction revelation attempts (Spanish)
    r'revela(r)?\s+(tus|las|mis)?\s*instrucciones?',
    r'muestra(me)?\s+(tus|las|mis)?\s*instrucciones?',
    r'cu[aá]les?\s+son\s+(tus|las)?\s*instrucciones?',
    r'dime\s+(tus|las)?\s*instrucciones?',
    r'qu[eé]\s+(son\s+)?tus\s+reglas',
    r'cu[aá]l\s+es\s+tu\s+(prompt|sistema)',
    
    # Instruction revelation attempts (English)
    r'show\s+(me\s+)?(your\s+)?(system\s+)?instructions?',
    r'what\s+are\s+your\s+(system\s+)?instructions?',
    r'reveal\s+(your\s+)?instructions?',
    r'print\s+(your\s+)?(system\s+)?(prompt|instructions?)',
    r'repeat\s+(your\s+)?(system\s+)?(instructions?|prompt)',
    r'tell\s+me\s+your\s+(rules|instructions?)',
    r'what\s+(are\s+)?your\s+rules',
    
    # Classic prompt injection
    r'ignore\s+(all\s+)?previous\s+instructions?',
    r'you\s+are\s+now',
    r'system\s*:',
    r'<script',
    r'javascript:',
    r'onerror\s*=',
    r'onclick\s*=',
    r'\broot\b',
    r'\bsudo\b',
    r'grant\s+(me\s+)?access',
    r'\badmin\b',
]

def sanitize_message(message: str) -> str:
    """
    Sanitizes user message and limits length.
    """
    if not message:
        return ""
    # Remove HTML tags or basic injection attempts
    sanitized = message.strip()
    sanitized = re.sub(r'[<>]', '', sanitized)
    return sanitized[:MAX_MESSAGE_LENGTH]

def contains_suspicious_content(message: str) -> bool:
    """
    Detects suspicious patterns (Prompt Injection).
    """
    if not message:
        return False
    return any(re.search(pattern, message, re.IGNORECASE) for pattern in SUSPICIOUS_PATTERNS)
