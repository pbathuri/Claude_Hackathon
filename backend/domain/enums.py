"""
Canonical enums for the WHO-aligned AI telehealth platform.
Single source of truth for status codes, triage levels, actor types,
and all string-typed domain constants used across backend services.
"""
from enum import Enum


class CaseStatus(str, Enum):
    # Values match the DB case_status_enum exactly (models.py CASE_STATUS_VALUES)
    CREATED = "open"
    INTAKE_COMPLETE = "intake_complete"
    PENDING_REVIEW = "pending"
    ASSIGNED = "assigned"
    IN_REVIEW = "in_progress"
    RESPONDED = "resolved"
    ESCALATED = "escalated"
    EXPIRED = "expired"
    CLOSED = "closed"


class TriageLevel(str, Enum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    BLACK = "BLACK"
    UNKNOWN = "UNKNOWN"


class UrgencyDisplay(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MODERATE = "Moderate"
    LOW = "Low"
    UNKNOWN = "Unknown"


class ActorType(str, Enum):
    PATIENT = "patient"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    DOCTOR = "doctor"


class UncertaintyLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ConsentType(str, Enum):
    VERBAL_DISCLOSURE = "verbal_disclosure"
    DATA_PROCESSING = "data_processing"
    IMAGE_UPLOAD = "image_upload"


class SourceChannel(str, Enum):
    VOICE = "voice"
    SMS = "sms"
    WEB = "web"
    TWILIO = "twilio"


class ExtractionProvenance(str, Enum):
    PATIENT_REPORTED = "patient_reported"
    AI_EXTRACTED = "ai_extracted"
    RULE_DERIVED = "rule_derived"
    CLINICIAN_AUTHORED = "clinician_authored"
    SYSTEM_DEFAULT = "system_default"


# ── Valid state transitions (finite state machine) ──────────────
# Each key maps to the set of states reachable from it.
# CLOSED is a terminal state with no outgoing transitions.

VALID_TRANSITIONS: dict[CaseStatus, set[CaseStatus]] = {
    CaseStatus.CREATED: {CaseStatus.INTAKE_COMPLETE, CaseStatus.ESCALATED},
    CaseStatus.INTAKE_COMPLETE: {CaseStatus.PENDING_REVIEW, CaseStatus.ESCALATED},
    CaseStatus.PENDING_REVIEW: {CaseStatus.ASSIGNED, CaseStatus.EXPIRED, CaseStatus.ESCALATED},
    CaseStatus.ASSIGNED: {CaseStatus.IN_REVIEW, CaseStatus.EXPIRED, CaseStatus.ESCALATED},
    CaseStatus.IN_REVIEW: {CaseStatus.RESPONDED, CaseStatus.ESCALATED},
    CaseStatus.RESPONDED: {CaseStatus.CLOSED},
    CaseStatus.ESCALATED: {CaseStatus.ASSIGNED, CaseStatus.CLOSED},
    CaseStatus.EXPIRED: {CaseStatus.PENDING_REVIEW, CaseStatus.CLOSED},
    CaseStatus.CLOSED: set(),
}


def validate_transition(current: CaseStatus, target: CaseStatus) -> bool:
    """Return True if moving from *current* to *target* is a legal state change."""
    return target in VALID_TRANSITIONS.get(current, set())
