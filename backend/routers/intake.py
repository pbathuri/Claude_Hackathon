"""
Intake router: handles new patient calls, intake conversation turns,
and intake completion with ICD-11 mapping.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from services.country_service import (
    parse_phone, check_teleconsult_allowed, get_or_create_patient, hash_phone,
)
from services.intake_service import intake_agent
from services.icd11_service import map_intake_to_icd11
from services.case_service import create_case, complete_intake, move_to_pending
from services.triage_service import check_emergency_keywords

router = APIRouter(prefix="/intake", tags=["intake"])


class StartIntakeRequest(BaseModel):
    phone_number: str
    language: str = "en"
    message: str | None = None


class StartIntakeResponse(BaseModel):
    session_id: str
    case_id: str
    country_code: str
    country_name: str
    permission_tier: str
    disclaimer: str | None
    ai_response: str | None = None


@router.post("/start", response_model=StartIntakeResponse)
async def start_intake(req: StartIntakeRequest, db: Session = Depends(get_db)):
    """
    Start a new intake session from an inbound call/message.
    1. Parse phone → detect country
    2. Check permission matrix
    3. Create patient + case
    4. Begin Claude intake conversation
    """
    # 1. Parse phone number
    phone_info = parse_phone(req.phone_number)
    if "error" in phone_info:
        raise HTTPException(status_code=400, detail=phone_info["error"])

    country_code = phone_info["country_code"]

    # 2. Check permissions
    perms = check_teleconsult_allowed(db, country_code)
    if not perms["allowed"]:
        raise HTTPException(
            status_code=403,
            detail=f"Teleconsultation not available: {perms.get('reason', 'unsupported country')}",
        )

    # 3. Create or find patient, create case
    patient = get_or_create_patient(
        db, phone_info["e164"], country_code, req.language
    )
    case = create_case(
        db,
        patient_id=patient.id,
        country_code=country_code,
        permission_tier=perms.get("permission_tier"),
    )

    # 4. Start intake conversation if initial message provided
    ai_response = None
    if req.message:
        ai_response = intake_agent.process_message(case.id, req.message)

    return StartIntakeResponse(
        session_id=case.id,
        case_id=case.id,
        country_code=country_code,
        country_name=phone_info.get("country_name", ""),
        permission_tier=perms.get("permission_tier", "unknown"),
        disclaimer=perms.get("disclaimer"),
        ai_response=ai_response,
    )


class IntakeMessageRequest(BaseModel):
    session_id: str
    message: str


class IntakeMessageResponse(BaseModel):
    ai_response: str
    is_complete: bool
    is_emergency: bool
    intake_data: dict | None = None
    icd11_codes: list | None = None


@router.post("/message", response_model=IntakeMessageResponse)
async def send_intake_message(req: IntakeMessageRequest, db: Session = Depends(get_db)):
    """
    Send a message in an ongoing intake conversation.
    When intake is complete, returns structured data + ICD-11 codes.
    """
    # Check for emergency keywords before sending to Claude
    is_keyword_emergency = check_emergency_keywords(req.message)

    # Process through Claude
    ai_response = intake_agent.process_message(req.session_id, req.message)
    session = intake_agent.sessions.get(req.session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = IntakeMessageResponse(
        ai_response=ai_response,
        is_complete=session.is_complete,
        is_emergency=session.is_emergency or is_keyword_emergency,
    )

    # If intake is complete, finalize the case
    if session.is_complete and session.intake_data:
        # Map symptoms to ICD-11 codes
        icd11_results = await map_intake_to_icd11(session.intake_data)
        icd11_flat = []
        for item in icd11_results:
            for code in item.get("icd11_codes", []):
                icd11_flat.append(code)

        # Update the case with intake data
        complete_intake(db, req.session_id, session.intake_data, icd11_flat)
        move_to_pending(db, req.session_id)

        result.intake_data = session.intake_data
        result.icd11_codes = icd11_results

        # Clean up session memory
        intake_agent.cleanup_session(req.session_id)

    return result
