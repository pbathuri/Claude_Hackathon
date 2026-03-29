"""
Patient-Facing Copy System — Phase 02.

Centralizes all patient-facing text for localization readability.
All strings are:
- Short sentences
- Non-diagnostic
- Low-literacy-friendly
- Culturally neutral
- Resilient to machine translation (no idioms, no double negatives)

Usage:
    from services.patient_copy import get_copy
    msg = get_copy("disclosure_intro", "es")  # Returns Spanish version
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── English source strings (single source of truth) ──────────────────────
# Keys are functional IDs. Values are plain English suitable for translation.

COPY_EN = {
    # ── Disclosure / Consent ──
    "disclosure_intro": (
        "Before we begin, I need to tell you something important."
    ),
    "disclosure_not_doctor": (
        "This service uses a computer to help collect your health information. "
        "It is not a doctor. It cannot diagnose you or prescribe medicine."
    ),
    "disclosure_purpose": (
        "Your answers will be shared with a real doctor who will review them. "
        "The doctor will give you health guidance."
    ),
    "disclosure_consent_ask": (
        "Do you agree to continue? You can stop at any time."
    ),
    "disclosure_emergency": (
        "If you are having a medical emergency right now, please hang up and call {emergency_number}."
    ),

    # ── Greeting / Start ──
    "greeting": (
        "Hello. I am here to help collect information about your health. "
        "Please tell me what is bothering you."
    ),
    "greeting_language_confirm": (
        "I will try to speak with you in {language_name}. "
        "If I make a mistake, please tell me."
    ),

    # ── During conversation ──
    "ask_main_symptom": "What is the main problem you are having today?",
    "ask_duration": "How long have you had this problem?",
    "ask_severity": "On a scale of 1 to 10, how bad is it? 1 is very mild. 10 is the worst.",
    "ask_other_symptoms": "Do you have any other symptoms?",
    "ask_medications": "Are you taking any medicines right now?",
    "ask_allergies": "Are you allergic to anything?",
    "ask_medical_history": "Have you had any serious health problems before?",

    # ── Clarification (when translation is uncertain) ──
    "clarify_not_understood": (
        "I want to make sure I understand you correctly. "
        "Can you say that again in a different way?"
    ),
    "clarify_pain_location": "Can you point to or describe exactly where it hurts?",
    "clarify_pain_type": "What does the pain feel like? Is it sharp, dull, burning, or something else?",
    "clarify_timing": "Did this start suddenly, or has it been getting worse slowly?",
    "clarify_yes_no": "I need a simple answer. Is it yes or no?",

    # ── Emergency ──
    "emergency_detected": (
        "What you are describing sounds serious. "
        "Please call {emergency_number} right now. "
        "Do not wait."
    ),
    "emergency_call_action": "Call {emergency_number} now.",
    "emergency_stay_safe": "Stay where you are. Help is available.",
    "emergency_someone_with_you": "Is there someone with you who can help?",

    # ── Completion ──
    "intake_complete": (
        "Thank you. I have collected your health information. "
        "A doctor will review it soon."
    ),
    "intake_complete_timeline": (
        "You should hear back within {timeframe}. "
        "If your symptoms get worse before then, please call {emergency_number}."
    ),
    "intake_complete_case_id": "Your case number is {case_id}.",

    # ── Follow-up ──
    "followup_greeting": "Hello. We are checking on you after your visit.",
    "followup_how_feeling": "How are you feeling now?",
    "followup_option_better": "Reply 1 if you are feeling better.",
    "followup_option_same": "Reply 2 if you feel about the same.",
    "followup_option_worse": "Reply 3 if you are feeling worse.",
    "followup_worse_action": (
        "We are sorry you are not feeling better. "
        "A doctor will contact you soon. "
        "If this is an emergency, call {emergency_number}."
    ),
    "followup_better_response": "We are glad you are feeling better. Take care.",
    "followup_same_response": (
        "Thank you for letting us know. "
        "Please continue to rest and take any medicines your doctor recommended. "
        "If you get worse, reply 3 or call {emergency_number}."
    ),

    # ── Error / Retry ──
    "error_general": "Something went wrong. Please try again.",
    "error_could_not_hear": "I could not hear you clearly. Can you please repeat that?",
    "error_connection": "We are having a connection problem. Please wait a moment.",
    "error_unsupported_language": (
        "I am sorry, I may not be able to understand your language well. "
        "I will do my best. If this is an emergency, call {emergency_number}."
    ),

    # ── Waiting ──
    "waiting_processing": "Please wait while I process your information.",
    "waiting_doctor_review": "A doctor is reviewing your case. Please be patient.",
    "waiting_still_here": "I am still here. Take your time.",

    # ── Upload instructions ──
    "upload_photo_prompt": (
        "If you can take a photo of the affected area, it will help the doctor. "
        "You can send it now or skip this step."
    ),
    "upload_success": "Photo received. Thank you.",
    "upload_skip": "No problem. We will continue without a photo.",
}

# ── Pre-translated versions for supported languages ──────────────────────
# These are curated translations for critical strings (emergency, consent).
# Non-critical strings fall back to runtime Claude translation.

COPY_CURATED = {
    "es": {
        "emergency_detected": (
            "Lo que describe suena grave. "
            "Llame al {emergency_number} ahora mismo. "
            "No espere."
        ),
        "emergency_call_action": "Llame al {emergency_number} ahora.",
        "disclosure_not_doctor": (
            "Este servicio usa una computadora para recoger su información de salud. "
            "No es un doctor. No puede diagnosticar ni recetar medicinas."
        ),
        "followup_option_better": "Responda 1 si se siente mejor.",
        "followup_option_same": "Responda 2 si se siente igual.",
        "followup_option_worse": "Responda 3 si se siente peor.",
    },
    "fr": {
        "emergency_detected": (
            "Ce que vous décrivez semble grave. "
            "Appelez le {emergency_number} maintenant. "
            "N'attendez pas."
        ),
        "emergency_call_action": "Appelez le {emergency_number} maintenant.",
    },
    "hi": {
        "emergency_detected": (
            "आप जो बता रहे हैं वह गंभीर लगता है। "
            "कृपया अभी {emergency_number} पर कॉल करें। "
            "इंतजार न करें।"
        ),
        "emergency_call_action": "अभी {emergency_number} पर कॉल करें।",
    },
    "sw": {
        "emergency_detected": (
            "Unachokieleza kinaonekana ni hatari. "
            "Tafadhali piga simu {emergency_number} sasa hivi. "
            "Usisubiri."
        ),
        "emergency_call_action": "Piga simu {emergency_number} sasa.",
    },
    "ar": {
        "emergency_detected": (
            "ما تصفه يبدو خطيراً. "
            "اتصل بـ {emergency_number} الآن. "
            "لا تنتظر."
        ),
    },
}


def get_copy(
    key: str,
    lang: str = "en",
    **format_args,
) -> str:
    """
    Get patient-facing copy in the specified language.

    Lookup order:
    1. Curated translation for this language + key
    2. English source with runtime translation
    3. English source as final fallback

    Format args (e.g., emergency_number, case_id) are applied after translation.
    """
    # 1. Check curated translations first
    if lang != "en" and lang in COPY_CURATED:
        curated = COPY_CURATED[lang].get(key)
        if curated:
            try:
                return curated.format(**format_args) if format_args else curated
            except KeyError:
                return curated

    # 2. Get English source
    english = COPY_EN.get(key)
    if not english:
        logger.warning("[PatientCopy] Unknown copy key: %s", key)
        return key

    # 3. If English requested, just format and return
    if lang == "en":
        try:
            return english.format(**format_args) if format_args else english
        except KeyError:
            return english

    # 4. Runtime translation for non-curated strings
    # Apply format args BEFORE translation so the template vars survive
    try:
        formatted_en = english.format(**format_args) if format_args else english
    except KeyError:
        formatted_en = english

    try:
        from services.language_service import translate_from_english
        translated = translate_from_english(formatted_en, lang)
        return translated
    except Exception as exc:
        logger.warning("[PatientCopy] Translation failed for '%s' to %s: %s", key, lang, exc)
        return formatted_en


def get_all_keys() -> list[str]:
    """Return all available copy keys."""
    return list(COPY_EN.keys())
