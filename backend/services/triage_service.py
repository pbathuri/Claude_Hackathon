"""
START (Simple Triage and Rapid Treatment) protocol adapted for phone-based assessment.
Classifies patients into RED / YELLOW / GREEN / BLACK based on proxy questions
that can be asked over a phone call.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from config import TRIAGE_BASE_SCORES


@dataclass
class PhoneAssessment:
    """Answers gathered via phone proxy questions."""
    can_walk: bool
    is_breathing: bool
    breathing_after_reposition: Optional[bool] = None
    respiratory_rate: Optional[int] = None          # breaths per minute
    capillary_refill_over_2s: Optional[bool] = None
    can_follow_commands: Optional[bool] = None


# Phone proxy questions mapped to each START criterion
PHONE_PROXY_QUESTIONS = {
    "ambulatory": "Are you able to stand up and walk across the room right now?",
    "breathing": (
        "Can you see their chest moving? "
        "Hold your hand near their mouth — do you feel air?"
    ),
    "respiratory_rate": (
        "Watch their chest. I'll count 15 seconds — "
        "tell me how many breaths. (multiply by 4)"
    ),
    "perfusion": (
        "Press firmly on their fingernail for 5 seconds. "
        "Does pink color return within 2 seconds?"
    ),
    "mental_status": (
        "Ask them to squeeze your hand. Can they follow that instruction?"
    ),
}


def start_triage(assessment: PhoneAssessment) -> str:
    """
    Run the START decision tree. Returns triage level: RED, YELLOW, GREEN, or BLACK.
    """
    # Step 1: Can the patient walk?
    if assessment.can_walk:
        return "GREEN"

    # Step 2: Is the patient breathing?
    if not assessment.is_breathing:
        if assessment.breathing_after_reposition:
            return "RED"
        return "BLACK"

    # Step 3: Respiratory rate > 30?
    if assessment.respiratory_rate is not None and assessment.respiratory_rate > 30:
        return "RED"

    # Step 4: Perfusion (capillary refill > 2 seconds?)
    if assessment.capillary_refill_over_2s:
        return "RED"

    # Step 5: Mental status — can follow commands?
    if assessment.can_follow_commands is not None and not assessment.can_follow_commands:
        return "RED"

    # If breathing, normal rate, good perfusion, can follow commands → delayed
    return "YELLOW"


def triage_from_intake(intake_data: dict) -> str:
    """
    Determine triage level from Claude intake output.
    The intake agent sets triage_level directly based on symptom severity
    and emergency detection rules. This function validates and falls back.
    """
    level = intake_data.get("triage_level", "GREEN").upper()
    if level not in TRIAGE_BASE_SCORES:
        return "GREEN"
    return level


def get_base_score(triage_level: str) -> float:
    """Return the base priority score for a triage level."""
    return float(TRIAGE_BASE_SCORES.get(triage_level, 10))


# Phrases: substring match (multi-word, specific enough to avoid false positives).
# Omit vague phrases like "shortness of breath" / "difficulty breathing" here — they
# still influence YELLOW triage via detect_red_flags on submit, but must not block intake.
_EMERGENCY_PHRASES = [
    "chest pain",
    "chest tightness",
    "can't breathe",
    "cannot breathe",
    "heart attack",
    "face drooping",
    "arm weakness",
    "slurred speech",
    "severe bleeding",
    "bleeding heavily",
    "major trauma",
    "unconscious",
    "unresponsive",
    "passed out",
    "throat swelling",
    "throat closing",
    "anaphylaxis",
    "self-harm",
    "kill myself",
    "kill yourself",
    "want to die",
    "stopped breathing",
    "not breathing",
]

# Single tokens / tight patterns: word boundaries so "heatstroke" does not match "stroke".
_EMERGENCY_WORD_RES = [
    re.compile(r"\bstroke\b", re.IGNORECASE),
    re.compile(r"\bseizure\b", re.IGNORECASE),
    re.compile(r"\bconvulsions?\b", re.IGNORECASE),
    re.compile(r"\bsuicidal\b", re.IGNORECASE),
    re.compile(r"\bsuicide\b", re.IGNORECASE),
]

# Backward compat: flat list for code that iterates keywords (e.g. submit red flag labels)
EMERGENCY_KEYWORDS = list(_EMERGENCY_PHRASES) + [
    "stroke",
    "seizure",
    "convulsion",
    "suicidal",
    "suicide",
]


def check_emergency_keywords(text: str) -> bool:
    """True only for clear, immediate-danger phrases (does not block on mild dyspnea)."""
    return len(emergency_keyword_hits(text)) > 0


def emergency_keyword_hits(text: str) -> list[str]:
    """Labels for matched immediate-danger phrases (word-safe; no heatstroke→stroke)."""
    if not text or not str(text).strip():
        return []
    lower = str(text).lower()
    hits: list[str] = []
    for phrase in _EMERGENCY_PHRASES:
        if phrase in lower:
            hits.append(phrase.title())
    for rx in _EMERGENCY_WORD_RES:
        m = rx.search(text)
        if m:
            hits.append(m.group(0).title())
    # Dedupe preserving order
    return list(dict.fromkeys(hits))


def build_triage_breakdown(
    triage_level: str,
    severity: int = 5,
    red_flags: list[str] | None = None,
    symptom_count: int = 0,
    duration: str = "",
    kg_confidence: float = 0.0,
    country_tier: int = 3,
) -> dict:
    """
    Build an explainable triage score breakdown (Phase 01).
    Returns a dict matching TriageScoreBreakdown schema.
    Every component is individually auditable.
    """
    base = float(TRIAGE_BASE_SCORES.get(triage_level, 10))
    severity_score = max(0.0, (severity - 3) * 5.0)  # 1-3 → 0, 4→5, 7→20, 10→35
    red_flag_score = len(red_flags or []) * 15.0       # Each red flag adds 15 points
    symptom_count_score = min(20.0, symptom_count * 3.0)  # Up to 20 pts

    # Duration: longer durations get slightly lower urgency (chronic vs acute)
    duration_score = 0.0
    if duration:
        lower_dur = duration.lower()
        if any(w in lower_dur for w in ["hour", "minute"]):
            duration_score = 10.0  # Acute onset
        elif any(w in lower_dur for w in ["day", "1 day", "2 day"]):
            duration_score = 5.0
        elif any(w in lower_dur for w in ["week"]):
            duration_score = 2.0
        # months/years → 0 (chronic, lower urgency)

    kg_score = kg_confidence * 10.0  # 0-10 pts
    tier_score = {1: 10, 2: 20, 3: 30, 4: 40}.get(country_tier, 30)

    total = base + severity_score + red_flag_score + symptom_count_score + duration_score + kg_score + tier_score

    # Build explanation
    parts = [f"Triage {triage_level} (base={base})"]
    if severity_score > 0:
        parts.append(f"severity {severity}/10 (+{severity_score:.0f})")
    if red_flag_score > 0:
        parts.append(f"{len(red_flags or [])} red flags (+{red_flag_score:.0f})")
    if symptom_count_score > 0:
        parts.append(f"{symptom_count} symptoms (+{symptom_count_score:.0f})")
    if duration_score > 0:
        parts.append(f"duration '{duration}' (+{duration_score:.0f})")
    parts.append(f"Tier {country_tier} (+{tier_score:.0f})")

    return {
        "triage_level": triage_level,
        "base_score": base,
        "severity_score": severity_score,
        "red_flag_score": red_flag_score,
        "symptom_count_score": symptom_count_score,
        "duration_score": duration_score,
        "kg_confidence_score": kg_score,
        "country_tier_score": tier_score,
        "total_priority": round(total, 1),
        "explanation": " | ".join(parts),
    }
