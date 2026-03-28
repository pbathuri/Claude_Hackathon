"""
Language Service — Detection, translation, and multilingual conversation support.

Provides:
1. Language detection from user text (fast heuristic + Claude fallback)
2. Translation to English for KG traversal / clinical processing
3. Translation FROM English back to user's language for responses
4. Language-aware prompt generation

All clinical processing (KG navigation, ICD-11 mapping, triage) runs in English.
User-facing messages are translated to/from the detected language transparently.
"""

import logging
import os
import re
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Supported languages with metadata ────────────────────────────────────────
# ISO 639-1 → display name, Whisper code, Twilio/Polly voice, ElevenLabs model support
SUPPORTED_LANGUAGES = {
    "en": {
        "name": "English",
        "whisper": "en",
        "twilio_voice": "Polly.Joanna",
        "twilio_lang": "en-US",
        "greeting": "Hello! Welcome to the WHO Health Access Service.",
        "emergency_notice": "Please call emergency services immediately.",
    },
    "es": {
        "name": "Spanish",
        "whisper": "es",
        "twilio_voice": "Polly.Lupe",
        "twilio_lang": "es-US",
        "greeting": "¡Hola! Bienvenido al Servicio de Acceso a la Salud de la OMS.",
        "emergency_notice": "Por favor llame a los servicios de emergencia inmediatamente.",
    },
    "fr": {
        "name": "French",
        "whisper": "fr",
        "twilio_voice": "Polly.Lea",
        "twilio_lang": "fr-FR",
        "greeting": "Bonjour ! Bienvenue au Service d'Accès à la Santé de l'OMS.",
        "emergency_notice": "Veuillez appeler les services d'urgence immédiatement.",
    },
    "hi": {
        "name": "Hindi",
        "whisper": "hi",
        "twilio_voice": "Polly.Aditi",
        "twilio_lang": "hi-IN",
        "greeting": "नमस्ते! WHO स्वास्थ्य सेवा में आपका स्वागत है।",
        "emergency_notice": "कृपया तुरंत आपातकालीन सेवाओं को कॉल करें।",
    },
    "pt": {
        "name": "Portuguese",
        "whisper": "pt",
        "twilio_voice": "Polly.Camila",
        "twilio_lang": "pt-BR",
        "greeting": "Olá! Bem-vindo ao Serviço de Acesso à Saúde da OMS.",
        "emergency_notice": "Por favor, ligue para os serviços de emergência imediatamente.",
    },
    "ar": {
        "name": "Arabic",
        "whisper": "ar",
        "twilio_voice": "Polly.Zeina",
        "twilio_lang": "arb",
        "greeting": "مرحباً! أهلاً بك في خدمة الوصول الصحي لمنظمة الصحة العالمية.",
        "emergency_notice": "يرجى الاتصال بخدمات الطوارئ فوراً.",
    },
    "sw": {
        "name": "Swahili",
        "whisper": "sw",
        "twilio_voice": "Polly.Joanna",  # fallback to English voice
        "twilio_lang": "en-US",  # Twilio lacks Swahili; use English STT + translate
        "greeting": "Habari! Karibu kwenye Huduma ya Afya ya WHO.",
        "emergency_notice": "Tafadhali piga simu huduma za dharura mara moja.",
    },
    "yo": {
        "name": "Yoruba",
        "whisper": "yo",
        "twilio_voice": "Polly.Joanna",
        "twilio_lang": "en-US",
        "greeting": "Ẹ kú àárọ̀! Ẹ kú àbọ̀ sí Iṣẹ́ Ìlera WHO.",
        "emergency_notice": "Jọwọ pe awọn iṣẹ pajawiri lẹsẹkẹsẹ.",
    },
    "ha": {
        "name": "Hausa",
        "whisper": "ha",
        "twilio_voice": "Polly.Joanna",
        "twilio_lang": "en-US",
        "greeting": "Sannu! Barka da zuwa sabis na kiwon lafiya na WHO.",
        "emergency_notice": "Da fatan za a kira sabis na gaggawa nan da nan.",
    },
    "zh": {
        "name": "Chinese",
        "whisper": "zh",
        "twilio_voice": "Polly.Zhiyu",
        "twilio_lang": "zh-CN",
        "greeting": "你好！欢迎使用世界卫生组织健康服务。",
        "emergency_notice": "请立即拨打急救电话。",
    },
    "de": {
        "name": "German",
        "whisper": "de",
        "twilio_voice": "Polly.Vicki",
        "twilio_lang": "de-DE",
        "greeting": "Hallo! Willkommen beim WHO-Gesundheitsdienst.",
        "emergency_notice": "Bitte rufen Sie sofort den Notdienst an.",
    },
    "tl": {
        "name": "Filipino",
        "whisper": "tl",
        "twilio_voice": "Polly.Joanna",
        "twilio_lang": "en-US",
        "greeting": "Kamusta! Maligayang pagdating sa WHO Health Access Service.",
        "emergency_notice": "Mangyaring tumawag sa mga serbisyong pang-emergency kaagad.",
    },
}

# Quick character-set heuristics for common scripts (avoids API call)
_SCRIPT_PATTERNS = [
    (re.compile(r"[\u0900-\u097F]"), "hi"),       # Devanagari → Hindi
    (re.compile(r"[\u0600-\u06FF]"), "ar"),        # Arabic script
    (re.compile(r"[\u4E00-\u9FFF]"), "zh"),        # CJK → Chinese
    (re.compile(r"[àâçéèêëîïôùûüÿæœ]", re.I), "fr"),  # French diacritics
    (re.compile(r"[áéíóúñ¿¡]", re.I), "es"),       # Spanish
    (re.compile(r"[ãõçâê]", re.I), "pt"),           # Portuguese
    (re.compile(r"[äöüß]", re.I), "de"),            # German
    (re.compile(r"[Ẹẹọ́ọ̀Ṣṣ]"), "yo"),              # Yoruba
]

# Common non-English phrases for fast detection
_PHRASE_HINTS = {
    "hola": "es", "buenos días": "es", "tengo": "es", "dolor": "es", "fiebre": "es",
    "bonjour": "fr", "j'ai": "fr", "mal à": "fr", "fièvre": "fr", "douleur": "fr",
    "namaste": "hi", "mujhe": "hi", "dard": "hi", "bukhar": "hi",
    "olá": "pt", "tenho": "pt", "dor": "pt", "febre": "pt",
    "مرحبا": "ar", "ألم": "ar", "حمى": "ar",
    "你好": "zh", "疼": "zh", "发烧": "zh", "头疼": "zh",
    "habari": "sw", "maumivu": "sw", "homa": "sw",
    "sannu": "ha", "ciwon": "ha", "zazzabi": "ha",
}


def detect_language(text: str) -> str:
    """
    Detect language from user text.

    Strategy (fast → slow):
    1. Script-based heuristic (instant — catches Arabic, Hindi, Chinese, etc.)
    2. Phrase-hint lookup (instant — catches common non-English medical terms)
    3. Defaults to "en" (the Claude translation step will catch misdetections)

    Returns ISO 639-1 code.
    """
    if not text or not text.strip():
        return "en"

    text_stripped = text.strip()

    # 1. Script detection (catches non-Latin scripts instantly)
    for pattern, lang in _SCRIPT_PATTERNS:
        if pattern.search(text_stripped):
            logger.info("[Lang] Script-detected: %s", lang)
            return lang

    # 2. Phrase hint lookup
    text_lower = text_stripped.lower()
    for phrase, lang in _PHRASE_HINTS.items():
        if phrase in text_lower:
            logger.info("[Lang] Phrase-detected '%s' → %s", phrase, lang)
            return lang

    # 3. Default to English
    return "en"


def get_language_config(lang_code: str) -> dict:
    """Get full language config, falling back to English for unsupported languages."""
    return SUPPORTED_LANGUAGES.get(lang_code, SUPPORTED_LANGUAGES["en"])


# ─── Translation via Claude ───────────────────────────────────────────────────

_anthropic_client = None


def _get_client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )
    return _anthropic_client


def translate_to_english(text: str, source_lang: str) -> str:
    """
    Translate user text to English for KG traversal and clinical processing.
    Returns original text if already English or translation fails.
    """
    if source_lang == "en" or not text.strip():
        return text

    lang_name = SUPPORTED_LANGUAGES.get(source_lang, {}).get("name", source_lang)

    try:
        client = _get_client()
        resp = client.messages.create(
            model="claude-haiku-4-5-20241022",  # fast + cheap for translation
            max_tokens=500,
            system=(
                "You are a medical translator. Translate the patient's message "
                "from {lang} to English accurately. Preserve medical terminology. "
                "Output ONLY the English translation, nothing else."
            ).format(lang=lang_name),
            messages=[{"role": "user", "content": text}],
        )
        translated = resp.content[0].text.strip()
        logger.info("[Lang] Translated %s→en: '%s' → '%s'",
                    source_lang, text[:60], translated[:60])
        return translated
    except Exception as exc:
        logger.warning("[Lang] Translation %s→en failed: %s — using original", source_lang, exc)
        return text


def translate_from_english(text: str, target_lang: str) -> str:
    """
    Translate English AI response to the user's language.
    Returns original text if target is English or translation fails.
    """
    if target_lang == "en" or not text.strip():
        return text

    lang_name = SUPPORTED_LANGUAGES.get(target_lang, {}).get("name", target_lang)

    try:
        client = _get_client()
        resp = client.messages.create(
            model="claude-haiku-4-5-20241022",
            max_tokens=600,
            system=(
                "You are a medical translator. Translate the health assistant's "
                "message from English to {lang}. Use simple, empathetic language "
                "appropriate for a patient. Preserve any medical terms the patient "
                "would understand. Output ONLY the {lang} translation, nothing else."
            ).format(lang=lang_name),
            messages=[{"role": "user", "content": text}],
        )
        translated = resp.content[0].text.strip()
        logger.info("[Lang] Translated en→%s: '%s' → '%s'",
                    target_lang, text[:60], translated[:60])
        return translated
    except Exception as exc:
        logger.warning("[Lang] Translation en→%s failed: %s — using English", target_lang, exc)
        return text


def translate_disclosure(disclosure_script: str, target_lang: str) -> str:
    """
    Translate the verbal disclosure / disclaimer to the user's language.
    This is critical for informed consent — we use a higher-quality translation.
    """
    if target_lang == "en" or not disclosure_script.strip():
        return disclosure_script

    lang_name = SUPPORTED_LANGUAGES.get(target_lang, {}).get("name", target_lang)

    try:
        client = _get_client()
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",  # higher quality for legal/consent text
            max_tokens=800,
            system=(
                "You are a certified medical-legal translator. Translate this "
                "patient consent disclosure from English to {lang}. "
                "This is a legally significant document — accuracy is critical. "
                "Use clear, simple language a patient would understand. "
                "Output ONLY the {lang} translation."
            ).format(lang=lang_name),
            messages=[{"role": "user", "content": disclosure_script}],
        )
        return resp.content[0].text.strip()
    except Exception as exc:
        logger.warning("[Lang] Disclosure translation failed: %s — using English", exc)
        return disclosure_script


# ─── Emergency numbers by country ─────────────────────────────────────────────

EMERGENCY_NUMBERS = {
    "IN": {"number": "112", "name": "India Emergency"},
    "NG": {"number": "112", "name": "Nigeria Emergency"},
    "KE": {"number": "999", "name": "Kenya Emergency"},
    "PH": {"number": "911", "name": "Philippines Emergency"},
    "US": {"number": "911", "name": "US Emergency"},
    "GB": {"number": "999", "name": "UK Emergency"},
    "BR": {"number": "192", "name": "SAMU Brazil"},
    "MX": {"number": "911", "name": "Mexico Emergency"},
    "ZA": {"number": "10177", "name": "South Africa Emergency"},
    "GH": {"number": "112", "name": "Ghana Emergency"},
    "ET": {"number": "911", "name": "Ethiopia Emergency"},
    "TZ": {"number": "114", "name": "Tanzania Emergency"},
    "UG": {"number": "999", "name": "Uganda Emergency"},
    "EG": {"number": "123", "name": "Egypt Emergency"},
    "DE": {"number": "112", "name": "Germany Emergency"},
    "FR": {"number": "15", "name": "SAMU France"},
    "ES": {"number": "112", "name": "Spain Emergency"},
    "SA": {"number": "997", "name": "Saudi Arabia Emergency"},
    "AE": {"number": "998", "name": "UAE Emergency"},
    "PK": {"number": "1122", "name": "Pakistan Emergency"},
    "BD": {"number": "999", "name": "Bangladesh Emergency"},
    "CN": {"number": "120", "name": "China Emergency"},
}

# Fallback
_DEFAULT_EMERGENCY = {"number": "112", "name": "Emergency Services"}


def get_emergency_number(country_code: str) -> dict:
    """Get emergency number for a country code."""
    return EMERGENCY_NUMBERS.get(country_code, _DEFAULT_EMERGENCY)


def build_emergency_message(country_code: str, lang_code: str, flags: list[str]) -> str:
    """Build a localized emergency message with the correct local number."""
    emerg = get_emergency_number(country_code)
    lang_cfg = get_language_config(lang_code)
    flags_str = ", ".join(flags) if flags else "critical symptoms"

    # English base message
    msg = (
        f"I'm detecting potential emergency indicators: {flags_str}. "
        f"Please call {emerg['name']} at {emerg['number']} immediately. "
        "Do not wait — your safety is the priority."
    )

    if lang_code != "en":
        msg = translate_from_english(msg, lang_code)

    return msg
