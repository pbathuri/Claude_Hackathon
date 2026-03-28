"""
START (Simple Triage and Rapid Treatment) protocol adapted for phone-based assessment.
Classifies patients into RED / YELLOW / GREEN / BLACK based on proxy questions
that can be asked over a phone call.
"""
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


# Emergency keywords that should trigger immediate RED classification
EMERGENCY_KEYWORDS = [
    "chest pain", "chest tightness", "can't breathe", "cannot breathe",
    "difficulty breathing", "shortness of breath", "stroke",
    "face drooping", "arm weakness", "slurred speech",
    "severe bleeding", "major trauma", "unconscious", "unresponsive",
    "suicidal", "self-harm", "throat swelling", "anaphylaxis",
    "seizure", "convulsion", "heart attack",
]


def check_emergency_keywords(text: str) -> bool:
    """Check if text contains emergency keywords warranting RED triage."""
    lower = text.lower()
    return any(kw in lower for kw in EMERGENCY_KEYWORDS)
