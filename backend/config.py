"""
Configuration for the WHO-aligned AI Health Access Backend.
All constants, environment loading, and system-wide settings.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

# --- Database ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./telehealth.db")

# --- Claude Model ---
INTAKE_MODEL = "claude-haiku-4-5-20241022"
INTAKE_MAX_TOKENS = 1024

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

# --- WHO GHO API ---
WHO_GHO_BASE_URL = "https://ghoapi.azureedge.net/api"
WHO_INDICATORS = {
    "physicians_per_10k": "HWF_0001",
    "hospital_beds_per_10k": "WHS6_102",
    "uhc_coverage_index": "UHC_SCI_CMPND",
}

# --- NLM ICD-11 API (no auth required) ---
NLM_ICD11_URL = "https://clinicaltables.nlm.nih.gov/api/icd11_codes/v3/search"
