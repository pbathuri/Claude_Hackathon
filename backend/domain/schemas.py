"""
Pydantic models for canonical data types used across the platform.
These schemas enforce structure at the application boundary—validated
before persistence and serialised for API responses.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .enums import (
    ActorType,
    ExtractionProvenance,
    SourceChannel,
    TriageLevel,
    UncertaintyLevel,
)


class ConversationTurn(BaseModel):
    turn_index: int
    actor_type: ActorType
    channel: SourceChannel
    language: str = "en"
    text: str
    original_text: Optional[str] = None
    original_language: Optional[str] = None
    language_confidence: Optional[float] = None
    translated_text: Optional[str] = None
    translation_confidence: Optional[float] = None
    transcript_confidence: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExtractedFact(BaseModel):
    field: str
    value: str
    confidence: float = 1.0
    provenance: ExtractionProvenance = ExtractionProvenance.PATIENT_REPORTED
    source_turn_indices: list[int] = []
    uncertainty_level: UncertaintyLevel = UncertaintyLevel.NONE
    notes: Optional[str] = None


class ClinicalExtraction(BaseModel):
    complaint: Optional[ExtractedFact] = None
    duration: Optional[ExtractedFact] = None
    severity: Optional[ExtractedFact] = None
    body_area: Optional[ExtractedFact] = None
    symptoms: list[ExtractedFact] = []
    medications: list[ExtractedFact] = []
    allergies: list[ExtractedFact] = []
    medical_history: list[ExtractedFact] = []
    red_flags: list[ExtractedFact] = []
    uncertainty_flags: list[str] = []
    overall_confidence: float = 0.0
    extraction_complete: bool = False


class ScoreBreakdown(BaseModel):
    clinical_urgency_score: float = 0.0
    tier_score: float = 0.0
    wait_bonus: float = 0.0
    specialty_bonus: float = 0.0
    red_flag_bonus: float = 0.0
    uncertainty_penalty: float = 0.0
    routing_priority_score: float = 0.0
    display_urgency: str = "Unknown"
    triage_level: TriageLevel = TriageLevel.UNKNOWN
    scoring_version: str = "2.0"


class ConsentEvent(BaseModel):
    consent_type: str
    version: str = "1.0"
    language: str = "en"
    channel: str = "web"
    accepted: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    consent_text_hash: Optional[str] = None
