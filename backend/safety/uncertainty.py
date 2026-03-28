"""Structured uncertainty states for clinical safety."""

from dataclasses import dataclass, field
from enum import Enum


class UncertaintyType(str, Enum):
    INSUFFICIENT_INFORMATION = "insufficient_information"
    CONFLICTING_INFORMATION = "conflicting_information"
    TRANSLATION_UNCERTAINTY = "translation_uncertainty"
    LOW_CONFIDENCE_EXTRACTION = "low_confidence_extraction"
    ESCALATION_REQUIRED = "escalation_required"
    TRANSCRIPT_LOW_CONFIDENCE = "transcript_low_confidence"
    CODE_SWITCHING_DETECTED = "code_switching_detected"


@dataclass
class UncertaintyAssessment:
    uncertainties: list[dict] = field(default_factory=list)
    overall_level: str = "none"  # none, low, moderate, high, critical
    requires_escalation: bool = False
    requires_clarification: bool = False
    safe_to_proceed: bool = True

    def add(self, uncertainty_type: UncertaintyType, detail: str = "", severity: str = "low"):
        self.uncertainties.append({
            "type": uncertainty_type.value,
            "detail": detail,
            "severity": severity,
        })
        self._recalculate()

    def _recalculate(self):
        if not self.uncertainties:
            self.overall_level = "none"
            return

        severities = [u["severity"] for u in self.uncertainties]
        if "critical" in severities:
            self.overall_level = "critical"
            self.requires_escalation = True
            self.safe_to_proceed = False
        elif "high" in severities:
            self.overall_level = "high"
            self.requires_escalation = True
        elif "moderate" in severities:
            self.overall_level = "moderate"
            self.requires_clarification = True
        else:
            self.overall_level = "low"

    def to_dict(self) -> dict:
        return {
            "uncertainties": self.uncertainties,
            "overall_level": self.overall_level,
            "requires_escalation": self.requires_escalation,
            "requires_clarification": self.requires_clarification,
            "safe_to_proceed": self.safe_to_proceed,
        }
