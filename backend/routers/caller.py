"""
Caller API integration router.
These endpoints are designed for Teammate 2's voice/SMS caller-api pipeline.
Their LangGraph flow (Whisper STT → LLM conversation → Piper TTS) collects
symptoms via multi-turn voice/text, then submits the completed conversation
to these endpoints for triage, ICD-11 mapping, priority scoring, and case creation.

Integration flow:
  1. POST /caller/session/start     → phone parse, country detect, tier + disclaimer
  2. POST /caller/session/consent   → patient acknowledges disclaimer
  3. POST /caller/ai-turn           → each user turn (text and/or transcript from client)
  4. POST /caller/browser-stt/push  → optional: persist browser Web Speech segments (Redis)
  5. POST /caller/stt               → optional: multipart audio → OpenAI Whisper (multilingual STT)
  6. POST /caller/session/submit    → completed symptoms → case creation + triage + ICD-11
  7. GET  /caller/session/{id}      → check case status (frontend contract shape)
  8. GET  /caller/disclosure/{cc}   → get verbal disclosure script for a country

Language handling:
  - Language is auto-detected from user's first message (or explicit via request)
  - User text is translated to English for KG traversal + clinical processing
  - AI responses are generated in English, then translated back to user's language
  - Verbal disclosure is translated for informed consent

Where conversation data goes: the web simulator (static/caller.html) sends turns to /caller/ai-turn
and finalizes with /caller/session/submit. Twilio voice uses /twilio/* webhooks and _submit_twilio_case.
The external LangGraph agent (src/main.py) calls the same session/start, consent, submit endpoints.
TTS for the browser is POST /caller/tts (ElevenLabs). STT is browser Web Speech, optional Redis sync,
and/or POST /caller/stt (Whisper) for recorded audio — not ElevenLabs.
"""
import os
import re

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
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
from services.triage_service import check_emergency_keywords, get_base_score, build_triage_breakdown
from safety.red_flag_rules import detect_red_flags
from services.icd11_service import map_intake_to_icd11, search_icd11
from services.language_service import (
    detect_language,
    get_language_config,
    translate_to_english,
    translate_from_english,
    translate_disclosure,
    build_emergency_message,
    get_emergency_number,
    SUPPORTED_LANGUAGES,
)
from config import (
    is_knowledge_graph_enabled, OPENAI_API_KEY,
    CONVERSATION_MODEL, CONVERSATION_MAX_TOKENS,
    ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL_ID,
    MAX_TURNS_BEFORE_COMPLETE, MIN_SYMPTOMS_FOR_COMPLETE,
    STALE_TURNS_FOR_COMPLETE, GRAPH_CONFIDENCE_THRESHOLD,
)

import logging
from services import session_store
from services.navigator_store import get_navigator, persist_navigator, clear_navigator

kg_logger = logging.getLogger(__name__)

_anthropic_client = None


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _anthropic_client


HF_MEDICAL_MODEL = "microsoft/BioGPT-Large"
HF_CHAT_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"


def _call_huggingface_medical(system_prompt: str, messages: list, user_message: str) -> str | None:
    """Call HuggingFace Inference API as secondary LLM for medical intake."""
    import httpx

    hf_token = os.environ.get("HF_TOKEN", "")
    if not hf_token:
        return None

    prompt_parts = [f"System: {system_prompt[:500]}"]
    for m in messages[-4:]:
        role = "Patient" if m["role"] == "user" else "Assistant"
        prompt_parts.append(f"{role}: {m['content']}")
    prompt_parts.append("Assistant:")
    prompt = "\n".join(prompt_parts)

    try:
        resp = httpx.post(
            f"https://api-inference.huggingface.co/models/{HF_CHAT_MODEL}",
            headers={"Authorization": f"Bearer {hf_token}"},
            json={
                "inputs": prompt,
                "parameters": {"max_new_tokens": 150, "temperature": 0.7, "return_full_text": False},
            },
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data:
                text = data[0].get("generated_text", "").strip()
                if text and len(text) > 10:
                    first_line = text.split("\n")[0].strip()
                    return first_line if first_line else text[:200]
    except Exception:
        pass
    return None


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

    # Track session language and translate disclosure if needed
    session_store.case_language_set(case.id, req.language)
    if req.language != "en":
        verbal_disclosure = translate_disclosure(verbal_disclosure, req.language)

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
    from datetime import datetime, timezone

    from domain.models_ext import ConsentEventRecord

    case = db.query(Case).filter_by(id=req.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Mark consent on patient and disclaimer shown on case
    patient = db.query(Patient).filter_by(id=case.patient_id).first()
    if patient:
        patient.consent_given = req.consent_given
    case.disclaimer_shown = True

    db.add(
        ConsentEventRecord(
            case_id=case.id,
            patient_id=case.patient_id,
            consent_type="capability_disclaimer",
            accepted=req.consent_given,
            channel="web",
            metadata_json={
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    )

    db.commit()
    return {
        "status": "consent_recorded",
        "case_id": case.id,
        "consent_given": req.consent_given,
        "consent_timestamp": datetime.now(timezone.utc).isoformat(),
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

    # ── Layered red flag detection (Phase 03 safety engine) ────────────
    all_text = " ".join(req.symptoms) + " " + req.transcript_summary
    session_lang = session_store.case_language_get(req.case_id) or "en"
    red_flag_result = detect_red_flags(
        text=all_text,
        language=session_lang,
        english_text=all_text if session_lang == "en" else None,
    )
    is_emergency = red_flag_result.is_emergency

    # Also check individual symptoms with keyword layer
    red_flags = []
    for symptom in req.symptoms:
        if check_emergency_keywords(symptom):
            red_flags.append(symptom)
    if check_emergency_keywords(req.transcript_summary):
        from services.triage_service import EMERGENCY_KEYWORDS
        lower_text = all_text.lower()
        for kw in EMERGENCY_KEYWORDS:
            if kw in lower_text:
                red_flags.append(kw.title())
    # Merge safety engine flags
    for flag_info in red_flag_result.flags:
        raw_flag = flag_info.get("flag") or flag_info.get("matched_text") or ""
        flag_name = str(raw_flag).split(":")[-1].title() if raw_flag else ""
        if flag_name and flag_name not in red_flags:
            red_flags.append(flag_name)
    red_flags = list(dict.fromkeys(red_flags))

    # Determine triage level from severity + red flags
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

    # ICD-11 mapping (non-blocking — returns empty on failure)
    try:
        icd11_results = await map_intake_to_icd11(intake_data)
        icd11_flat = [
            code
            for item in icd11_results
            for code in item.get("icd11_codes", [])
        ]
    except Exception as exc:
        kg_logger.warning("[ICD-11] Mapping failed (non-blocking): %s", exc)
        icd11_flat = []

    # ── Knowledge Graph: navigate symptoms for enrichment ────────────
    kg_insights = {}
    if is_knowledge_graph_enabled():
        try:
            from routers.knowledge_graph import _graph
            if _graph:
                nav = get_navigator(req.case_id, _graph)
                kg_context = nav.process_symptoms(req.symptoms)
                persist_navigator(req.case_id, nav)

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
                kg_logger.info("[KG] Case %s enriched: specialty=%s confidence=%.2f",
                              req.case_id,
                              intake_data.get("recommended_specialty"),
                              kg_insights.get("graph_confidence", 0))
        except Exception as exc:
            kg_logger.warning("[KG] Graph enrichment failed (non-blocking): %s", exc)

    # ── Build explainable triage breakdown (Phase 01) ────────────────
    country_perm = db.query(CountryPermission).filter_by(
        country_code=case.country_code
    ).first()
    _country_tier = country_perm.country_tier if country_perm else 3

    triage_breakdown = build_triage_breakdown(
        triage_level=triage_level,
        severity=req.severity,
        red_flags=red_flags,
        symptom_count=len(req.symptoms),
        duration=req.duration,
        kg_confidence=kg_insights.get("graph_confidence", 0.0),
        country_tier=_country_tier,
    )
    intake_data["triage_breakdown"] = triage_breakdown

    # Complete the case intake
    case = complete_intake(db, req.case_id, intake_data, icd11_flat)

    # Store triage breakdown and detected language on case
    case.triage_breakdown = triage_breakdown
    case.detected_language = session_lang
    case.priority_score = triage_breakdown["total_priority"]
    case.conversation_log = {
        "channel": "web_caller",
        "turns": req.message_history,
        "transcript_summary": req.transcript_summary,
        "symptoms_final": req.symptoms,
        "triage_level": triage_level,
    }
    db.commit()
    db.refresh(case)

    case = move_to_pending(db, req.case_id)

    return SubmitConversationResponse(
        case_id=case.id,
        patient_alias=case.patient_alias or "",
        country=country_perm.country_name if country_perm else case.country_code,
        country_tier=_country_tier,
        urgency=TRIAGE_TO_URGENCY.get(triage_level, "Low"),
        triage_level=triage_level,
        priority_score=triage_breakdown["total_priority"],
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

    # Base frontend shape (includes portal-mapped status, kgInsights, symptomSummary)
    result = get_case_for_frontend(db, case_id)

    # Add doctor response info (status comes from get_case_for_frontend)
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


# ─────────────────────────────────────────────────────────────────────────────
# 7. AI CONVERSATION TURN — web simulator drives symptom collection via KG
# ─────────────────────────────────────────────────────────────────────────────
class AITurnRequest(BaseModel):
    case_id: str
    user_message: str
    turn_number: int = 1
    collected_symptoms: list[str] = []
    language: str = "en"
    message_history: list[dict] = []


class AITurnResponse(BaseModel):
    ai_message: str
    detected_symptoms: list[str]
    all_symptoms_so_far: list[str]
    suggested_questions: list[dict] = []
    is_emergency: bool = False
    emergency_flags: list[str] = []
    should_complete: bool = False
    turn_number: int
    activated_conditions: list[dict] = []
    body_systems: list[str] = []
    severity_extracted: int | None = None
    duration_extracted: str | None = None
    body_area_extracted: str | None = None
    transcript_summary: str | None = None


def _extract_symptoms_from_text(text: str, graph) -> list[str]:
    """Fuzzy-match words/phrases in user text against KG symptom nodes."""
    from knowledge_graph.graph_engine import NodeType
    text_lower = text.lower()
    found = []
    for node in graph.get_nodes_by_type(NodeType.SYMPTOM):
        if node.name.lower() in text_lower:
            found.append(node.name)
    return found


_FALLBACK_QUESTIONS = [
    "How long have you been experiencing these symptoms?",
    "On a scale of 1 to 10, how severe is the discomfort?",
    "Do you have any other symptoms you haven't mentioned?",
    "Do you have any chronic conditions or medical history I should know about?",
    "Are you currently taking any medications?",
    "Do you have any known allergies?",
    "Has anything made the symptoms better or worse?",
    "Have you traveled recently or been exposed to anyone who is sick?",
]


def _generate_fallback_message(
    turn: int,
    new_symptoms: list[str],
    all_symptoms: list[str],
    suggested_questions: list[dict],
    is_emergency: bool,
    emergency_flags: list[str],
    should_complete: bool,
) -> str:
    """Rule-based fallback when Claude API is unavailable. Uses turn-indexed
    questions to avoid repetition even without LLM context."""
    if is_emergency:
        flags_str = ", ".join(emergency_flags) if emergency_flags else "critical symptoms"
        return (
            f"I'm detecting potential emergency indicators: {flags_str}. "
            "Please call emergency services immediately. "
            "Do not wait — your safety is the priority."
        )

    if should_complete:
        symptom_str = ", ".join(all_symptoms) if all_symptoms else "your symptoms"
        return (
            f"Thank you for sharing. I've recorded: {symptom_str}. "
            "Your case is being submitted to a physician for review. "
            "If your condition worsens, please seek emergency care."
        )

    # Pick a question by turn index (never repeats across turns)
    q_idx = max(0, turn - 2)
    next_q = _FALLBACK_QUESTIONS[q_idx % len(_FALLBACK_QUESTIONS)]

    if turn == 1:
        if new_symptoms:
            return (
                f"Thank you for calling. I understand you're experiencing "
                f"{', '.join(new_symptoms)}. {next_q}"
            )
        return f"Thank you for calling. I'm here to help. {next_q}"

    if new_symptoms:
        return f"I see, you also have {', '.join(new_symptoms)}. {next_q}"
    return f"Thank you for that information. {next_q}"


def _generate_claude_response(
    turn_number: int,
    user_message: str,
    all_symptoms: list[str],
    suggested_questions: list[dict],
    activated_conditions: list[dict],
    body_systems: list[str],
    is_emergency: bool,
    emergency_flags: list[str],
    should_complete: bool,
    message_history: list[dict],
    *,
    use_knowledge_graph: bool = True,
    country_code: str = "",
    previous_ai_messages: list[str] | None = None,
) -> str:
    """
    Call Claude to generate a conversational AI response; KG context optional.
    Includes anti-repetition logic and localized emergency numbers.
    Response is always in English (translation to user language happens in the caller).
    """
    # Filter KG suggested questions to exclude ones already asked
    asked_qs = set()
    if previous_ai_messages:
        for msg in previous_ai_messages:
            asked_qs.add(msg.lower()[:80])
    fresh_questions = []
    if suggested_questions:
        for q in suggested_questions:
            q_text = q.get("question", "")
            if not any(q_text.lower() in asked for asked in asked_qs):
                fresh_questions.append(q)

    if use_knowledge_graph:
        kg_parts = []
        if activated_conditions:
            cond_str = ", ".join(
                f"{c['name']} (score: {c['score']})" for c in activated_conditions[:5]
            )
            kg_parts.append(f"Likely conditions: {cond_str}")
        if body_systems:
            kg_parts.append(f"Body systems: {', '.join(body_systems[:3])}")
        if fresh_questions:
            q_str = "\n".join(
                f"  - {q['question']}" for q in fresh_questions[:2]
            )
            kg_parts.append(f"Suggested new questions (pick ONE or ask your own):\n{q_str}")
        kg_block = "\n".join(kg_parts) if kg_parts else ""
        context_header = "CLINICAL CONTEXT"
        followup_rule = (
            "- Use the clinical context to guide your ONE follow-up question.\n"
            "- You may use a suggested question OR ask your own based on intake progress.\n"
        )
    else:
        kg_block = ""
        context_header = "CONTEXT"
        followup_rule = "- Ask one relevant follow-up question based on intake progress.\n"

    # Localized emergency number
    emerg = get_emergency_number(country_code)
    emergency_line = ""
    if is_emergency:
        flags_str = ", ".join(emergency_flags) if emergency_flags else "critical symptoms"
        emergency_line = (
            f"\nEMERGENCY DETECTED: {flags_str}. "
            f"Tell the patient to call {emerg['name']} at {emerg['number']} IMMEDIATELY. "
            "Their safety is the absolute priority. Be direct and urgent."
        )

    completion_line = ""
    if should_complete and not is_emergency:
        sym_str = ", ".join(all_symptoms) if all_symptoms else "the reported symptoms"
        completion_line = (
            f"\nCONVERSATION COMPLETE: Summarize the symptoms collected ({sym_str}) "
            "and inform the patient their case is being submitted to a qualified "
            "physician for review. Thank them for their patience."
        )

    # Anti-repetition context
    anti_rep = ""
    if previous_ai_messages:
        recent = previous_ai_messages[-2:]  # last 2 messages
        anti_rep = (
            "\nANTI-REPETITION: Your recent messages were:\n"
            + "\n".join(f'  - "{m[:100]}"' for m in recent)
            + "\nDo NOT repeat these phrases or questions. Ask something NEW and different. "
            "If you already asked about a topic, move on to a different aspect."
        )

    # Build a structured intake progression plan so Claude knows what to ask next
    info_collected = []
    info_needed = []
    if all_symptoms:
        info_collected.append(f"Symptoms: {', '.join(all_symptoms)}")
    else:
        info_needed.append("main symptoms")

    # Check what we still need
    has_duration = any("day" in m.get("content", "").lower() or "week" in m.get("content", "").lower()
                       or "hour" in m.get("content", "").lower() or "month" in m.get("content", "").lower()
                       for m in message_history if m.get("role") == "user")
    has_severity = any(c.isdigit() for m in message_history for c in m.get("content", "") if m.get("role") == "user")
    has_history = any(kw in " ".join(m.get("content", "") for m in message_history if m.get("role") == "user").lower()
                      for kw in ("diabetes", "asthma", "hypertension", "medication", "medicine", "allergy", "allergic", "history", "condition"))

    if has_duration:
        info_collected.append("duration mentioned")
    else:
        info_needed.append("how long they've had symptoms")
    if has_severity:
        info_collected.append("severity mentioned")
    else:
        info_needed.append("severity on 1-10 scale")
    if has_history:
        info_collected.append("medical history touched on")
    else:
        info_needed.append("medical history, medications, allergies")

    progress_block = ""
    if info_collected:
        progress_block += f"ALREADY COLLECTED: {'; '.join(info_collected)}\n"
    if info_needed:
        progress_block += f"STILL NEED TO ASK ABOUT: {'; '.join(info_needed)}\n"
    progress_block += f"Turn {turn_number} of {MAX_TURNS_BEFORE_COMPLETE} max.\n"

    system_prompt = (
        "You are a warm, empathetic health assistant conducting a symptom intake "
        "phone call. You gather information so a real physician can review the case.\n\n"
        "RULES:\n"
        "- You are NOT a doctor. Never diagnose, prescribe, or speculate.\n"
        "- Keep each response to 1-2 short sentences. This is a phone call — be brief.\n"
        "- NEVER repeat a question or phrase from a previous turn.\n"
        "- Acknowledge what the patient just said, then ask ONE new question.\n"
        "- Progress through the intake: symptoms → duration → severity → history → medications → allergies.\n"
        "- RESPOND IN ENGLISH ONLY.\n\n"
        f"INTAKE PROGRESS:\n{progress_block}\n"
        f"{context_header}:\n{kg_block}\n\n"
        f"{followup_rule}"
        f"{anti_rep}{emergency_line}{completion_line}"
    )

    messages = []
    for msg in message_history:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            content = msg["content"]
            if not isinstance(content, str):
                content = str(content)
            messages.append({"role": msg["role"], "content": content})
    messages.append({"role": "user", "content": user_message})

    # --- Primary: Claude API ---
    try:
        client = _get_anthropic()
        response = client.messages.create(
            model=CONVERSATION_MODEL,
            max_tokens=CONVERSATION_MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        )
        result = response.content[0].text
        kg_logger.info("[Claude] Turn %d OK: %s", turn_number, result[:80])
        return result
    except Exception as exc:
        kg_logger.error("[Claude] API call failed: %s", exc, exc_info=True)

    # --- Secondary: HuggingFace medical model via Inference API ---
    try:
        hf_result = _call_huggingface_medical(system_prompt, messages, user_message)
        if hf_result:
            kg_logger.info("[HuggingFace] Turn %d OK: %s", turn_number, hf_result[:80])
            return hf_result
    except Exception as exc:
        kg_logger.warning("[HuggingFace] Fallback also failed: %s", exc)

    # --- Tertiary: rule-based fallback ---
    kg_logger.warning("[Fallback] Using rule-based for turn %d", turn_number)
    return _generate_fallback_message(
        turn=turn_number,
        new_symptoms=[],
        all_symptoms=all_symptoms,
        suggested_questions=fresh_questions if use_knowledge_graph else suggested_questions,
        is_emergency=is_emergency,
        emergency_flags=emergency_flags,
        should_complete=should_complete,
    )


@router.post("/ai-turn", response_model=AITurnResponse)
async def ai_conversation_turn(req: AITurnRequest):
    """
    Process one conversation turn from the web simulator.

    Language pipeline:
    1. Detect language from user message (or use explicit `language` field)
    2. Translate user message to English for KG traversal + symptom extraction
    3. Run all clinical processing in English
    4. Generate AI response in English
    5. Translate AI response back to user's language

    Anti-repetition: tracks previous AI messages per case to prevent loops.
    """
    # ── 0. Language detection and translation ──
    user_lang = req.language
    if req.turn_number <= 1 or user_lang == "auto":
        detected = detect_language(req.user_message)
        if detected != "en":
            user_lang = detected
            kg_logger.info("[AI Turn] Detected language: %s for case %s", user_lang, req.case_id)
    session_store.case_language_set(req.case_id, user_lang)

    # Translate to English for all clinical processing
    english_message = req.user_message
    if user_lang != "en":
        english_message = translate_to_english(req.user_message, user_lang)
        kg_logger.info("[AI Turn] Translated user input: %s → '%s'", user_lang, english_message[:80])

    # ── 1. Try to get the KG graph (non-fatal if disabled or unavailable) ──
    graph = None
    if is_knowledge_graph_enabled():
        try:
            from routers.knowledge_graph import get_graph
            graph = get_graph()
        except Exception as exc:
            kg_logger.warning("[AI Turn] KG not available, using keyword-only mode: %s", exc)

    # ── 2. Extract symptoms from English-translated message ──
    detected_symptoms: list[str] = []
    if graph:
        detected_symptoms = _extract_symptoms_from_text(english_message, graph)
    else:
        common = [
            "fever", "headache", "cough", "nausea", "vomiting", "diarrhea",
            "fatigue", "dizziness", "chest pain", "abdominal pain", "rash",
            "sore throat", "body aches", "chills", "shortness of breath",
            "back pain", "joint pain", "loss of appetite", "weight loss",
        ]
        text_lower = english_message.lower()
        detected_symptoms = [s for s in common if s in text_lower]

    # ── 3. Merge with previously collected symptoms (deduplicate) ──
    all_symptoms = list(dict.fromkeys(req.collected_symptoms + detected_symptoms))

    # ── 4. KG navigation ──
    suggested_questions: list[dict] = []
    activated_conditions: list[dict] = []
    body_systems: list[str] = []
    graph_confidence = 0.0

    if graph and all_symptoms:
        try:
            nav = get_navigator(req.case_id, graph)
            context = nav.process_symptoms(all_symptoms)
            persist_navigator(req.case_id, nav)

            suggested_questions = context.get("suggested_questions", [])[:3]
            activated_conditions = [
                {"name": c["condition"], "score": round(c["activation_score"], 2)}
                for c in context.get("activated_conditions", [])[:5]
            ]
            body_systems = [
                s["system"] for s in context.get("activated_body_systems", [])
            ]
            graph_confidence = context.get("graph_confidence", 0.0)
        except Exception as exc:
            kg_logger.warning("[AI Turn] KG navigation failed (non-blocking): %s", exc)

    # ── 5. Emergency check (on English text for reliable keyword matching) ──
    is_emergency = check_emergency_keywords(english_message)
    emergency_flags: list[str] = []
    if is_emergency:
        from services.triage_service import EMERGENCY_KEYWORDS
        lower = english_message.lower()
        emergency_flags = [kw.title() for kw in EMERGENCY_KEYWORDS if kw in lower]

    # ── 6. Determine completion (smarter heuristics from config) ──
    new_count = len([s for s in detected_symptoms if s not in req.collected_symptoms])
    prev_stale = session_store.case_stale_get(req.case_id)
    if new_count == 0:
        session_store.case_stale_set(req.case_id, prev_stale + 1)
    else:
        session_store.case_stale_set(req.case_id, 0)

    stale_turns = session_store.case_stale_get(req.case_id)
    should_complete = (
        is_emergency
        or len(all_symptoms) >= MIN_SYMPTOMS_FOR_COMPLETE
        or graph_confidence > GRAPH_CONFIDENCE_THRESHOLD
        or req.turn_number >= MAX_TURNS_BEFORE_COMPLETE
        or stale_turns >= STALE_TURNS_FOR_COMPLETE
    )

    # ── 7. Extract severity, duration, body area from English message ──
    severity_extracted = None
    sev_match = re.search(
        r'(\d{1,2})\s*(?:out of|/)\s*10|pain\s*level\s*(\d{1,2})|severity\s*(\d{1,2})',
        english_message, re.IGNORECASE,
    )
    if sev_match:
        raw = next((g for g in sev_match.groups() if g is not None), None)
        if raw and 1 <= int(raw) <= 10:
            severity_extracted = int(raw)

    duration_extracted = None
    dur_match = re.search(
        r'(\d+\s*(?:days?|weeks?|months?|hours?|years?))',
        english_message, re.IGNORECASE,
    )
    if dur_match:
        duration_extracted = dur_match.group(1)
    else:
        since_match = re.search(
            r'since\s+(yesterday|last\s+\w+)',
            english_message, re.IGNORECASE,
        )
        if since_match:
            duration_extracted = f"since {since_match.group(1)}"

    body_area_extracted = body_systems[0] if body_systems else None

    # ── 8. Build message history in ENGLISH for Claude ──
    claude_history = []
    for msg in req.message_history:
        if msg.get("role") not in ("user", "assistant"):
            continue
        body = (msg.get("content") or msg.get("text") or "").strip()
        if body:
            claude_history.append({"role": msg["role"], "content": body})

    # ── 9. Get country code for localized emergency numbers ──
    case_country = ""
    try:
        from database import SessionLocal
        db = SessionLocal()
        case = db.query(Case).filter_by(id=req.case_id).first()
        if case:
            case_country = case.country_code or ""
        db.close()
    except Exception:
        pass

    # ── 10. Generate AI response via Claude (in English) ──
    previous_msgs = session_store.case_ai_history_get(req.case_id)
    ai_message_english = _generate_claude_response(
        turn_number=req.turn_number,
        user_message=english_message,
        all_symptoms=all_symptoms,
        suggested_questions=suggested_questions,
        activated_conditions=activated_conditions,
        body_systems=body_systems,
        is_emergency=is_emergency,
        emergency_flags=emergency_flags,
        should_complete=should_complete,
        message_history=claude_history,
        use_knowledge_graph=graph is not None,
        country_code=case_country,
        previous_ai_messages=previous_msgs,
    )

    # Track for anti-repetition
    session_store.case_ai_history_append(req.case_id, ai_message_english)

    # ── 11. Translate AI response to user's language ──
    ai_message = ai_message_english
    if user_lang != "en":
        ai_message = translate_from_english(ai_message_english, user_lang)
        kg_logger.info("[AI Turn] Translated response en→%s", user_lang)

    # ── 12. Generate clinical summary on completion (always in English) ──
    transcript_summary = None
    if should_complete and all_symptoms:
        try:
            client = _get_anthropic()
            summary_resp = client.messages.create(
                model=CONVERSATION_MODEL,
                max_tokens=100,
                system=(
                    "You are a clinical note writer. Produce a single concise "
                    "sentence summarizing the patient's presenting symptoms for "
                    "a physician handoff. No diagnosis."
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Symptoms: {', '.join(all_symptoms)}. "
                        f"Duration: {duration_extracted or 'unknown'}. "
                        f"Severity: {severity_extracted or 'unknown'}/10. "
                        f"Body area: {body_area_extracted or 'unknown'}."
                    ),
                }],
            )
            transcript_summary = summary_resp.content[0].text
        except Exception as exc:
            kg_logger.warning("[Claude] Summary generation failed: %s", exc)
            transcript_summary = f"Patient reports: {', '.join(all_symptoms)}."

        # Clean up ephemeral turn tracking (KG navigator kept for submit/backprop)
        session_store.case_stale_delete(req.case_id)
        session_store.case_ai_history_delete(req.case_id)
        session_store.case_language_delete(req.case_id)

    return AITurnResponse(
        ai_message=ai_message,
        detected_symptoms=detected_symptoms,
        all_symptoms_so_far=all_symptoms,
        suggested_questions=suggested_questions,
        is_emergency=is_emergency,
        emergency_flags=emergency_flags,
        should_complete=should_complete,
        turn_number=req.turn_number + 1,
        activated_conditions=activated_conditions,
        body_systems=body_systems,
        severity_extracted=severity_extracted,
        duration_extracted=duration_extracted,
        body_area_extracted=body_area_extracted,
        transcript_summary=transcript_summary,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 8. BROWSER STT — Web Speech transcript segments in Redis (or in-memory fallback)
# ─────────────────────────────────────────────────────────────────────────────
class BrowserSttPushRequest(BaseModel):
    case_id: str
    text: str
    is_final: bool = True
    lang: str = ""


@router.post("/browser-stt/push")
async def browser_stt_push(req: BrowserSttPushRequest):
    """
    Persist a segment from the browser's Web Speech API (final or interim rollup).
    Keyed by case_id; use GET /caller/browser-stt/{case_id} to read merged transcript.
    """
    from services.browser_stt_store import push_segment

    doc = push_segment(req.case_id, req.text, lang=req.lang, is_final=req.is_final)
    return {
        "case_id": req.case_id,
        "segment_count": len(doc.get("segments", [])),
        "full_text": doc.get("full_text", ""),
    }


@router.get("/browser-stt/{case_id}")
async def browser_stt_get(case_id: str):
    """Return merged browser STT transcript and segments for a case."""
    from services.browser_stt_store import get_state

    return get_state(case_id)


@router.delete("/browser-stt/{case_id}")
async def browser_stt_clear(case_id: str):
    """Clear stored browser STT for a case (e.g. after successful submit)."""
    from services.browser_stt_store import clear_state

    clear_state(case_id)
    return {"status": "cleared", "case_id": case_id}


# ─────────────────────────────────────────────────────────────────────────────
# 9. SPEECH-TO-TEXT — OpenAI Whisper (multilingual); not ElevenLabs
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/stt")
async def speech_to_text_whisper(
    file: UploadFile = File(...),
    language: str | None = Form(None),
):
    """
    Transcribe uploaded audio with OpenAI Whisper (whisper-1).
    Omit `language` for auto-detect; pass ISO-639-1 code (e.g. es, hi) to bias recognition.
    """
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY not configured (required for Whisper STT)",
        )

    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file too large (max 25MB)")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")

    import httpx

    fname = file.filename or "audio.webm"
    mime = file.content_type or "application/octet-stream"
    files = {"file": (fname, content, mime)}
    data: dict = {"model": "whisper-1"}
    if language:
        data["language"] = language

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files=files,
            data=data,
        )

    if resp.status_code != 200:
        kg_logger.warning("[Whisper STT] OpenAI error: %s", resp.text[:500])
        raise HTTPException(
            status_code=502,
            detail=f"Whisper transcription failed: {resp.text[:300]}",
        )

    body = resp.json()
    return {
        "text": body.get("text", ""),
        "language": language,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 10. TEXT-TO-SPEECH — ElevenLabs (speech output only)
# ─────────────────────────────────────────────────────────────────────────────
class TTSRequest(BaseModel):
    text: str


@router.post("/tts")
async def text_to_speech(req: TTSRequest):
    """Convert text to speech using ElevenLabs API (TTS only — STT is /caller/stt Whisper)."""
    import httpx
    from fastapi.responses import StreamingResponse

    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=503, detail="ELEVENLABS_API_KEY not configured")

    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")

    # Truncate to prevent excessively long TTS (Twilio/ElevenLabs limits)
    text = req.text[:2000]

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream",
                headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
                json={
                    "text": text,
                    "model_id": ELEVENLABS_MODEL_ID,
                    "voice_settings": {"stability": 0.75, "similarity_boost": 0.75},
                },
                timeout=15.0,
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="TTS service timeout")
    except Exception as exc:
        kg_logger.warning("[TTS] ElevenLabs error: %s", exc)
        raise HTTPException(status_code=502, detail="TTS service unavailable")

    if resp.status_code != 200:
        err_body = resp.text[:500]
        kg_logger.warning("[TTS] ElevenLabs HTTP %d: %s", resp.status_code, err_body)
        raise HTTPException(
            status_code=502,
            detail=f"TTS error {resp.status_code}: {err_body}",
        )

    return StreamingResponse(
        iter([resp.content]),
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# 11. IMAGE UPLOAD — camera capture from web simulator
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    import os
    import uuid as _uuid
    os.makedirs("static/uploads", exist_ok=True)
    ext = file.filename.split(".")[-1] if file.filename else "jpg"
    name = f"{_uuid.uuid4().hex[:12]}.{ext}"
    path = f"static/uploads/{name}"
    with open(path, "wb") as f:
        f.write(await file.read())
    return {"url": f"/static/uploads/{name}", "filename": name}
