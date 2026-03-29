"""
Cases router: case lifecycle management, doctor assignment, responses, follow-ups.
"""
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import Case, AuditLog
from services.case_service import (
    get_case_with_details, get_case_for_frontend, get_all_cases_for_frontend,
    assign_case, start_case, submit_response,
    escalate_case, close_case, schedule_followup, handle_followup_reply,
)
from services.priority_queue import get_next_case_for_doctor, get_queue_snapshot
from auth.middleware import get_current_actor

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("/")
def list_cases(
    status: str | None = None,
    country_code: str | None = None,
    triage_level: str | None = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    """List cases with optional filters."""
    q = db.query(Case)
    if status:
        q = q.filter(Case.status == status)
    if country_code:
        q = q.filter(Case.country_code == country_code)
    if triage_level:
        q = q.filter(Case.triage_level == triage_level)
    q = q.order_by(Case.priority_score.desc(), Case.opened_at.asc())
    cases = q.limit(limit).all()

    return [
        {
            "id": c.id,
            "status": c.status,
            "triage_level": c.triage_level,
            "country_code": c.country_code,
            "chief_complaint": c.chief_complaint,
            "priority_score": c.priority_score,
            "recommended_specialty": c.recommended_specialty,
            "assigned_doctor_id": c.assigned_doctor_id,
            "is_followup": c.is_followup,
            "opened_at": c.opened_at.isoformat() if c.opened_at else None,
        }
        for c in cases
    ]


@router.get("/queue")
def get_queue(doctor_id: str | None = None, db: Session = Depends(get_db)):
    """Get the priority queue snapshot, optionally scored for a specific doctor."""
    return get_queue_snapshot(db, doctor_id)


@router.get("/patient-cases", tags=["frontend"])
def list_patient_cases(
    status: str | None = None,
    limit: int = Query(default=200, le=500),
    db: Session = Depends(get_db),
):
    """
    List all cases in the frontend doctor-portal contract shape.
    Returns: caseId, patientAlias, country, countryTier, urgency,
    symptomSummary, painScore, symptomDuration, bodyArea, imageUrls,
    consentGiven, submittedAt, aiStructuredNotes, redFlagIndicators, priorityScore,
    status (portal-mapped), kgInsights (when intake stored KG enrichment).
    Intake is persisted as Case.intake_data (see schemas.intake.IntakeData).
    """
    return get_all_cases_for_frontend(db, status=status, limit=limit)


@router.get("/patient-cases/{case_id}", tags=["frontend"])
def get_patient_case(case_id: str, db: Session = Depends(get_db)):
    """
    Get a single case in the frontend doctor-portal contract shape.
    """
    result = get_case_for_frontend(db, case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Case not found")
    return result


@router.get("/stream", tags=["frontend"])
async def cases_stream():
    """
    Server-Sent Events: pending case counts for doctor portal live refresh.
    """

    async def event_generator():
        while True:
            db = SessionLocal()
            try:
                pending = (
                    db.query(Case)
                    .filter(Case.status.in_(["pending", "intake_complete"]))
                    .count()
                )
                total = db.query(Case).count()
                payload = json.dumps({"pending": pending, "total": total})
                yield f"data: {payload}\n\n"
            finally:
                db.close()
            await asyncio.sleep(4)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)):
    """Get full case details including symptoms, responses, and follow-ups (internal format)."""
    result = get_case_with_details(db, case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Case not found")
    return result


class AssignRequest(BaseModel):
    doctor_id: str


@router.api_route("/{case_id}/assign", methods=["POST", "PATCH"])
def assign(
    case_id: str,
    req: AssignRequest,
    db: Session = Depends(get_db),
    _actor: dict = Depends(get_current_actor),
):
    """Manually assign a case to a doctor (POST or PATCH; body: doctor_id)."""
    try:
        case = assign_case(db, case_id, req.doctor_id)
        return {
            "success": True,
            "status": "assigned",
            "case_id": case.id,
            "doctor_id": req.doctor_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/next")
def pull_next_case(req: AssignRequest, db: Session = Depends(get_db)):
    """
    Doctor pulls the next highest-priority case from the queue.
    Score is computed relative to the doctor's country and specialty.
    """
    case = get_next_case_for_doctor(db, req.doctor_id)
    if not case:
        return {"status": "empty", "message": "No pending cases in queue"}
    return {
        "status": "assigned",
        "case_id": case.id,
        "triage_level": case.triage_level,
        "country_code": case.country_code,
        "chief_complaint": case.chief_complaint,
        "priority_score": case.priority_score,
    }


@router.post("/{case_id}/start")
def start(
    case_id: str,
    req: AssignRequest,
    db: Session = Depends(get_db),
    _actor: dict = Depends(get_current_actor),
):
    """Doctor starts working on an assigned case."""
    try:
        case = start_case(db, case_id, req.doctor_id)
        return {"status": "in_progress", "case_id": case.id}
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))


class ResponseRequest(BaseModel):
    doctor_id: str
    guidance_text: str
    is_emergency_referral: bool = False
    compliance_acknowledged: bool = True


@router.post("/{case_id}/respond")
def respond(
    case_id: str,
    req: ResponseRequest,
    db: Session = Depends(get_db),
    _actor: dict = Depends(get_current_actor),
):
    """
    Doctor submits guidance for a case. This resolves the case
    and schedules follow-up checks at 24h and 48h.
    """
    try:
        response = submit_response(
            db, case_id, req.doctor_id, req.guidance_text,
            req.is_emergency_referral, req.compliance_acknowledged,
        )
        # Schedule follow-ups
        schedule_followup(db, case_id, hours=24)
        schedule_followup(db, case_id, hours=48)
        return {
            "status": "resolved",
            "response_id": response.id,
            "case_id": case_id,
            "is_emergency_referral": req.is_emergency_referral,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{case_id}/escalate")
def escalate(
    case_id: str,
    db: Session = Depends(get_db),
    _actor: dict = Depends(get_current_actor),
):
    """Manually escalate a case to RED priority."""
    try:
        case = escalate_case(db, case_id, reason="manual_escalation")
        return {"status": "escalated", "case_id": case.id, "triage_level": "RED"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{case_id}/close")
def close(
    case_id: str,
    db: Session = Depends(get_db),
    _actor: dict = Depends(get_current_actor),
):
    """Close a resolved case."""
    try:
        case = close_case(db, case_id)
        return {"status": "closed", "case_id": case.id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class FollowUpReplyRequest(BaseModel):
    followup_id: str
    reply: str  # "1"=better, "2"=same, "3"=worse


@router.post("/{case_id}/followup-reply")
def followup_reply(case_id: str, req: FollowUpReplyRequest, db: Session = Depends(get_db)):
    """Process a patient's follow-up reply."""
    try:
        fu = handle_followup_reply(db, req.followup_id, req.reply)
        return {
            "status": fu.status,
            "reply": fu.patient_reply,
            "escalated": req.reply == "3",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{case_id}/audit")
def get_audit_trail(case_id: str, db: Session = Depends(get_db)):
    """Get the audit trail for a specific case."""
    entries = (
        db.query(AuditLog)
        .filter(AuditLog.resource_type == "case", AuditLog.resource_id == case_id)
        .order_by(AuditLog.timestamp.asc())
        .all()
    )
    return [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "actor_id": e.actor_id,
            "actor_type": e.actor_type,
            "action": e.action,
            "details": e.details,
        }
        for e in entries
    ]


@router.get("/{case_id}/fhir", tags=["interoperability"])
def get_case_fhir_bundle(case_id: str, db: Session = Depends(get_db)):
    """
    Export a case as a FHIR R4 Bundle (Phase 06 Interoperability).
    Returns Patient, Encounter, Conditions, Severity Observation, Consent,
    and Practitioner resources for interoperability with hospital systems.
    """
    from models import Patient as PatientModel, DoctorProfile, SymptomRecord
    from adapters.fhir_mapper import build_case_bundle

    case = db.query(Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    patient = db.query(PatientModel).filter_by(id=case.patient_id).first()
    symptoms = []
    symptom_rec = db.query(SymptomRecord).filter_by(case_id=case_id).first()
    if symptom_rec and symptom_rec.symptoms_json:
        symptoms = symptom_rec.symptoms_json

    doctor_name = ""
    doctor_specialty = ""
    if case.assigned_doctor_id:
        doc = db.query(DoctorProfile).filter_by(id=case.assigned_doctor_id).first()
        if doc:
            doctor_name = doc.full_name
            doctor_specialty = doc.specialization

    intake = case.intake_data or {}
    severity = intake.get("severity", 5)

    return build_case_bundle(
        case_id=case.id,
        patient_id=case.patient_id,
        status=case.status,
        triage_level=case.triage_level or "GREEN",
        symptoms=symptoms,
        severity=severity,
        icd11_codes=case.icd11_codes,
        country_code=case.country_code,
        chief_complaint=case.chief_complaint or "",
        consent_given=patient.consent_given if patient else True,
        doctor_id=case.assigned_doctor_id,
        doctor_name=doctor_name,
        doctor_specialty=doctor_specialty,
    )
