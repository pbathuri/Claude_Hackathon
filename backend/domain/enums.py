"""
Canonical enums for the WHO-aligned AI telehealth platform.
Single source of truth for status codes, triage levels, actor types,
and all string-typed domain constants used across backend services.
"""
from enum import Enum


class CaseStatus(str, Enum):
    CREATED = "created"
    ACTIVE_INTAKE = "active_intake"
    INTAKE_COMPLETE = "intake_complete"
    PENDING_REVIEW = "pending_review"
    ASSIGNED = "assigned"
    IN_REVIEW = "in_review"
    RESPONDED = "responded"
    FOLLOWUP_PENDING = "followup_pending"
    FOLLOWUP_REPLIED = "followup_replied"
    ESCALATED = "escalated"
    EXPIRED = "expired"
    CLOSED = "closed"
    INSUFFICIENT_INFORMATION = "insufficient_information"


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
    CaseStatus.CREATED: {CaseStatus.ACTIVE_INTAKE, CaseStatus.INSUFFICIENT_INFORMATION},
    CaseStatus.ACTIVE_INTAKE: {CaseStatus.INTAKE_COMPLETE, CaseStatus.INSUFFICIENT_INFORMATION, CaseStatus.ESCALATED},
    CaseStatus.INTAKE_COMPLETE: {CaseStatus.PENDING_REVIEW, CaseStatus.ESCALATED},
    CaseStatus.PENDING_REVIEW: {CaseStatus.ASSIGNED, CaseStatus.EXPIRED, CaseStatus.ESCALATED},
    CaseStatus.ASSIGNED: {CaseStatus.IN_REVIEW, CaseStatus.EXPIRED, CaseStatus.ESCALATED},
    CaseStatus.IN_REVIEW: {CaseStatus.RESPONDED, CaseStatus.ESCALATED},
    CaseStatus.RESPONDED: {CaseStatus.FOLLOWUP_PENDING, CaseStatus.CLOSED},
    CaseStatus.FOLLOWUP_PENDING: {CaseStatus.FOLLOWUP_REPLIED, CaseStatus.EXPIRED, CaseStatus.ESCALATED},
    CaseStatus.FOLLOWUP_REPLIED: {CaseStatus.CLOSED, CaseStatus.ESCALATED, CaseStatus.PENDING_REVIEW},
    CaseStatus.ESCALATED: {CaseStatus.ASSIGNED, CaseStatus.CLOSED},
    CaseStatus.EXPIRED: {CaseStatus.PENDING_REVIEW, CaseStatus.CLOSED},
    CaseStatus.INSUFFICIENT_INFORMATION: {CaseStatus.ACTIVE_INTAKE, CaseStatus.CLOSED},
    CaseStatus.CLOSED: set(),
}


def validate_transition(current: CaseStatus, target: CaseStatus) -> bool:
    """Return True if moving from *current* to *target* is a legal state change."""
    return target in VALID_TRANSITIONS.get(current, set())
