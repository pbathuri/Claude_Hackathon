"""
Clinician Explainability Model — Phase 04.

Builds the doctor-facing evidence package for each case.
Separates information into distinct layers:

1. Language/Communication Layer — language detected, translation status, risk level
2. Raw Patient Evidence — original text, timestamps, channel
3. Translation Layer — translated text, confidence, ambiguity flags
4. Structured Extraction — symptoms, severity, duration with source attribution
5. Rule/Safety Layer — what rules fired, what signals influenced urgency
6. Unresolved Ambiguity — what the system could not determine safely

Each layer is independently inspectable. Nothing is hidden.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def build_language_banner(
    patient_language: str,
    detected_languages: list[str] | None = None,
    translation_used: bool = False,
    code_switching: bool = False,
    translation_confidence: float = 1.0,
    detection_method: str = "default",
) -> dict:
    """
    Build the language/communication banner for the doctor portal.
    Shows at the top of case detail when translation was involved.
    """
    from services.language_service import SUPPORTED_LANGUAGES

    lang_config = SUPPORTED_LANGUAGES.get(patient_language, {})
    lang_name = lang_config.get("name", patient_language.upper())

    # Determine risk level
    if not translation_used:
        risk_level = "none"
        risk_label = "No translation used"
    elif translation_confidence >= 0.8:
        risk_level = "low"
        risk_label = "Translation appears reliable"
    elif translation_confidence >= 0.6:
        risk_level = "medium"
        risk_label = "Translation may contain inaccuracies"
    else:
        risk_level = "high"
        risk_label = "Translation confidence is low — verify with patient"

    if code_switching:
        risk_level = "medium" if risk_level == "low" else risk_level
        risk_label += " | Code-switching detected"

    return {
        "patient_language": patient_language,
        "patient_language_name": lang_name,
        "detected_languages": detected_languages or [patient_language],
        "translation_used": translation_used,
        "code_switching_detected": code_switching,
        "translation_confidence": round(translation_confidence, 2),
        "detection_method": detection_method,
        "risk_level": risk_level,  # none | low | medium | high
        "risk_label": risk_label,
        "interpreter_recommended": risk_level == "high" or code_switching,
    }


def build_patient_evidence(
    conversation_turns: list[dict],
    patient_language: str = "en",
) -> list[dict]:
    """
    Build the raw patient evidence layer.
    Shows original patient utterances with timestamps and channel info.
    Only includes patient turns, not AI turns.
    """
    evidence = []
    for turn in conversation_turns:
        if turn.get("role") not in ("user", "patient", "human"):
            continue

        entry = {
            "turn_number": turn.get("turn_number", len(evidence) + 1),
            "original_text": turn.get("original_text") or turn.get("content", ""),
            "language": turn.get("language", patient_language),
            "timestamp": turn.get("timestamp"),
            "channel": turn.get("source_channel", "unknown"),
            "label": "Original patient statement",
        }

        # If we have a translation, include it as a separate clearly-labeled field
        english_text = turn.get("english_translation") or turn.get("translated_text")
        if english_text and english_text != entry["original_text"]:
            entry["english_translation"] = english_text
            entry["translation_label"] = "System-translated to English"
            entry["translation_confidence"] = turn.get("translation_confidence", 0.8)

        evidence.append(entry)

    return evidence


def build_extraction_layer(
    extracted_facts: list[dict],
    symptoms: list[str] | None = None,
    severity: int | None = None,
    duration: str = "",
    body_area: str = "",
    medications: list[str] | None = None,
    allergies: list[str] | None = None,
) -> dict:
    """
    Build the structured extraction layer.
    Each extracted item has source attribution.
    """
    items = []

    # Add symptoms with source
    for symptom in (symptoms or []):
        # Find matching fact for attribution
        source_turn = None
        for fact in extracted_facts:
            if fact.get("fact_type") == "symptom" and fact.get("value", "").lower() == symptom.lower():
                source_turn = fact.get("turn_number")
                break

        items.append({
            "type": "symptom",
            "value": symptom,
            "source": "patient_reported" if source_turn else "ai_extracted",
            "source_turn": source_turn,
            "confidence": 0.9 if source_turn else 0.7,
            "label": "AI-extracted" if not source_turn else "Patient-reported",
        })

    if severity is not None:
        items.append({
            "type": "severity",
            "value": str(severity),
            "display": f"{severity}/10",
            "source": "patient_reported",
            "label": "Patient-reported severity",
        })

    if duration:
        items.append({
            "type": "duration",
            "value": duration,
            "source": "patient_reported",
            "label": "Patient-reported duration",
        })

    if body_area:
        items.append({
            "type": "body_area",
            "value": body_area,
            "source": "ai_extracted",
            "label": "AI-identified body area",
        })

    for med in (medications or []):
        items.append({"type": "medication", "value": med, "source": "patient_reported"})

    for allergy in (allergies or []):
        items.append({"type": "allergy", "value": allergy, "source": "patient_reported"})

    return {
        "items": items,
        "total_facts": len(items),
        "ai_extracted_count": sum(1 for i in items if i.get("source") == "ai_extracted"),
        "patient_reported_count": sum(1 for i in items if i.get("source") == "patient_reported"),
        "label": "Structured clinical data (AI-assisted extraction from patient conversation)",
    }


def build_safety_layer(
    triage_level: str,
    triage_breakdown: dict | None = None,
    red_flags: list[str | dict] | None = None,
    emergency_detected: bool = False,
    kg_insights: dict | None = None,
) -> dict:
    """
    Build the safety/rule-trigger layer.
    Shows what rules fired and what signals influenced urgency.
    """
    triggers = []

    if emergency_detected:
        triggers.append({
            "rule": "emergency_detection",
            "severity": "immediate",
            "description": "Emergency keywords detected in patient text",
        })

    for flag in (red_flags or []):
        if isinstance(flag, dict):
            triggers.append({
                "rule": flag.get("rule", "red_flag_rule"),
                "severity": flag.get("severity", "warning"),
                "description": f"Red flag: {flag.get('matched_text', flag.get('flag', 'unknown'))}",
                "layer": flag.get("layer", "keyword"),
            })
        else:
            triggers.append({
                "rule": "red_flag_keyword",
                "severity": "warning",
                "description": f"Red flag indicator: {flag}",
            })

    return {
        "triage_level": triage_level,
        "triage_breakdown": triage_breakdown,
        "triggers": triggers,
        "trigger_count": len(triggers),
        "emergency_detected": emergency_detected,
        "kg_confidence": kg_insights.get("graph_confidence", 0) if kg_insights else 0,
        "label": "Safety signals and rule triggers (deterministic, not AI opinion)",
    }


def build_ambiguity_block(
    translation_artifacts: list[dict] | None = None,
    uncertainty_state: str = "confident",
    warnings: list[str] | None = None,
) -> dict:
    """
    Build the unresolved ambiguity block.
    Surfaces what the system could NOT determine safely.
    """
    unresolved = []

    for artifact in (translation_artifacts or []):
        for flag in artifact.get("ambiguity_flags", []):
            unresolved.append({
                "type": "translation",
                "flag": flag,
                "context": f"Original: '{artifact.get('original_text', '')[:80]}...'",
            })

    if uncertainty_state != "confident":
        unresolved.append({
            "type": "system",
            "flag": uncertainty_state,
            "context": "Overall case assessment uncertainty",
        })

    for w in (warnings or []):
        unresolved.append({
            "type": "guard",
            "flag": "conversation_warning",
            "context": w,
        })

    return {
        "unresolved_items": unresolved,
        "has_unresolved": len(unresolved) > 0,
        "count": len(unresolved),
        "label": "Unresolved ambiguities — items the system could not determine safely",
    }


def build_case_explainability(
    case_data: dict,
    intake_data: dict | None = None,
    conversation_log: dict | None = None,
    triage_breakdown: dict | None = None,
) -> dict:
    """
    Build the complete explainability package for a case.
    This is the top-level function called by get_case_for_frontend().
    """
    intake = intake_data or {}
    conv = conversation_log or {}

    patient_lang = case_data.get("detected_language") or "en"
    translation_used = patient_lang != "en"

    # Translation artifacts from conversation log
    translation_artifacts = conv.get("translation_artifacts", [])
    avg_confidence = 1.0
    if translation_artifacts:
        confidences = [a.get("confidence", 0.8) for a in translation_artifacts]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 1.0

    return {
        "language_banner": build_language_banner(
            patient_language=patient_lang,
            translation_used=translation_used,
            translation_confidence=avg_confidence,
            code_switching=conv.get("code_switching_detected", False),
            detection_method=conv.get("detection_method", "default"),
        ),
        "patient_evidence": build_patient_evidence(
            conversation_turns=conv.get("turns", []),
            patient_language=patient_lang,
        ),
        "extraction": build_extraction_layer(
            extracted_facts=conv.get("extracted_facts", []),
            symptoms=_get_symptoms_from_intake(intake),
            severity=intake.get("severity"),
            duration=intake.get("duration"),
            body_area=intake.get("body_area"),
            medications=intake.get("current_medications"),
            allergies=intake.get("allergies"),
        ),
        "safety": build_safety_layer(
            triage_level=case_data.get("triage_level", "GREEN"),
            triage_breakdown=triage_breakdown,
            red_flags=intake.get("red_flag_indicators"),
            emergency_detected=case_data.get("is_emergency", False),
            kg_insights=intake.get("kg_insights"),
        ),
        "ambiguity": build_ambiguity_block(
            translation_artifacts=translation_artifacts,
            uncertainty_state=conv.get("uncertainty_state", "confident"),
        ),
    }


def _get_symptoms_from_intake(intake: dict) -> list[str]:
    """Extract symptom list from intake data."""
    symptoms = []
    main = intake.get("main_symptom", "")
    if main:
        symptoms.append(main)
    symptoms.extend(intake.get("associated_symptoms") or [])
    return symptoms
