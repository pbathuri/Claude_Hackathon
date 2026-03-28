"""
Multi-factor priority queue for case routing.
Score = base_triage + wait_escalation + country_match + specialty_match + followup_bonus
Scores are computed *relative to a specific doctor* at pull time.
"""
import threading
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from config import (
    TRIAGE_BASE_SCORES,
    WAIT_ESCALATION_PER_15MIN,
    COUNTRY_MATCH_BONUS,
    SPECIALTY_MATCH_BONUS,
    FOLLOWUP_BONUS,
)
from models import Case, DoctorProfile


def compute_priority_score(
    case: Case,
    doctor_country: str | None = None,
    doctor_specialty: str | None = None,
) -> float:
    """
    Compute composite priority score for a case, optionally relative to a doctor.
    """
    # Base triage score
    base = float(TRIAGE_BASE_SCORES.get(case.triage_level or "GREEN", 10))

    # Wait-time escalation: +5 per 15 min since case opened
    now = datetime.now(timezone.utc)
    opened = case.opened_at or now
    if opened.tzinfo is None:
        opened = opened.replace(tzinfo=timezone.utc)
    wait_minutes = (now - opened).total_seconds() / 60
    wait_bonus = (wait_minutes // 15) * WAIT_ESCALATION_PER_15MIN

    # Country match bonus
    country_bonus = (
        COUNTRY_MATCH_BONUS
        if doctor_country and case.country_code == doctor_country
        else 0
    )

    # Specialty match bonus
    specialty_bonus = (
        SPECIALTY_MATCH_BONUS
        if doctor_specialty
        and case.recommended_specialty
        and case.recommended_specialty.lower() == doctor_specialty.lower()
        else 0
    )

    # Follow-up bonus
    followup_bonus = FOLLOWUP_BONUS if case.is_followup else 0

    return base + wait_bonus + country_bonus + specialty_bonus + followup_bonus


def get_next_case_for_doctor(db: Session, doctor_id: str) -> Case | None:
    """
    Pull the highest-priority pending case for a specific doctor.
    Scores are computed relative to the doctor's country and specialty.
    """
    doctor = db.query(DoctorProfile).filter_by(id=doctor_id).first()
    if not doctor:
        return None

    pending_cases = (
        db.query(Case)
        .filter(Case.status.in_(["pending", "intake_complete"]))
        .all()
    )

    if not pending_cases:
        return None

    # Score each case relative to this doctor
    scored = [
        (
            compute_priority_score(
                c,
                doctor_country=doctor.country_code,
                doctor_specialty=doctor.specialization,
            ),
            c,
        )
        for c in pending_cases
    ]

    # Sort descending by score
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_case = scored[0]

    # Update the case
    best_case.status = "assigned"
    best_case.assigned_doctor_id = doctor_id
    best_case.assigned_at = datetime.now(timezone.utc)
    best_case.priority_score = best_score
    db.commit()
    db.refresh(best_case)

    return best_case


def get_queue_snapshot(db: Session, doctor_id: str | None = None) -> list[dict]:
    """
    Return current queue state with scores. If doctor_id is given,
    scores are relative to that doctor.
    """
    pending = (
        db.query(Case)
        .filter(Case.status.in_(["pending", "intake_complete"]))
        .all()
    )

    doctor = None
    if doctor_id:
        doctor = db.query(DoctorProfile).filter_by(id=doctor_id).first()

    results = []
    for c in pending:
        score = compute_priority_score(
            c,
            doctor_country=doctor.country_code if doctor else None,
            doctor_specialty=doctor.specialization if doctor else None,
        )
        results.append({
            "case_id": c.id,
            "triage_level": c.triage_level,
            "country_code": c.country_code,
            "specialty": c.recommended_specialty,
            "is_followup": c.is_followup,
            "priority_score": score,
            "status": c.status,
            "opened_at": c.opened_at.isoformat() if c.opened_at else None,
        })

    results.sort(key=lambda x: x["priority_score"], reverse=True)
    return results
