"""
Configuration for the WHO-aligned AI Health Access Backend.
All constants, environment loading, and system-wide settings.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def is_knowledge_graph_enabled() -> bool:
    """When False, skip KG initialization and all graph usage in caller/Twilio flows."""
    return os.getenv("ENABLE_KNOWLEDGE_GRAPH", "true").lower() in (
        "1",
        "true",
        "yes",
    )


# --- API Keys ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

# --- Database ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./telehealth.db")

# --- Redis (browser Web Speech transcript persistence; optional) ---
REDIS_URL = os.getenv("REDIS_URL", "")
BROWSER_STT_TTL_SECONDS = int(os.getenv("BROWSER_STT_TTL_SECONDS", "604800"))  # 7 days

# --- OpenAI (Whisper STT via /caller/stt) ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# --- Claude Models ---
CONVERSATION_MODEL = os.getenv("CONVERSATION_MODEL", "claude-sonnet-4-20250514")
TRANSLATION_MODEL = os.getenv("TRANSLATION_MODEL", "claude-haiku-4-5-20241022")
INTAKE_MODEL = os.getenv("INTAKE_MODEL", "claude-haiku-4-5-20241022")
INTAKE_MAX_TOKENS = 1024
CONVERSATION_MAX_TOKENS = 350

# --- ElevenLabs TTS ---
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "Xb7hH8MSUJpSbSDYk0k2")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_flash_v2_5")

# --- Triage Base Scores (START protocol) ---
TRIAGE_BASE_SCORES = {
    "RED": 100,
    "YELLOW": 50,
    "GREEN": 10,
    "BLACK": 0,
}

# --- Priority Queue Weights ---
WAIT_ESCALATION_PER_15MIN = 5
COUNTRY_MATCH_BONUS = 20
SPECIALTY_MATCH_BONUS = 15
FOLLOWUP_BONUS = 10

# --- Case Expiration ---
DOCTOR_RESPONSE_TIMEOUT_HOURS = 2
FOLLOWUP_HOURS = [24, 48]

# --- Conversation Flow ---
MAX_TURNS_BEFORE_COMPLETE = 8
MIN_SYMPTOMS_FOR_COMPLETE = 5
STALE_TURNS_FOR_COMPLETE = 2
GRAPH_CONFIDENCE_THRESHOLD = 0.7

# --- WHO GHO API ---
WHO_GHO_BASE_URL = "https://ghoapi.azureedge.net/api"
WHO_INDICATORS = {
    "physicians_per_10k": "HWF_0001",
    "hospital_beds_per_10k": "WHS6_102",
    "uhc_coverage_index": "UHC_SCI_CMPND",
}

# --- NLM ICD-11 API (no auth required) ---
NLM_ICD11_URL = "https://clinicaltables.nlm.nih.gov/api/icd11_codes/v3/search"
