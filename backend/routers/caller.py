"""
Caller API integration router.
These endpoints are designed for Teammate 2's voice/SMS caller-api pipeline.
Their LangGraph flow (Whisper STT → LLM conversation → Piper TTS) collects
symptoms via multi-turn voice/text, then submits the completed conversation
to these endpoints for triage, ICD-11 mapping, priority scoring, and case creation.

Integration flow:
  1. POST /caller/session/start     → phone parse, country detect, tier + disclaimer
  2. POST /caller/session/consent   → patient acknowledges disclaimer
  3. POST /caller/session/submit    → completed symptoms → case creation + triage + ICD-11
  4. GET  /caller/session/{id}      → check case status (frontend contract shape)
  5. GET  /caller/disclosure/{cc}   → get verbal disclosure script for a country
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Patient, Case, CountryPermission
from services.country_service import (
    parse_phone, check_teleconsult_allowed, get_or_create_patient,
)
from services.case_service import (
    create_case, complete_intake, move_to_pending,
    get_case_for_frontend, URGENCY_SCORES, TIER_SCORES,
    compute_frontend_priority, TRIAGE_TO_URGENCY,
)
from services.triage_service import check_emergency_keywords, get_base_score
from services.icd11_service import map_intake_to_icd11, search_icd11

import logging
kg_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/caller", tags=["caller-api"])


# ─────────────────────────────────────────────────────────────────────────────
# 1. START SESSION — called when inbound call/message arrives
# ─────────────────────────────────────────────────────────────────────────────
class SessionStartRequest(BaseModel):
    phone_number: str
    language: str = "en"


class SessionStartResponse(BaseModel):
    session_id: str
    case_id: str
    patient_alias: str
    country_code: str
    country_name: str
    country_tier: int
    permission_tier: str
    allows_teleconsult: bool
    allows_ai_triage: bool
    requires_local_doctor: bool
    disclaimer: str | None
    verbal_disclosure: str | None
    data_law: str | None


@router.post("/session/start", response_model=SessionStartResponse)
async def start_session(req: SessionStartRequest, db: Session = Depends(get_db)):
    """
    Start a new caller session. Call this when a phone call or WhatsApp
    message arrives.

    Returns country detection, permission tier, disclaimer text for the
    verbal disclosure the SDD requires, and a case_id to track this session.
    """
    # Parse phone → detect country
    phone_info = parse_phone(req.phone_number)
    if "error" in phone_info:
        raise HTTPException(status_code=400, detail=phone_info["error"])

    country_code = phone_info["country_code"]

    # Check permissions
    perms = check_teleconsult_allowed(db, country_code)
    if not perms["allowed"]:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "teleconsult_not_available",
                "country": phone_info.get("country_name", country_code),
                "reason": perms.get("reason", "Country not in permission matrix"),
            },
        )

    # Create patient + case
    patient = get_or_create_patient(db, phone_info["e164"], country_code, req.language)
    case = create_case(
        db,
        patient_id=patient.id,
        country_code=country_code,
        permission_tier=perms.get("permission_tier"),
    )

    # Build verbal disclosure script (per SDD Section 6.4.1)
    country_perm = db.query(CountryPermission).filter_by(country_code=country_code).first()
    verbal_disclosure = _build_verbal_disclosure(country_perm)

    return SessionStartResponse(
        session_id=case.id,
        case_id=case.id,
        patient_alias=case.patient_alias or "",
        country_code=country_code,
        country_name=phone_info.get("country_name", ""),
        country_tier=country_perm.country_tier if country_perm else 4,
        permission_tier=perms.get("permission_tier", "unknown"),
        allows_teleconsult=perms.get("allowed", False),
        allows_ai_triage=perms.get("allows_ai_triage", False),
        requires_local_doctor=perms.get("requires_local_doctor", True),
        disclaimer=perms.get("disclaimer"),
        verbal_disclosure=verbal_disclosure,
        data_law=perms.get("data_law"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. CONSENT — patient acknowledges disclaimer
# ─────────────────────────────────────────────────────────────────────────────
class ConsentRequest(BaseModel):
    case_id: str
    consent_given: bool = True


@router.post("/session/consent")
async def record_consent(req: ConsentRequest, db: Session = Depends(get_db)):
    """
    Record that the patient acknowledged the capability disclaimer.
    Per SDD Section 3, this must happen before any clinical exchange.
    """
    case = db.query(Case).filter_by(id=req.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Mark consent on patient and disclaimer shown on case
    patient = db.query(Patient).filter_by(id=case.patient_id).first()
    if patient:
        patient.consent_given = req.consent_given
    case.disclaimer_shown = True

    db.commit()
    return {
        "status": "consent_recorded",
        "case_id": case.id,
        "consent_given": req.consent_given,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. SUBMIT COMPLETED CONVERSATION — the key integration endpoint
# ─────────────────────────────────────────────────────────────────────────────
class SubmitConversationRequest(BaseModel):
    """
    Submit the completed voice conversation from the caller-api pipeline.
    This is what the caller-api sends when conversation_complete=true.
    """
    case_id: str
    symptoms: list[str]                          # from graph state
    message_history: list[dict] = []             # full conversation turns
    transcript_summary: str = ""                 # LLM-generated summary
    severity: int = 5                            # pain/severity 1-10
    duration: str = ""                           # symptom duration
    body_area: str = ""                          # from body map or LLM
    medical_history: list[str] = []
    current_medications: list[str] = []
    allergies: list[str] = []


class SubmitConversationResponse(BaseModel):
    """Response after processing the completed conversation."""
    case_id: str
    patient_alias: str
    country: str
    country_tier: int
    urgency: str
    triage_level: str
    priority_score: float
    symptom_summary: str
    pain_score: int
    symptom_duration: str
    body_area: str
    icd11_codes: list[dict]
    red_flag_indicators: list[str]
    ai_structured_notes: str
    is_emergency: bool
    status: str
    kg_insights: dict = {}  # knowledge graph analysis


@router.post("/session/submit", response_model=SubmitConversationResponse)
async def submit_conversation(req: SubmitConversationRequest, db: Session = Depends(get_db)):
    """
    Submit the completed voice/text conversation for processing.

    The caller-api pipeline calls this when conversation_complete=true.
    The backend will:
      1. Detect red-flag emergency keywords
      2. Determine triage level from symptom severity
      3. Map symptoms to ICD-11 codes via NLM API
      4. Compute priority score (urgencyScore + tierScore)
      5. Update the case record
      6. Move case to pending queue for doctor assignment

    Returns the fully processed case in a shape ready for the doctor portal.
    """
    case = db.query(Case).filter_by(id=req.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Detect red flags from symptom list and transcript
    red_flags = []
    all_text = " ".join(req.symptoms) + " " + req.transcript_summary
    for symptom in req.symptoms:
        if check_emergency_keywords(symptom):
            red_flags.append(symptom)
    if check_emergency_keywords(req.transcript_summary):
        # Extract specific red flag phrases
        from services.triage_service import EMERGENCY_KEYWORDS
        lower_text = all_text.lower()
        for kw in EMERGENCY_KEYWORDS:
            if kw in lower_text:
                # Capitalize nicely for frontend
                red_flags.append(kw.title())
    red_flags = list(dict.fromkeys(red_flags))  # deduplicate, preserve order

    # Determine triage level from severity + red flags
    is_emergency = len(red_flags) > 0 and any(
        kw in all_text.lower() for kw in [
            "chest pain", "can't breathe", "cannot breathe", "stroke",
            "unconscious", "unresponsive", "suicidal", "self-harm",
        ]
    )
    if is_emergency:
        triage_level = "RED"
    elif req.severity >= 7 or len(red_flags) > 0:
        triage_level = "YELLOW"
    elif req.severity >= 4:
        triage_level = "YELLOW"
    else:
        triage_level = "GREEN"

    # Build the symptom summary
    symptom_summary = " and ".join(req.symptoms[:3]) if req.symptoms else ""
    if req.duration:
        symptom_summary += f" for {req.duration}"

    # Build structured intake data (same shape our Claude intake produces)
    intake_data = {
        "main_symptom": req.symptoms[0] if req.symptoms else "",
        "duration": req.duration,
        "severity": req.severity,
        "associated_symptoms": req.symptoms[1:] if len(req.symptoms) > 1 else [],
        "medical_history": req.medical_history,
        "current_medications": req.current_medications,
        "allergies": req.allergies,
        "triage_level": triage_level,
        "recommended_specialty": "general",  # default, can be refined
        "body_area": req.body_area,
        "red_flag_indicators": red_flags,
        "patient_summary": req.transcript_summary or symptom_summary,
    }

    # ICD-11 mapping
    icd11_results = await map_intake_to_icd11(intake_data)
    icd11_flat = []
    for item in icd11_results:
        for code in item.get("icd11_codes", []):
            icd11_flat.append(code)

    # ── Knowledge Graph: navigate symptoms for enrichment ────────────
    kg_insights = {}
    try:
        from routers.knowledge_graph import _graph, _navigator_sessions
        if _graph:
            from knowledge_graph.navigator import ConversationNavigator
            nav = ConversationNavigator(_graph, case_id=req.case_id)
            kg_context = nav.process_symptoms(req.symptoms)

            # Use graph to refine recommended specialty
            if kg_context.get("suggested_specialties"):
                intake_data["recommended_specialty"] = kg_context["suggested_specialties"][0]["specialty"]

            # Store graph insights in intake_data for the doctor portal
            kg_insights = {
                "activated_conditions": kg_context.get("activated_conditions", [])[:5],
                "suggested_specialties": kg_context.get("suggested_specialties", [])[:3],
                "graph_confidence": kg_context.get("graph_confidence", 0),
                "body_systems": kg_context.get("activated_body_systems", [])[:3],
            }
            intake_data["kg_insights"] = kg_insights

            # Store navigator for future backpropagation
            _navigator_sessions[req.case_id] = nav
            kg_logger.info("[KG] Case %s enriched: specialty=%s confidence=%.2f",
                          req.case_id,
                          intake_data.get("recommended_specialty"),
                          kg_insights.get("graph_confidence", 0))
    except Exception as exc:
        kg_logger.warning("[KG] Graph enrichment failed (non-blocking): %s", exc)

    # Complete the case intake
    case = complete_intake(db, req.case_id, intake_data, icd11_flat)
    case = move_to_pending(db, req.case_id)

    # Get country info for response
    country_perm = db.query(CountryPermission).filter_by(
        country_code=case.country_code
    ).first()

    return SubmitConversationResponse(
        case_id=case.id,
        patient_alias=case.patient_alias or "",
        country=country_perm.country_name if country_perm else case.country_code,
        country_tier=country_perm.country_tier if country_perm else 4,
        urgency=TRIAGE_TO_URGENCY.get(triage_level, "Low"),
        triage_level=triage_level,
        priority_score=case.priority_score or 0,
        symptom_summary=symptom_summary,
        pain_score=req.severity,
        symptom_duration=req.duration,
        body_area=req.body_area,
        icd11_codes=icd11_flat,
        red_flag_indicators=red_flags,
        ai_structured_notes=req.transcript_summary or symptom_summary,
        is_emergency=is_emergency,
        status=case.status,
        kg_insights=kg_insights,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. GET SESSION STATUS — check what happened after submission
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/session/{case_id}")
async def get_session_status(case_id: str, db: Session = Depends(get_db)):
    """
    Get the current status of a caller session / case.
    Returns the frontend contract shape if the case has been triaged,
    plus doctor response if one exists.
    """
    case = db.query(Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Base frontend shape
    result = get_case_for_frontend(db, case_id)

    # Add status + doctor response info
    result["status"] = case.status
    result["assignedDoctorId"] = case.assigned_doctor_id

    if case.responses:
        latest = case.responses[-1]
        result["doctorResponse"] = {
            "guidanceText": latest.guidance_text,
            "isEmergencyReferral": latest.is_emergency_referral,
            "respondedAt": latest.created_at.isoformat() if latest.created_at else None,
        }
    else:
        result["doctorResponse"] = None

    if case.followups:
        result["followUps"] = [
            {
                "id": f.id,
                "scheduledAt": f.scheduled_at.isoformat() if f.scheduled_at else None,
                "channel": f.channel,
                "status": f.status,
                "patientReply": f.patient_reply,
            }
            for f in case.followups
        ]
    else:
        result["followUps"] = []

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 5. VERBAL DISCLOSURE — per SDD Section 6.4.1
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/disclosure/{country_code}")
async def get_disclosure(country_code: str, db: Session = Depends(get_db)):
    """
    Get the verbal capability disclosure script for a country.
    Per SDD Section 6.4.1, the physician must read this before the call connects.
    The caller-api should play/read the patient-facing version during call start.
    """
    perm = db.query(CountryPermission).filter_by(country_code=country_code).first()
    if not perm:
        raise HTTPException(
            status_code=404,
            detail=f"Country {country_code} not in permission matrix",
        )

    return {
        "country_code": perm.country_code,
        "country_name": perm.country_name,
        "country_tier": perm.country_tier,
        "permission_tier": perm.permission_tier,
        "patient_disclaimer": perm.disclaimer_text,
        "verbal_disclosure_script": _build_verbal_disclosure(perm),
        "physician_status_bar": _build_physician_status(perm),
        "capability_card": _build_capability_card(perm),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6. EMERGENCY CHECK — quick check if text contains emergency keywords
# ─────────────────────────────────────────────────────────────────────────────
class EmergencyCheckRequest(BaseModel):
    text: str


@router.post("/emergency-check")
async def emergency_check(req: EmergencyCheckRequest):
    """
    Quick check if caller's speech contains emergency keywords.
    The caller-api can call this after each STT transcription to detect
    emergencies mid-conversation without waiting for completion.
    """
    is_emergency = check_emergency_keywords(req.text)
    flags = []
    if is_emergency:
        from services.triage_service import EMERGENCY_KEYWORDS
        lower = req.text.lower()
        flags = [kw.title() for kw in EMERGENCY_KEYWORDS if kw in lower]

    return {
        "is_emergency": is_emergency,
        "red_flags": flags,
        "action": "ROUTE_TO_EMERGENCY_SERVICES" if is_emergency else "CONTINUE_INTAKE",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — disclosure text builders (per SDD Section 3)
# ─────────────────────────────────────────────────────────────────────────────
TIER_CAPABILITIES = {
    1: {
        "can": [
            "examine your symptoms and give you a formal diagnosis",
            "recommend a treatment plan and home care steps",
            "prescribe medication through this platform",
            "refer you to a specialist or in-person facility",
        ],
        "cannot": [],
        "label": "Full diagnosis, treatment & prescribing authorized",
    },
    2: {
        "can": [
            "examine your symptoms and give you a formal diagnosis",
            "recommend a treatment plan and home care steps",
            "refer you to a specialist or in-person facility",
        ],
        "cannot": [
            "prescribe medication directly — you will need to obtain a prescription from a local provider",
        ],
        "label": "Full diagnosis & treatment authorized — prescribing not available",
    },
    3: {
        "can": [
            "examine your symptoms and give you a formal diagnosis",
            "provide home management guidance",
            "recommend referral to a local provider or facility",
        ],
        "cannot": [
            "prescribe medication through this platform",
            "order laboratory tests or imaging directly",
        ],
        "label": "Diagnosis authorized — treatment managed by local provider",
    },
    4: {
        "can": [
            "discuss your symptoms and assess urgency",
            "provide general health guidance",
            "recommend whether you should see a local provider",
        ],
        "cannot": [
            "give a formal medical diagnosis",
            "prescribe medication",
            "order tests or referrals",
        ],
        "label": "Clinical guidance only — formal diagnosis not yet authorized",
    },
}


def _build_verbal_disclosure(perm: CountryPermission | None) -> str:
    """Build the verbal disclosure script per SDD Section 6.4.1."""
    if not perm:
        return ""

    tier = perm.country_tier or 4
    caps = TIER_CAPABILITIES.get(tier, TIER_CAPABILITIES[4])

    can_text = ", ".join(caps["can"][:-1]) + f", and {caps['can'][-1]}" if len(caps["can"]) > 1 else caps["can"][0]
    cannot_parts = []
    for item in caps["cannot"]:
        cannot_parts.append(item)

    script = (
        f"Before we begin, I am required to let you know what I can help you with today. "
        f"In your region, I am authorized to {can_text}."
    )
    if cannot_parts:
        cannot_text = "; ".join(cannot_parts)
        script += f" I am not authorized to {cannot_text}."

    script += (
        " This session is not a substitute for emergency care. "
        "If your condition is life-threatening, please contact emergency services immediately. "
        "Do you understand and wish to continue?"
    )
    return script


def _build_physician_status(perm: CountryPermission | None) -> dict:
    """Build the physician session status bar per SDD Section 3.3."""
    if not perm:
        return {}

    tier = perm.country_tier or 4
    caps = TIER_CAPABILITIES.get(tier, TIER_CAPABILITIES[4])
    colors = {1: "green", 2: "teal", 3: "blue", 4: "amber"}

    return {
        "jurisdiction": perm.country_name,
        "tier": tier,
        "label": caps["label"],
        "color": colors.get(tier, "amber"),
        "can_diagnose": tier <= 3,
        "can_treat": tier <= 2,
        "can_prescribe": tier <= 1,
        "can_refer": tier <= 2,
    }


def _build_capability_card(perm: CountryPermission | None) -> dict:
    """Build the patient-facing capability disclosure card per SDD Section 3.2."""
    if not perm:
        return {}

    tier = perm.country_tier or 4
    caps = TIER_CAPABILITIES.get(tier, TIER_CAPABILITIES[4])

    return {
        "tier": tier,
        "label": caps["label"],
        "authorized": caps["can"],
        "not_authorized": caps["cannot"],
        "emergency_notice": (
            "This session is not a substitute for emergency care. "
            "If your condition is life-threatening, please contact "
            "emergency services immediately."
        ),
    }
