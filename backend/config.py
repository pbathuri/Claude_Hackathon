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
def _normalize_database_url(url: str) -> str:
    """Render/Heroku sometimes provide postgres://; SQLAlchemy expects postgresql://."""
    u = url.strip()
    if u.startswith("postgres://"):
        return u.replace("postgres://", "postgresql://", 1)
    return u


def _validate_database_url(url: str) -> None:
    """
    Catch common misconfiguration: Supabase/API HTTPS URL instead of Postgres URI.
    Correct form: postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
    """
    if not url:
        return
    lower = url.lower()
    if lower.startswith(("http://", "https://")):
        raise ValueError(
            "DATABASE_URL must be the PostgreSQL connection string (postgresql://... or postgres://...), "
            "not the Supabase REST URL (https://....supabase.co). "
            "In Supabase Dashboard: Project Settings → Database → Connection string → URI "
            "(use 'Transaction' or 'Session' mode; add ?sslmode=require if required)."
        )
    if ("supabase.co" in lower or "supabase.com" in lower) and not (
        lower.startswith("postgresql") or lower.startswith("postgres://")
    ):
        raise ValueError(
            "DATABASE_URL for Supabase must be the Postgres URI (postgres:// or postgresql://), "
            "not https://."
        )


_raw_db_url = os.getenv("DATABASE_URL", "sqlite:///./telehealth.db").strip()
if _raw_db_url and not _raw_db_url.startswith("sqlite"):
    _validate_database_url(_raw_db_url)
DATABASE_URL = _normalize_database_url(_raw_db_url)

# Twilio REST: accept TWILIO_API_KEY as alias when users name the secret that way in hosting UIs
TWILIO_API_KEY_SECRET = os.getenv("TWILIO_API_KEY_SECRET", "") or os.getenv("TWILIO_API_KEY", "")

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
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

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
