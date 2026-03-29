"""
Translation Pipeline with Provenance — Phase 03.

Every translation produces a TranslationArtifact that preserves:
- original text and language
- translated text and target language
- method used (claude_haiku, claude_sonnet, heuristic, none)
- confidence score (0.0-1.0)
- clinically sensitive terms detected
- ambiguity flags

No translated text may exist without a provenance artifact.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class TranslationMethod(str, Enum):
    NONE = "none"                       # No translation needed (same language)
    CLAUDE_HAIKU = "claude_haiku"       # Fast translation via Haiku
    CLAUDE_SONNET = "claude_sonnet"     # High-quality translation via Sonnet
    HEURISTIC = "heuristic"             # Rule-based / fallback
    FAILED = "failed"                   # Translation attempted but failed


class AmbiguityFlag(str, Enum):
    LOW_DETECTION_CONFIDENCE = "low_language_detection_confidence"
    LOW_TRANSLATION_CONFIDENCE = "low_translation_confidence"
    COLLOQUIAL_TERM_UNRESOLVED = "colloquial_term_unresolved"
    CLINICALLY_SENSITIVE_UNCERTAIN = "clinically_sensitive_term_uncertain"
    CODE_SWITCHING_DETECTED = "code_switching_detected"
    TRANSCRIPT_LOW_CONFIDENCE = "transcript_low_confidence"
    SUMMARY_MAY_HAVE_LOST_DETAIL = "summary_may_have_lost_detail"
    NEGATION_UNCERTAIN = "negation_uncertain"
    DURATION_AMBIGUOUS = "duration_ambiguous"
    LATERALITY_AMBIGUOUS = "laterality_ambiguous"


# Clinically sensitive term categories where mistranslation matters most
SENSITIVE_CATEGORIES = {
    "pain_location": [
        "chest", "abdomen", "head", "back", "joint", "throat",
        "stomach", "side", "arm", "leg", "neck", "eye",
    ],
    "pain_intensity": [
        "severe", "mild", "moderate", "worst", "unbearable",
        "sharp", "dull", "stabbing", "burning", "throbbing",
        "excruciating", "aching", "cramping",
    ],
    "duration_timing": [
        "sudden", "gradual", "intermittent", "constant", "worsening",
        "improving", "recurring", "acute", "chronic",
        "hours", "days", "weeks", "months", "minutes",
    ],
    "laterality": [
        "left", "right", "both", "bilateral", "one side",
        "upper", "lower",
    ],
    "breathing": [
        "breathe", "breathing", "breath", "shortness", "wheeze",
        "gasp", "choking", "suffocating", "airway",
    ],
    "consciousness": [
        "conscious", "unconscious", "fainted", "dizzy", "confused",
        "alert", "responsive", "unresponsive", "drowsy", "lethargic",
    ],
    "bleeding": [
        "blood", "bleeding", "hemorrhage", "spotting", "clot",
    ],
    "pregnancy": [
        "pregnant", "pregnancy", "labor", "contraction", "miscarriage",
        "trimester", "morning sickness",
    ],
    "fever": [
        "fever", "temperature", "chills", "sweating", "hot", "cold",
    ],
    "dehydration": [
        "vomiting", "diarrhea", "thirsty", "dry mouth", "urination",
        "not eating", "not drinking",
    ],
}


@dataclass
class TranslationArtifact:
    """Provenance record for any translation operation."""
    original_text: str
    original_language: str
    translated_text: str
    target_language: str
    method: TranslationMethod = TranslationMethod.NONE
    confidence: float = 1.0
    sensitive_terms_detected: list[str] = field(default_factory=list)
    ambiguity_flags: list[str] = field(default_factory=list)
    back_translation: Optional[str] = None  # For verification if available

    def to_dict(self) -> dict:
        return {
            "original_text": self.original_text,
            "original_language": self.original_language,
            "translated_text": self.translated_text,
            "target_language": self.target_language,
            "method": self.method.value,
            "confidence": self.confidence,
            "sensitive_terms_detected": self.sensitive_terms_detected,
            "ambiguity_flags": self.ambiguity_flags,
        }

    @property
    def is_low_confidence(self) -> bool:
        return self.confidence < 0.7

    @property
    def has_clinical_ambiguity(self) -> bool:
        clinical_flags = {
            AmbiguityFlag.CLINICALLY_SENSITIVE_UNCERTAIN.value,
            AmbiguityFlag.NEGATION_UNCERTAIN.value,
            AmbiguityFlag.LATERALITY_AMBIGUOUS.value,
        }
        return bool(set(self.ambiguity_flags) & clinical_flags)


@dataclass
class LanguageDetectionResult:
    """Result of language detection with confidence."""
    language_code: str
    confidence: float  # 0.0-1.0
    method: str  # "script", "phrase_hint", "whisper", "default"
    is_code_switched: bool = False
    secondary_language: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "language_code": self.language_code,
            "confidence": self.confidence,
            "method": self.method,
            "is_code_switched": self.is_code_switched,
            "secondary_language": self.secondary_language,
        }


def detect_sensitive_terms(text: str) -> list[str]:
    """Detect clinically sensitive terms in text that need careful translation."""
    found = []
    lower = text.lower()
    for category, terms in SENSITIVE_CATEGORIES.items():
        for term in terms:
            if term in lower:
                found.append(f"{category}:{term}")
    return found


def detect_code_switching(text: str) -> tuple[bool, Optional[str]]:
    """
    Detect if text contains multiple languages (code-switching).
    Returns (is_code_switched, secondary_language).
    """
    from services.language_service import _SCRIPT_PATTERNS, _PHRASE_HINTS

    detected_scripts = set()
    for pattern, lang in _SCRIPT_PATTERNS:
        if pattern.search(text):
            detected_scripts.add(lang)

    # Latin-script languages detected by phrases
    latin_langs = set()
    lower = text.lower()
    for phrase, lang in _PHRASE_HINTS.items():
        if phrase in lower and lang not in detected_scripts:
            latin_langs.add(lang)

    all_langs = detected_scripts | latin_langs
    if len(all_langs) > 1:
        langs = list(all_langs)
        return True, langs[1] if len(langs) > 1 else None
    return False, None


def detect_language_with_confidence(text: str, whisper_lang: str = None,
                                     whisper_confidence: float = None) -> LanguageDetectionResult:
    """
    Enhanced language detection that returns confidence scores.
    Combines heuristic detection with optional Whisper ASR metadata.
    """
    from services.language_service import detect_language, _SCRIPT_PATTERNS, _PHRASE_HINTS

    if not text or not text.strip():
        return LanguageDetectionResult("en", 0.5, "default")

    # Check code switching first
    is_code_switched, secondary = detect_code_switching(text)

    # If Whisper provided a language, trust it with its confidence
    if whisper_lang and whisper_confidence:
        return LanguageDetectionResult(
            language_code=whisper_lang,
            confidence=whisper_confidence,
            method="whisper",
            is_code_switched=is_code_switched,
            secondary_language=secondary,
        )

    # Script detection — high confidence
    for pattern, lang in _SCRIPT_PATTERNS:
        if pattern.search(text.strip()):
            return LanguageDetectionResult(
                language_code=lang,
                confidence=0.9,
                method="script",
                is_code_switched=is_code_switched,
                secondary_language=secondary,
            )

    # Phrase hint — moderate confidence
    lower = text.strip().lower()
    for phrase, lang in _PHRASE_HINTS.items():
        if phrase in lower:
            return LanguageDetectionResult(
                language_code=lang,
                confidence=0.75,
                method="phrase_hint",
                is_code_switched=is_code_switched,
                secondary_language=secondary,
            )

    # Default English — lower confidence
    return LanguageDetectionResult(
        language_code="en",
        confidence=0.5,
        method="default",
        is_code_switched=is_code_switched,
        secondary_language=secondary,
    )


def translate_with_provenance(
    text: str,
    source_lang: str,
    target_lang: str,
    context: str = "medical_intake",
) -> TranslationArtifact:
    """
    Translate text with full provenance tracking.
    Returns a TranslationArtifact that preserves original text and metadata.
    """
    # No translation needed
    if source_lang == target_lang or not text.strip():
        return TranslationArtifact(
            original_text=text,
            original_language=source_lang,
            translated_text=text,
            target_language=target_lang,
            method=TranslationMethod.NONE,
            confidence=1.0,
        )

    # Detect sensitive terms in original
    sensitive = detect_sensitive_terms(text)
    ambiguity = []

    if source_lang == "en":
        # English to other language
        from services.language_service import translate_from_english
        translated = translate_from_english(text, target_lang)
        method = TranslationMethod.CLAUDE_HAIKU
    else:
        # Other language to English
        from services.language_service import translate_to_english
        translated = translate_to_english(text, source_lang)
        method = TranslationMethod.CLAUDE_HAIKU

    # Check if translation actually changed the text
    if translated == text:
        # Translation returned original — likely failed silently
        method = TranslationMethod.FAILED
        ambiguity.append(AmbiguityFlag.LOW_TRANSLATION_CONFIDENCE.value)
        confidence = 0.3
    else:
        confidence = 0.8  # Default Claude translation confidence

        # Check if sensitive terms are preserved in translation
        if sensitive:
            translated_sensitive = detect_sensitive_terms(translated)
            original_categories = {s.split(":")[0] for s in sensitive}
            translated_categories = {s.split(":")[0] for s in translated_sensitive}
            missing = original_categories - translated_categories
            if missing:
                ambiguity.append(AmbiguityFlag.CLINICALLY_SENSITIVE_UNCERTAIN.value)
                confidence -= 0.15 * len(missing)

        # Check for negation patterns that might flip meaning
        negation_patterns = [r"\bnot\b", r"\bno\b", r"\bnever\b", r"\bdon't\b", r"\bcan't\b"]
        original_negations = sum(1 for p in negation_patterns if re.search(p, text, re.I))
        translated_negations = sum(1 for p in negation_patterns if re.search(p, translated, re.I))
        if abs(original_negations - translated_negations) > 0 and source_lang != "en":
            ambiguity.append(AmbiguityFlag.NEGATION_UNCERTAIN.value)
            confidence -= 0.1

    confidence = max(0.1, min(1.0, confidence))

    return TranslationArtifact(
        original_text=text,
        original_language=source_lang,
        translated_text=translated,
        target_language=target_lang,
        method=method,
        confidence=confidence,
        sensitive_terms_detected=sensitive,
        ambiguity_flags=ambiguity,
    )
