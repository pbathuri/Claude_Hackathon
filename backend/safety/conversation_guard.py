"""
Conversation Guard — Phase 03 Safety Engine.

Enforces conversation boundaries:
- Max turn limit (hard stop)
- Minimum sufficiency check before completion
- Anti-repetition detection
- Stale conversation detection
- Structured uncertainty reporting
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from models.conversation import (
    ConversationSummary,
    UncertaintyState,
    ExtractedFact,
    FactSource,
)

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────

MAX_TURNS_HARD_LIMIT = 12          # Absolute max turns before forced completion
MIN_SYMPTOMS_FOR_SUFFICIENT = 3    # Need at least this many symptoms
MIN_FACTS_FOR_SUFFICIENT = 4       # Need at least this many total facts
STALE_THRESHOLD = 2                # Turns with no new facts = stale
REPETITION_SIMILARITY = 0.85       # Threshold for "same question" detection


@dataclass
class GuardVerdict:
    """Result of the conversation guard check."""
    should_continue: bool = True
    should_complete: bool = False
    force_complete: bool = False
    reason: str = ""
    uncertainty: UncertaintyState = UncertaintyState.CONFIDENT
    warnings: list[str] = field(default_factory=list)


def check_conversation_sufficiency(
    summary: ConversationSummary,
    turn_number: int,
    new_facts_this_turn: int = 0,
    consecutive_stale_turns: int = 0,
) -> GuardVerdict:
    """
    Determine if a conversation should continue, complete, or be force-completed.

    Decision tree:
    1. Emergency detected → force complete immediately
    2. Max turns reached → force complete with warning
    3. Sufficient facts gathered → suggest completion
    4. Stale turns exceeded → suggest completion with insufficient_information
    5. Otherwise → continue
    """
    verdict = GuardVerdict()
    symptoms = summary.get_symptoms()
    total_facts = len(summary.extracted_facts)

    # 1. Emergency — immediate completion
    if summary.emergency_flags:
        verdict.should_complete = True
        verdict.force_complete = True
        verdict.should_continue = False
        verdict.reason = "emergency_detected"
        return verdict

    # 2. Hard turn limit
    if turn_number >= MAX_TURNS_HARD_LIMIT:
        verdict.should_complete = True
        verdict.force_complete = True
        verdict.should_continue = False
        verdict.reason = "max_turns_reached"
        if total_facts < MIN_FACTS_FOR_SUFFICIENT:
            verdict.uncertainty = UncertaintyState.INSUFFICIENT_INFORMATION
            verdict.warnings.append(
                f"Conversation reached {MAX_TURNS_HARD_LIMIT} turns with only "
                f"{total_facts} facts extracted (minimum {MIN_FACTS_FOR_SUFFICIENT})"
            )
        return verdict

    # 3. Sufficient information gathered
    has_enough_symptoms = len(symptoms) >= MIN_SYMPTOMS_FOR_SUFFICIENT
    has_severity = summary.get_severity() is not None
    has_duration = summary.get_duration() is not None
    has_enough_facts = total_facts >= MIN_FACTS_FOR_SUFFICIENT

    if has_enough_symptoms and has_enough_facts and (has_severity or has_duration):
        verdict.should_complete = True
        verdict.should_continue = False
        verdict.reason = "sufficient_information"
        summary.is_sufficient = True
        return verdict

    # 4. Stale conversation (no new information for N turns)
    if consecutive_stale_turns >= STALE_THRESHOLD and turn_number >= 3:
        verdict.should_complete = True
        verdict.should_continue = False
        verdict.reason = "stale_conversation"
        if not has_enough_symptoms:
            verdict.uncertainty = UncertaintyState.INSUFFICIENT_INFORMATION
            verdict.warnings.append(
                f"No new clinical facts for {consecutive_stale_turns} turns. "
                f"Only {len(symptoms)} symptoms collected."
            )
        return verdict

    # 5. Continue — but add warnings if approaching limits
    verdict.should_continue = True
    if turn_number >= MAX_TURNS_HARD_LIMIT - 2:
        verdict.warnings.append(
            f"Approaching turn limit ({turn_number}/{MAX_TURNS_HARD_LIMIT}). "
            f"Focus on gathering remaining key facts."
        )

    return verdict


def check_repetition(
    new_message: str,
    previous_messages: list[str],
    threshold: float = REPETITION_SIMILARITY,
) -> bool:
    """
    Check if the new AI message is too similar to a previous one.
    Uses simple word overlap ratio (fast, no ML dependency).
    """
    if not previous_messages or not new_message:
        return False

    new_words = set(new_message.lower().split())
    if not new_words:
        return False

    for prev in previous_messages[-5:]:  # Check last 5 messages
        prev_words = set(prev.lower().split())
        if not prev_words:
            continue
        overlap = len(new_words & prev_words)
        union = len(new_words | prev_words)
        if union > 0 and overlap / union > threshold:
            return True

    return False


def extract_facts_from_text(
    text: str,
    turn_number: int,
    existing_symptoms: list[str],
) -> list[ExtractedFact]:
    """
    Rule-based fact extraction from patient text.
    This runs BEFORE Claude to catch obvious facts deterministically.

    Extracts: symptoms (from keyword list), severity (from numbers), duration patterns.
    """
    import re

    facts: list[ExtractedFact] = []
    lower = text.lower()

    # ── Severity extraction ──────────────────────────────────────────
    severity_patterns = [
        (r"(\d+)\s*(?:out of|/)\s*10", "severity"),
        (r"pain\s+(?:level|score|is)\s+(\d+)", "severity"),
        (r"severity\s+(\d+)", "severity"),
    ]
    for pattern, fact_type in severity_patterns:
        m = re.search(pattern, lower)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 10:
                facts.append(ExtractedFact(
                    fact_type=fact_type,
                    value=str(val),
                    source=FactSource.PATIENT_STATED,
                    confidence=0.9,
                    turn_number=turn_number,
                    raw_text=m.group(0),
                ))
                break

    # ── Duration extraction ──────────────────────────────────────────
    duration_patterns = [
        r"(?:for|since|past|last)\s+(\d+\s+(?:day|week|month|hour|year)s?)",
        r"(\d+\s+(?:day|week|month|hour|year)s?)\s+(?:ago|now|already)",
        r"(?:started|began|onset)\s+(\d+\s+(?:day|week|month|hour|year)s?\s+ago)",
        r"(?:for|since|past|last)\s+(a\s+(?:day|week|month|hour|year))",
    ]
    for pattern in duration_patterns:
        m = re.search(pattern, lower)
        if m:
            facts.append(ExtractedFact(
                fact_type="duration",
                value=m.group(1).strip(),
                source=FactSource.PATIENT_STATED,
                confidence=0.85,
                turn_number=turn_number,
                raw_text=m.group(0),
            ))
            break

    # ── Body area extraction ─────────────────────────────────────────
    body_areas = {
        "head": ["head", "headache", "skull", "temple"],
        "chest": ["chest", "rib", "sternum", "breast"],
        "abdomen": ["stomach", "abdomen", "belly", "abdominal", "tummy"],
        "back": ["back", "spine", "lower back", "upper back"],
        "throat": ["throat", "neck", "tonsil"],
        "limbs": ["arm", "leg", "knee", "ankle", "wrist", "elbow", "shoulder", "hip"],
        "skin": ["skin", "rash", "lesion", "wound"],
        "eyes": ["eye", "vision", "sight"],
        "ears": ["ear", "hearing"],
        "whole body": ["whole body", "everywhere", "all over", "body aches"],
    }
    for area, keywords in body_areas.items():
        if any(kw in lower for kw in keywords):
            facts.append(ExtractedFact(
                fact_type="body_area",
                value=area,
                source=FactSource.AI_EXTRACTED,
                confidence=0.7,
                turn_number=turn_number,
            ))
            break

    # ── Symptom keyword extraction (deterministic) ───────────────────
    symptom_keywords = [
        "fever", "headache", "cough", "sore throat", "fatigue", "nausea",
        "vomiting", "diarrhea", "chest pain", "shortness of breath",
        "dizziness", "rash", "body aches", "chills", "sweating",
        "loss of appetite", "abdominal pain", "back pain", "joint pain",
        "muscle pain", "runny nose", "congestion", "sneezing",
        "weakness", "numbness", "tingling", "swelling", "bleeding",
        "weight loss", "insomnia", "anxiety", "depression",
        "palpitations", "blurred vision", "difficulty swallowing",
        "frequent urination", "blood in urine", "blood in stool",
        "constipation", "bloating", "itching", "bruising",
        "difficulty breathing", "wheezing", "ear pain", "toothache",
    ]
    existing_lower = [s.lower() for s in existing_symptoms]
    for kw in symptom_keywords:
        if kw in lower and kw not in existing_lower:
            facts.append(ExtractedFact(
                fact_type="symptom",
                value=kw,
                source=FactSource.PATIENT_STATED,
                confidence=0.8,
                turn_number=turn_number,
            ))

    return facts
