"""
Twilio Voice Webhook router.
Handles inbound phone calls via Twilio, collecting symptoms through
multi-turn voice conversation using <Gather> speech recognition.

Flow: Twilio POST /twilio/voice → verbal disclosure + first Gather
      → POST /twilio/gather (loop) → submit case or hangup
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
import logging

from database import get_db
from models import CountryPermission
from services.country_service import (
    parse_phone, check_teleconsult_allowed, get_or_create_patient,
)
from services.case_service import create_case, complete_intake, move_to_pending
from services.triage_service import check_emergency_keywords
from services.icd11_service import map_intake_to_icd11
from config import is_knowledge_graph_enabled
from routers.caller import _build_verbal_disclosure, _generate_fallback_message

try:
    from routers.caller import _generate_claude_response
except ImportError:
    _generate_claude_response = None

try:
    from routers.caller import _generate_fallback_message
except ImportError:
    _generate_fallback_message = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/twilio", tags=["twilio-voice"])

_call_sessions: dict[str, dict] = {}


# ─── XML helpers ────────────────────────────────────────────────────────────

def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _twiml(body: str) -> Response:
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n{body}\n</Response>'
    return Response(content=xml, media_type="application/xml")


# ─── POST /twilio/voice — incoming call webhook ────────────────────────────

@router.post("/voice")
async def incoming_call(request: Request, db: Session = Depends(get_db)):
    """
    Twilio webhook fired when someone dials the service number.
    Starts a case, plays the verbal disclosure, and opens the first
    speech Gather for symptom collection.
    """
    form = await request.form()
    caller_number = form.get("From", "")
    call_sid = form.get("CallSid", "unknown")

    phone_info = parse_phone(caller_number)
    if "error" in phone_info:
        phone_info = {"country_code": "NG", "e164": caller_number or "+0000000000",
                      "country_name": "Nigeria"}
        logger.warning("[Twilio] Could not parse %s — defaulting to NG for demo", caller_number)

    country_code = phone_info["country_code"]

    perms = check_teleconsult_allowed(db, country_code)
    if not perms["allowed"]:
        DEMO_FALLBACK = "NG"
        logger.info("[Twilio] Country %s not in permissions — falling back to %s for demo",
                    country_code, DEMO_FALLBACK)
        country_code = DEMO_FALLBACK
        phone_info["country_code"] = DEMO_FALLBACK
        phone_info["country_name"] = "Nigeria"
        perms = check_teleconsult_allowed(db, country_code)

    patient = get_or_create_patient(db, phone_info["e164"], country_code, "en")
    case = create_case(
        db,
        patient_id=patient.id,
        country_code=country_code,
        permission_tier=perms.get("permission_tier"),
    )

    country_perm = (
        db.query(CountryPermission).filter_by(country_code=country_code).first()
    )
    verbal_disclosure = _build_verbal_disclosure(country_perm)

    sentences = verbal_disclosure.split(". ")
    shortened = ". ".join(sentences[:2]) + "." if len(sentences) > 2 else verbal_disclosure

    _call_sessions[call_sid] = {
        "case_id": case.id,
        "turn": 1,
        "collected_symptoms": [],
        "message_history": [],
        "country_code": country_code,
    }

    logger.info("[Twilio] Incoming call %s from %s — case %s", call_sid, country_code, case.id)

    safe_disc = _escape_xml(shortened)
    return _twiml(
        f'  <Say voice="Polly.Joanna">Welcome to the WHO Health Access Service. {safe_disc}</Say>\n'
        '  <Pause length="1"/>\n'
        '  <Gather input="speech" action="/twilio/gather" method="POST"'
        ' speechTimeout="auto" language="en-US">\n'
        '    <Say voice="Polly.Joanna">Please describe your main symptoms.'
        " What brings you to call today?</Say>\n"
        "  </Gather>\n"
        "  <Say voice=\"Polly.Joanna\">I didn't catch that. Please call back when you're ready.</Say>"
    )


# ─── POST /twilio/gather — speech recognition result ───────────────────────

@router.post("/gather")
async def gather_speech(request: Request, db: Session = Depends(get_db)):
    """
    Twilio <Gather> callback — receives transcribed speech and drives
    the symptom-collection conversation turn by turn.
    """
    form = await request.form()
    speech_result = form.get("SpeechResult", "")
    call_sid = form.get("CallSid", "unknown")

    session = _call_sessions.get(call_sid)
    if not session:
        return _twiml(
            '  <Say voice="Polly.Joanna">Your session has expired. '
            "Please call back to start again.</Say>\n"
            "  <Hangup/>"
        )

    turn = session["turn"]
    collected = session["collected_symptoms"]
    session["message_history"].append({"role": "user", "content": speech_result})

    # ── 1. Extract symptoms ──────────────────────────────────────────────
    graph = None
    if is_knowledge_graph_enabled():
        try:
            from routers.knowledge_graph import get_graph
            graph = get_graph()
        except Exception:
            pass

    detected_symptoms: list[str] = []
    if graph:
        try:
            from routers.caller import _extract_symptoms_from_text
            detected_symptoms = _extract_symptoms_from_text(speech_result, graph)
        except ImportError:
            pass

    if not detected_symptoms:
        _COMMON_SYMPTOMS = [
            "fever", "headache", "cough", "nausea", "vomiting", "diarrhea",
            "fatigue", "dizziness", "chest pain", "abdominal pain", "rash",
            "sore throat", "body aches", "chills", "shortness of breath",
            "back pain", "joint pain", "loss of appetite", "weight loss",
        ]
        text_lower = speech_result.lower()
        detected_symptoms = [s for s in _COMMON_SYMPTOMS if s in text_lower]

    # ── 2. Merge symptoms ────────────────────────────────────────────────
    all_symptoms = list(dict.fromkeys(collected + detected_symptoms))
    session["collected_symptoms"] = all_symptoms

    # ── 3. KG navigation ─────────────────────────────────────────────────
    suggested_questions: list[dict] = []
    activated_conditions: list[dict] = []
    body_systems: list[str] = []
    graph_confidence = 0.0

    if graph and all_symptoms:
        try:
            from routers.knowledge_graph import _navigator_sessions
            from knowledge_graph.navigator import ConversationNavigator

            case_id = session["case_id"]
            if case_id not in _navigator_sessions:
                _navigator_sessions[case_id] = ConversationNavigator(
                    graph, case_id=case_id,
                )
            nav = _navigator_sessions[case_id]
            context = nav.process_symptoms(all_symptoms)

            suggested_questions = context.get("suggested_questions", [])[:3]
            graph_confidence = context.get("graph_confidence", 0.0)
            activated_conditions = [
                {"name": c["condition"], "score": round(c["activation_score"], 2)}
                for c in context.get("activated_conditions", [])[:5]
            ]
            body_systems = [
                s["system"] for s in context.get("activated_body_systems", [])
            ]
        except Exception as exc:
            logger.warning("[Twilio] KG navigation failed (non-blocking): %s", exc)

    # ── 4. Emergency check ───────────────────────────────────────────────
    is_emergency = check_emergency_keywords(speech_result)
    emergency_flags: list[str] = []
    if is_emergency:
        from services.triage_service import EMERGENCY_KEYWORDS
        lower = speech_result.lower()
        emergency_flags = [kw.title() for kw in EMERGENCY_KEYWORDS if kw in lower]

    # ── 5. Completion criteria ───────────────────────────────────────────
    should_complete = (
        len(all_symptoms) >= 5
        or graph_confidence > 0.7
        or turn >= 6
        or is_emergency
    )

    # ── 6. Generate AI response ──────────────────────────────────────────
    ai_response = None
    prior_history = session["message_history"][:-1]

    if _generate_claude_response is not None:
        try:
            ai_response = _generate_claude_response(
                turn_number=turn,
                user_message=speech_result,
                all_symptoms=all_symptoms,
                suggested_questions=suggested_questions,
                activated_conditions=activated_conditions,
                body_systems=body_systems,
                is_emergency=is_emergency,
                emergency_flags=emergency_flags,
                should_complete=should_complete,
                message_history=prior_history,
                use_knowledge_graph=graph is not None,
            )
        except Exception as exc:
            logger.warning("[Twilio] Claude response failed, using fallback: %s", exc)

    if ai_response is None and _generate_fallback_message is not None:
        try:
            ai_response = _generate_fallback_message(
                turn=turn,
                new_symptoms=detected_symptoms,
                all_symptoms=all_symptoms,
                suggested_questions=suggested_questions,
                is_emergency=is_emergency,
                emergency_flags=emergency_flags,
                should_complete=should_complete,
            )
        except Exception:
            pass

    if ai_response is None:
        ai_response = _generate_fallback_message(
            turn=turn,
            new_symptoms=detected_symptoms,
            all_symptoms=all_symptoms,
            suggested_questions=suggested_questions,
            is_emergency=is_emergency,
            emergency_flags=emergency_flags,
            should_complete=should_complete,
        )

    session["message_history"].append({"role": "assistant", "content": ai_response})
    session["turn"] = turn + 1

    safe_resp = _escape_xml(ai_response)

    # ── 7. Emergency → advise caller + hangup ────────────────────────────
    if is_emergency:
        try:
            await _submit_twilio_case(db, session)
        except Exception as exc:
            logger.error("[Twilio] Emergency case submission failed: %s", exc)
        _call_sessions.pop(call_sid, None)

        flags_str = ", ".join(emergency_flags) if emergency_flags else "critical symptoms"
        return _twiml(
            f'  <Say voice="Polly.Joanna">I am detecting potential emergency indicators: '
            f"{_escape_xml(flags_str)}. Please hang up and call emergency services "
            f"immediately. Your local emergency number is 911 or 112.</Say>\n"
            f"  <Hangup/>"
        )

    # ── 8. Complete → submit case + summary + hangup ─────────────────────
    if should_complete:
        try:
            await _submit_twilio_case(db, session)
        except Exception as exc:
            logger.error("[Twilio] Case submission failed: %s", exc)
        _call_sessions.pop(call_sid, None)

        symptom_str = _escape_xml(
            ", ".join(all_symptoms) if all_symptoms else "your symptoms"
        )
        return _twiml(
            f'  <Say voice="Polly.Joanna">{safe_resp}</Say>\n'
            '  <Pause length="1"/>\n'
            f'  <Say voice="Polly.Joanna">Your case has been submitted. A physician will review '
            f"{symptom_str} and respond shortly. "
            "If your condition worsens, please seek emergency care. Goodbye.</Say>\n"
            "  <Hangup/>"
        )

    # ── 9. Continue → respond + gather next turn ─────────────────────────
    return _twiml(
        f'  <Say voice="Polly.Joanna">{safe_resp}</Say>\n'
        '  <Gather input="speech" action="/twilio/gather" method="POST"'
        ' speechTimeout="auto" language="en-US">\n'
        '    <Say voice="Polly.Joanna">Go ahead, I\'m listening.</Say>\n'
        "  </Gather>\n"
        "  <Say voice=\"Polly.Joanna\">I didn't catch that. Please call back when you're ready.</Say>"
    )


# ─── Internal: submit case from voice session ──────────────────────────────

async def _submit_twilio_case(db: Session, session: dict) -> None:
    """Build intake data from the voice session state and finalize the case."""
    case_id = session["case_id"]
    symptoms = session["collected_symptoms"]
    history = session["message_history"]

    transcript = " | ".join(f"{m['role']}: {m['content']}" for m in history)

    all_text = " ".join(symptoms) + " " + transcript
    is_emergency = check_emergency_keywords(all_text)
    red_flags: list[str] = []
    if is_emergency:
        from services.triage_service import EMERGENCY_KEYWORDS
        lower = all_text.lower()
        red_flags = [kw.title() for kw in EMERGENCY_KEYWORDS if kw in lower]

    if is_emergency:
        triage_level = "RED"
    elif red_flags:
        triage_level = "YELLOW"
    else:
        triage_level = "GREEN"

    intake_data = {
        "main_symptom": symptoms[0] if symptoms else "",
        "duration": "",
        "severity": 5,
        "associated_symptoms": symptoms[1:] if len(symptoms) > 1 else [],
        "medical_history": [],
        "current_medications": [],
        "allergies": [],
        "triage_level": triage_level,
        "recommended_specialty": "general",
        "body_area": "",
        "red_flag_indicators": red_flags,
        "patient_summary": transcript[:500],
    }

    icd11_results = await map_intake_to_icd11(intake_data)
    icd11_flat = [
        code
        for item in icd11_results
        for code in item.get("icd11_codes", [])
    ]

    complete_intake(db, case_id, intake_data, icd11_flat)
    move_to_pending(db, case_id)

    logger.info(
        "[Twilio] Case %s submitted — %d symptoms, triage=%s",
        case_id, len(symptoms), triage_level,
    )
