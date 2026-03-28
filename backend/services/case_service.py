"""
Case lifecycle management: creation, assignment, escalation, expiration, resolution, follow-up.
State machine: open → intake_complete → pending → assigned → in_progress → resolved → closed
Also: escalated, expired → reassigned
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import (
    Case, Patient, DoctorProfile, DoctorResponse, SymptomRecord,
    ImageUpload, FollowUpSchedule, AuditLog, CountryPermission,
)
from services.triage_service import triage_from_intake, get_base_score
from services.priority_queue import compute_priority_score


# ── Urgency + Tier scoring for frontend contract ──
URGENCY_SCORES = {"RED": 100, "YELLOW": 50, "GREEN": 10, "BLACK": 0}
TIER_SCORES = {1: 10, 2: 20, 3: 30}  # Higher tier = more underserved = higher priority


def compute_frontend_priority(triage_level: str, country_tier: int) -> float:
    """priorityScore = urgencyScore + tierScore"""
    urgency = URGENCY_SCORES.get(triage_level, 10)
    tier = TIER_SCORES.get(country_tier, 30)
    return float(urgency + tier)


def _audit(db: Session, action: str, resource_type: str, resource_id: str,
           actor_id: str | None = None, actor_type: str | None = None,
           details: dict | None = None):
    """Append an entry to the audit log."""
    db.add(AuditLog(
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    ))


def _generate_patient_alias(patient_id: str) -> str:
    """Generate a privacy-safe alias like PT-2048 from patient UUID."""
    numeric = int(patient_id.replace("-", "")[:8], 16) % 10000
    return f"PT-{numeric:04d}"


def create_case(db: Session, patient_id: str, country_code: str,
                chief_complaint: str | None = None,
                permission_tier: str | None = None) -> Case:
    """Create a new case in 'open' status."""
    case = Case(
        patient_id=patient_id,
        country_code=country_code,
        status="open",
        chief_complaint=chief_complaint,
        permission_tier=permission_tier,
        patient_alias=_generate_patient_alias(patient_id),
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    _audit(db, "create", "case", case.id, actor_id=patient_id, actor_type="patient")
    db.commit()
    return case


def complete_intake(db: Session, case_id: str, intake_data: dict,
                    icd11_codes: list | None = None) -> Case:
    """
    Mark a case as intake_complete with structured data from Claude.
    Sets triage level, priority score, recommended specialty, and ICD-11 codes.
    """
    case = db.query(Case).filter_by(id=case_id).first()
    if not case:
        raise ValueError(f"Case {case_id} not found")

    triage = triage_from_intake(intake_data)

    # Look up country tier for priority scoring
    country_perm = db.query(CountryPermission).filter_by(
        country_code=case.country_code
    ).first()
    country_tier = country_perm.country_tier if country_perm else 3

    case.status = "intake_complete"
    case.intake_data = intake_data
    case.triage_level = triage
    case.chief_complaint = intake_data.get("main_symptom", case.chief_complaint)
    case.recommended_specialty = intake_data.get("recommended_specialty")
    case.icd11_codes = icd11_codes or []
    case.body_area = intake_data.get("body_area")
    case.red_flag_indicators = intake_data.get("red_flag_indicators", [])
    case.priority_score = compute_frontend_priority(triage, country_tier)
    case.intake_completed_at = datetime.now(timezone.utc)

    # Also create a symptom record
    db.add(SymptomRecord(
        case_id=case_id,
        symptoms_json=intake_data.get("associated_symptoms", []),
        icd11_codes=icd11_codes or [],
        severity=intake_data.get("severity"),
        transcript_text=intake_data.get("patient_summary"),
    ))

    _audit(db, "intake_complete", "case", case_id, actor_type="system",
           details={"triage_level": triage})
    db.commit()
    db.refresh(case)
    return case


def move_to_pending(db: Session, case_id: str) -> Case:
    """Move a case from intake_complete → pending (ready for doctor assignment)."""
    case = db.query(Case).filter_by(id=case_id).first()
    if not case:
        raise ValueError(f"Case {case_id} not found")
    case.status = "pending"
    _audit(db, "status_change", "case", case_id, actor_type="system",
           details={"new_status": "pending"})
    db.commit()
    db.refresh(case)
    return case


def assign_case(db: Session, case_id: str, doctor_id: str) -> Case:
    """Assign a case to a doctor."""
    case = db.query(Case).filter_by(id=case_id).first()
    if not case:
        raise ValueError(f"Case {case_id} not found")

    case.status = "assigned"
    case.assigned_doctor_id = doctor_id
    case.assigned_at = datetime.now(timezone.utc)

    _audit(db, "assign", "case", case_id, actor_id=doctor_id,
           actor_type="doctor", details={"doctor_id": doctor_id})
    db.commit()
    db.refresh(case)
    return case


def start_case(db: Session, case_id: str, doctor_id: str) -> Case:
    """Doctor starts working on a case (assigned → in_progress)."""
    case = db.query(Case).filter_by(id=case_id).first()
    if not case:
        raise ValueError(f"Case {case_id} not found")
    if case.assigned_doctor_id != doctor_id:
        raise PermissionError("Case not assigned to this doctor")

    case.status = "in_progress"
    _audit(db, "start", "case", case_id, actor_id=doctor_id, actor_type="doctor")
    db.commit()
    db.refresh(case)
    return case


def submit_response(db: Session, case_id: str, doctor_id: str,
                    guidance_text: str, is_emergency_referral: bool = False,
                    compliance_acknowledged: bool = True) -> DoctorResponse:
    """Doctor submits guidance for a case. Resolves the case."""
    case = db.query(Case).filter_by(id=case_id).first()
    if not case:
        raise ValueError(f"Case {case_id} not found")

    response = DoctorResponse(
        case_id=case_id,
        doctor_id=doctor_id,
        guidance_text=guidance_text,
        is_emergency_referral=is_emergency_referral,
        compliance_acknowledged=compliance_acknowledged,
    )
    db.add(response)

    case.status = "resolved"
    case.resolved_at = datetime.now(timezone.utc)

    _audit(db, "respond", "case", case_id, actor_id=doctor_id,
           actor_type="doctor", details={"is_emergency": is_emergency_referral})
    db.commit()
    db.refresh(response)
    return response


def escalate_case(db: Session, case_id: str, reason: str = "timeout") -> Case:
    """Escalate a case — boost to RED triage and re-enter queue."""
    case = db.query(Case).filter_by(id=case_id).first()
    if not case:
        raise ValueError(f"Case {case_id} not found")

    case.status = "escalated"
    case.triage_level = "RED"
    case.escalated_at = datetime.now(timezone.utc)
    case.assigned_doctor_id = None
    case.priority_score = compute_priority_score(case)

    _audit(db, "escalate", "case", case_id, actor_type="system",
           details={"reason": reason})
    db.commit()
    db.refresh(case)
    return case


def expire_and_requeue(db: Session, case_id: str) -> Case:
    """Expire an unresponded case and put it back in the queue."""
    case = db.query(Case).filter_by(id=case_id).first()
    if not case:
        raise ValueError(f"Case {case_id} not found")

    case.status = "pending"
    case.assigned_doctor_id = None
    case.assigned_at = None

    _audit(db, "expire_requeue", "case", case_id, actor_type="system")
    db.commit()
    db.refresh(case)
    return case


def close_case(db: Session, case_id: str) -> Case:
    """Close a resolved case."""
    case = db.query(Case).filter_by(id=case_id).first()
    if not case:
        raise ValueError(f"Case {case_id} not found")

    case.status = "closed"
    case.closed_at = datetime.now(timezone.utc)

    _audit(db, "close", "case", case_id, actor_type="system")
    db.commit()
    db.refresh(case)
    return case


def schedule_followup(db: Session, case_id: str, hours: int = 24,
                      channel: str = "sms") -> FollowUpSchedule:
    """Schedule a follow-up check on a resolved case."""
    from datetime import timedelta
    followup = FollowUpSchedule(
        case_id=case_id,
        scheduled_at=datetime.now(timezone.utc) + timedelta(hours=hours),
        channel=channel,
    )
    db.add(followup)
    _audit(db, "schedule_followup", "case", case_id, actor_type="system",
           details={"hours": hours, "channel": channel})
    db.commit()
    db.refresh(followup)
    return followup


def handle_followup_reply(db: Session, followup_id: str, reply: str) -> FollowUpSchedule:
    """
    Process a patient's follow-up reply (1=better, 2=same, 3=worse).
    If worse, create a new follow-up case.
    """
    fu = db.query(FollowUpSchedule).filter_by(id=followup_id).first()
    if not fu:
        raise ValueError(f"FollowUp {followup_id} not found")

    fu.patient_reply = reply
    fu.status = "replied"
    fu.replied_at = datetime.now(timezone.utc)

    if reply == "3":  # Worse
        # Create a follow-up case linked to the original
        original = db.query(Case).filter_by(id=fu.case_id).first()
        if original:
            new_case = Case(
                patient_id=original.patient_id,
                country_code=original.country_code,
                status="pending",
                triage_level="YELLOW",
                chief_complaint=f"Follow-up: {original.chief_complaint}",
                is_followup=True,
                parent_case_id=original.id,
                priority_score=get_base_score("YELLOW") + 10,
            )
            db.add(new_case)
            _audit(db, "followup_escalate", "case", fu.case_id,
                   actor_type="system", details={"reply": reply})

    db.commit()
    db.refresh(fu)
    return fu


def get_case_with_details(db: Session, case_id: str) -> dict | None:
    """Get a case with all related data (internal format)."""
    case = db.query(Case).filter_by(id=case_id).first()
    if not case:
        return None

    return {
        "id": case.id,
        "patient_id": case.patient_id,
        "patient_alias": case.patient_alias,
        "status": case.status,
        "triage_level": case.triage_level,
        "chief_complaint": case.chief_complaint,
        "country_code": case.country_code,
        "body_area": case.body_area,
        "red_flag_indicators": case.red_flag_indicators,
        "intake_data": case.intake_data,
        "icd11_codes": case.icd11_codes,
        "recommended_specialty": case.recommended_specialty,
        "priority_score": case.priority_score,
        "is_followup": case.is_followup,
        "parent_case_id": case.parent_case_id,
        "assigned_doctor_id": case.assigned_doctor_id,
        "permission_tier": case.permission_tier,
        "opened_at": case.opened_at.isoformat() if case.opened_at else None,
        "intake_completed_at": case.intake_completed_at.isoformat() if case.intake_completed_at else None,
        "assigned_at": case.assigned_at.isoformat() if case.assigned_at else None,
        "resolved_at": case.resolved_at.isoformat() if case.resolved_at else None,
        "symptom_records": [
            {
                "id": sr.id,
                "symptoms_json": sr.symptoms_json,
                "icd11_codes": sr.icd11_codes,
                "severity": sr.severity,
                "recorded_at": sr.recorded_at.isoformat() if sr.recorded_at else None,
            }
            for sr in case.symptom_records
        ],
        "responses": [
            {
                "id": r.id,
                "doctor_id": r.doctor_id,
                "guidance_text": r.guidance_text,
                "is_emergency_referral": r.is_emergency_referral,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in case.responses
        ],
        "followups": [
            {
                "id": f.id,
                "scheduled_at": f.scheduled_at.isoformat() if f.scheduled_at else None,
                "channel": f.channel,
                "status": f.status,
                "patient_reply": f.patient_reply,
            }
            for f in case.followups
        ],
    }


# ── Triage → frontend urgency mapping ──
TRIAGE_TO_URGENCY = {
    "RED": "Critical",
    "YELLOW": "High",
    "GREEN": "Low",
    "BLACK": "Expectant",
}


def get_case_for_frontend(db: Session, case_id: str) -> dict | None:
    """
    Return a case in the exact shape the frontend doctor portal expects.
    Matches the contract: caseId, patientAlias, country, countryTier, urgency,
    symptomSummary, painScore, symptomDuration, bodyArea, imageUrls, consentGiven,
    submittedAt, aiStructuredNotes, redFlagIndicators, priorityScore.
    """
    case = db.query(Case).filter_by(id=case_id).first()
    if not case:
        return None

    patient = db.query(Patient).filter_by(id=case.patient_id).first()
    country_perm = db.query(CountryPermission).filter_by(
        country_code=case.country_code
    ).first()

    intake = case.intake_data or {}
    image_urls = [
        f"/uploads/{img.file_path}" for img in case.images if img.file_path
    ]

    return {
        "caseId": case.id,
        "patientAlias": case.patient_alias or f"PT-{case.id[:4].upper()}",
        "country": country_perm.country_name if country_perm else case.country_code,
        "countryTier": country_perm.country_tier if country_perm else 3,
        "urgency": TRIAGE_TO_URGENCY.get(case.triage_level, "Low"),
        "symptomSummary": case.chief_complaint or intake.get("main_symptom", ""),
        "painScore": intake.get("severity", 0),
        "symptomDuration": intake.get("duration", ""),
        "bodyArea": case.body_area or intake.get("body_area", ""),
        "imageUrls": image_urls,
        "consentGiven": patient.consent_given if patient else False,
        "submittedAt": (
            case.opened_at.strftime("%Y-%m-%dT%H:%M:%SZ") if case.opened_at else None
        ),
        "aiStructuredNotes": intake.get("patient_summary", ""),
        "redFlagIndicators": case.red_flag_indicators or [],
        "priorityScore": case.priority_score or 0,
    }


def get_all_cases_for_frontend(db: Session, status: str | None = None,
                                limit: int = 50) -> list[dict]:
    """Return all cases in the frontend contract shape."""
    q = db.query(Case)
    if status:
        q = q.filter(Case.status == status)
    q = q.order_by(Case.priority_score.desc(), Case.opened_at.asc())
    cases = q.limit(limit).all()

    results = []
    for case in cases:
        patient = db.query(Patient).filter_by(id=case.patient_id).first()
        country_perm = db.query(CountryPermission).filter_by(
            country_code=case.country_code
        ).first()

        intake = case.intake_data or {}
        image_urls = [
            f"/uploads/{img.file_path}" for img in case.images if img.file_path
        ]

        results.append({
            "caseId": case.id,
            "patientAlias": case.patient_alias or f"PT-{case.id[:4].upper()}",
            "country": country_perm.country_name if country_perm else case.country_code,
            "countryTier": country_perm.country_tier if country_perm else 3,
            "urgency": TRIAGE_TO_URGENCY.get(case.triage_level, "Low"),
            "symptomSummary": case.chief_complaint or intake.get("main_symptom", ""),
            "painScore": intake.get("severity", 0),
            "symptomDuration": intake.get("duration", ""),
            "bodyArea": case.body_area or intake.get("body_area", ""),
            "imageUrls": image_urls,
            "consentGiven": patient.consent_given if patient else False,
            "submittedAt": (
                case.opened_at.strftime("%Y-%m-%dT%H:%M:%SZ") if case.opened_at else None
            ),
            "aiStructuredNotes": intake.get("patient_summary", ""),
            "redFlagIndicators": case.red_flag_indicators or [],
            "priorityScore": case.priority_score or 0,
        })

    return results
