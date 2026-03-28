"""Check if enough information has been gathered for safe case submission."""

from dataclasses import dataclass

REQUIRED_SLOTS = ["complaint", "duration", "severity"]
DESIRED_SLOTS = ["body_area", "medications", "allergies"]


@dataclass
class SufficiencyResult:
    sufficient: bool = False
    missing_required: list[str] = None
    missing_desired: list[str] = None
    recommendation: str = "continue_intake"

    def __post_init__(self):
        if self.missing_required is None:
            self.missing_required = []
        if self.missing_desired is None:
            self.missing_desired = []


def check_sufficiency(extraction: dict, symptom_count: int = 0, turn_count: int = 0) -> SufficiencyResult:
    result = SufficiencyResult()

    for slot in REQUIRED_SLOTS:
        val = extraction.get(slot)
        if not val or (isinstance(val, dict) and not val.get("value")):
            result.missing_required.append(slot)

    for slot in DESIRED_SLOTS:
        val = extraction.get(slot)
        if not val or (isinstance(val, dict) and not val.get("value")):
            result.missing_desired.append(slot)

    has_required = len(result.missing_required) == 0
    has_enough_symptoms = symptom_count >= 3
    has_enough_turns = turn_count >= 4

    if has_required and has_enough_symptoms:
        result.sufficient = True
        result.recommendation = "submit"
    elif has_enough_turns and has_enough_symptoms:
        result.sufficient = True
        result.recommendation = "submit_with_gaps"
    elif turn_count >= 8:
        result.sufficient = True
        result.recommendation = "submit_timeout"
    else:
        result.recommendation = "continue_intake"

    return result
