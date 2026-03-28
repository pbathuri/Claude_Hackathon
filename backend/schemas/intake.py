"""
Canonical intake payload stored in Case.intake_data (JSON).

All write paths should normalize through case_service.complete_intake.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IntakeData(BaseModel):
    """Structured clinical intake aligned with triage + ICD-11 + portal display."""

    model_config = ConfigDict(extra="allow")

    main_symptom: str = ""
    duration: str = ""
    severity: int = 5
    associated_symptoms: list[str] = Field(default_factory=list)
    medical_history: list[str] = Field(default_factory=list)
    current_medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    triage_level: str = "GREEN"
    recommended_specialty: str = "general"
    body_area: str = ""
    red_flag_indicators: list[str] = Field(default_factory=list)
    patient_summary: str = ""
    kg_insights: dict[str, Any] | None = None


def normalize_intake_dict(raw: dict) -> dict:
    """Validate and serialize; preserves extra keys allowed by IntakeData."""
    d = dict(raw)
    if d.get("severity") is None:
        d["severity"] = 5
    if d.get("triage_level") is None:
        d["triage_level"] = "GREEN"
    return IntakeData.model_validate(d).model_dump(mode="json")


def build_symptom_summary_line(intake: dict) -> str:
    """Single-line summary for portal symptomSummary (same field as before, richer when multiple symptoms)."""
    main = (intake.get("main_symptom") or "").strip()
    assoc = [s for s in (intake.get("associated_symptoms") or []) if s]
    if not assoc:
        return main
    if main:
        return f"{main} — Also: {', '.join(assoc)}"
    return ", ".join(assoc)
