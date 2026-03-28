"""
Domain events emitted by the case lifecycle.
Persisted to the audit log and (eventually) published to an event bus
for async subscribers like notifications, analytics, and compliance.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    event_type: str
    case_id: Optional[str] = None
    actor_id: Optional[str] = None
    actor_type: str = "system"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = {}


class CaseStatusChanged(DomainEvent):
    event_type: str = "case.status_changed"
    old_status: str = ""
    new_status: str = ""
    reason: str = ""


class EmergencyDetected(DomainEvent):
    event_type: str = "safety.emergency_detected"
    flags: list[str] = []
    source: str = ""
    action_taken: str = ""


class TriageCompleted(DomainEvent):
    event_type: str = "triage.completed"
    triage_level: str = ""
    score_breakdown: dict = {}


class DoctorResponseSubmitted(DomainEvent):
    event_type: str = "doctor.response_submitted"
    doctor_id: str = ""
    diagnosis: str = ""
