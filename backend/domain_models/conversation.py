"""
Canonical Conversation Model — Phase 01 Data Integrity.

Separates patient-reported data, AI-extracted facts, rule outputs, and clinician conclusions.
Every conversation turn is stored with its source (patient, ai, system) and any extracted facts.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class TurnRole(str, enum.Enum):
    PATIENT = "patient"
    AI = "ai"
    SYSTEM = "system"


class FactSource(str, enum.Enum):
    """Where a clinical fact was extracted from."""
    PATIENT_STATED = "patient_stated"       # Patient explicitly said it
    AI_EXTRACTED = "ai_extracted"           # AI inferred from conversation
    KG_INFERRED = "kg_inferred"            # Knowledge graph activation
    RULE_DERIVED = "rule_derived"          # Deterministic rule output
    CLINICIAN_CONFIRMED = "clinician_confirmed"  # Doctor verified


class UncertaintyState(str, enum.Enum):
    """Structured uncertainty — better than hiding doubt in free text."""
    CONFIDENT = "confident"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    CONFLICTING_INFORMATION = "conflicting_information"
    TRANSLATION_UNCERTAINTY = "translation_uncertainty"
    LOW_CONFIDENCE_EXTRACTION = "low_confidence_extraction"
    ESCALATION_REQUIRED = "escalation_required"


# Import the single canonical CaseStatus + VALID_TRANSITIONS from domain/enums
from domain.enums import CaseStatus, VALID_TRANSITIONS  # noqa: F401


def validate_transition(from_status: str, to_status: str) -> bool:
    """Check if a state transition is valid."""
    try:
        f = CaseStatus(from_status)
        t = CaseStatus(to_status)
    except ValueError:
        return False
    return t in VALID_TRANSITIONS.get(f, set())


# ── Pydantic models for structured conversation data ─────────────────────

class ConversationTurn(BaseModel):
    """A single turn in the conversation."""
    turn_number: int
    role: TurnRole
    content: str
    language: str = "en"
    english_translation: Optional[str] = None  # If role=patient and language != en
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExtractedFact(BaseModel):
    """A clinical fact extracted from conversation."""
    fact_type: str                              # symptom, duration, severity, medication, allergy, etc.
    value: str                                  # The extracted value
    source: FactSource
    confidence: float = 1.0                     # 0.0–1.0
    turn_number: Optional[int] = None           # Which turn it came from
    uncertainty: UncertaintyState = UncertaintyState.CONFIDENT
    raw_text: Optional[str] = None              # Original patient text that sourced this


class TriageScoreBreakdown(BaseModel):
    """Explainable triage scoring — no opaque floats."""
    triage_level: str                           # RED, YELLOW, GREEN
    base_score: float                           # From triage level
    severity_score: float = 0.0                 # From patient-reported severity
    red_flag_score: float = 0.0                 # From emergency keyword detection
    symptom_count_score: float = 0.0            # From number of symptoms
    duration_score: float = 0.0                 # From symptom duration
    kg_confidence_score: float = 0.0            # From knowledge graph confidence
    country_tier_score: float = 0.0             # From country underservice level
    total_priority: float = 0.0                 # Computed final priority score
    explanation: str = ""                       # Human-readable explanation

    def compute_total(self) -> float:
        self.total_priority = (
            self.base_score
            + self.severity_score
            + self.red_flag_score
            + self.symptom_count_score
            + self.duration_score
            + self.kg_confidence_score
            + self.country_tier_score
        )
        return self.total_priority


class ConversationSummary(BaseModel):
    """Complete conversation record for a case — stored as Case.conversation_log JSON."""
    turns: list[ConversationTurn] = Field(default_factory=list)
    extracted_facts: list[ExtractedFact] = Field(default_factory=list)
    detected_language: str = "en"
    emergency_flags: list[str] = Field(default_factory=list)
    uncertainty_state: UncertaintyState = UncertaintyState.CONFIDENT
    triage_breakdown: Optional[TriageScoreBreakdown] = None
    kg_insights: Optional[dict] = None
    is_sufficient: bool = False                 # Did conversation gather enough info?
    completion_reason: str = ""                 # Why conversation ended

    def get_symptoms(self) -> list[str]:
        """Extract all symptom facts."""
        return [f.value for f in self.extracted_facts if f.fact_type == "symptom"]

    def get_severity(self) -> Optional[int]:
        """Extract severity if reported."""
        for f in self.extracted_facts:
            if f.fact_type == "severity":
                try:
                    return int(f.value)
                except (ValueError, TypeError):
                    continue
        return None

    def get_duration(self) -> Optional[str]:
        """Extract duration if reported."""
        for f in self.extracted_facts:
            if f.fact_type == "duration":
                return f.value
        return None

    def get_body_area(self) -> Optional[str]:
        """Extract body area if reported."""
        for f in self.extracted_facts:
            if f.fact_type == "body_area":
                return f.value
        return None
