"""
Twilio Voice Webhook router.
Handles inbound phone calls via Twilio, collecting symptoms through
multi-turn voice conversation using <Gather> speech recognition.

Pipeline per turn:
  1. Twilio <Gather> → speech-to-text (caller's words)
  2. Language detection + translation to English
  3. KG symptom extraction + navigation (activated conditions, follow-up Qs)
  4. Claude API generates contextual response using KG context
  5. ElevenLabs TTS converts response to natural speech audio
  6. Twilio <Play> streams the audio back to the caller
  7. Next <Gather> opens for the caller's reply

Flow: Twilio POST /twilio/voice → verbal disclosure + first Gather
      → POST /twilio/gather (loop) → submit case or hangup
"""
import hashlib
import os
from urllib.parse import quote

from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
import httpx
import logging

from database import get_db
from models import CountryPermission
from services.country_service import (
    parse_phone, check_teleconsult_allowed, get_or_create_patient,
)
from services.case_service import create_case, complete_intake, move_to_pending
from services.triage_service import check_emergency_keywords
from services.icd11_service import map_intake_to_icd11
from services.language_service import (
    detect_language,
    get_language_config,
    translate_to_english,
    translate_from_english,
    translate_disclosure,
    build_emergency_message,
    get_emergency_number,
)
from config import (
    is_knowledge_graph_enabled,
    ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL_ID,
    CONVERSATION_MODEL, CONVERSATION_MAX_TOKENS,
    MIN_SYMPTOMS_FOR_COMPLETE, MAX_TURNS_BEFORE_COMPLETE,
    GRAPH_CONFIDENCE_THRESHOLD,
)
from routers.caller import (
    _build_verbal_disclosure,
    _generate_fallback_message,
    _extract_symptoms_from_text,
    _generate_claude_response,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/twilio", tags=["twilio-voice"])

# Per-call session state
_call_sessions: dict[str, dict] = {}

# In-memory cache for ElevenLabs audio (keyed by text hash, cleared per deploy)
_tts_cache: dict[str, bytes] = {}


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


def _truncate_for_tts(text: str, max_chars: int = 1500) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_period = truncated.rfind(". ")
    if last_period > max_chars // 2:
        return truncated[:last_period + 1]
    return truncated


def _tts_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _speak_twiml(text: str, voice: str, base_url: str) -> str:
    """Return TwiML that uses ElevenLabs <Play> if available, else <Say>."""
    if not ELEVENLABS_API_KEY:
        safe = _escape_xml(_truncate_for_tts(text))
        return f'  <Say voice="{voice}">{safe}</Say>\n'
    encoded = quote(text[:2000], safe="")
    return f'  <Play>/twilio/tts-audio?text={encoded}</Play>\n'


# ─── GET /twilio/tts-audio — ElevenLabs audio for Twilio <Play> ────────────

@router.get("/tts-audio")
async def tts_audio_for_twilio(text: str):
    """Twilio fetches this URL from <Play> to stream ElevenLabs audio."""
    if not text or not text.strip():
        return Response(status_code=204)

    text = text[:2000]
    cache_key = _tts_hash(text)

    if cache_key in _tts_cache:
        return Response(content=_tts_cache[cache_key], media_type="audio/mpeg")

    if not ELEVENLABS_API_KEY:
        return Response(status_code=503, content=b"ElevenLabs not configured")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream",
                headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
                json={
                    "text": text,
                    "model_id": ELEVENLABS_MODEL_ID,
                    "voice_settings": {"stability": 0.75, "similarity_boost": 0.75},
                },
            )
        if resp.status_code != 200:
            logger.warning("[TTS] ElevenLabs HTTP %d for Twilio Play", resp.status_code)
            return Response(status_code=502, content=b"TTS error")
        audio = resp.content
        _tts_cache[cache_key] = audio
        return Response(content=audio, media_type="audio/mpeg")
    except Exception as exc:
        logger.warning("[TTS] ElevenLabs error for Twilio: %s", exc)
        return Response(status_code=502, content=b"TTS unavailable")


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
        "ai_messages": [],  # for anti-repetition
        "country_code": country_code,
        "language": "en",   # will be updated after first speech
    }

    logger.info("[Twilio] Incoming call %s from %s — case %s", call_sid, country_code, case.id)

    # Default language config (English); will switch after first utterance
    lang_cfg = get_language_config("en")
    voice = lang_cfg["twilio_voice"]
    gather_lang = lang_cfg["twilio_lang"]

    base_url = str(request.base_url).rstrip("/")
    welcome_text = f"Welcome to the WHO Health Access Service. {shortened}"
    welcome_play = _speak_twiml(welcome_text, voice, base_url)
    ask_text = "Please describe your main symptoms. What brings you to call today?"
    ask_play = _speak_twiml(ask_text, voice, base_url)
    noinput_text = "I didn't catch that. Please call back when you're ready."
    noinput_play = _speak_twiml(noinput_text, voice, base_url)

    return _twiml(
        f'{welcome_play}'
        '  <Pause length="1"/>\n'
        f'  <Gather input="speech" action="/twilio/gather" method="POST"'
        f' speechTimeout="auto" speechModel="experimental_conversations"'
        f' language="{gather_lang}">\n'
        f'{ask_play}'
        "  </Gather>\n"
        f'{noinput_play}'
    )


# ─── POST /twilio/gather — speech recognition result ───────────────────────

@router.post("/gather")
async def gather_speech(request: Request, db: Session = Depends(get_db)):
    """
    Twilio <Gather> callback — receives transcribed speech and drives
    the symptom-collection conversation turn by turn.

    On first turn: detects language and switches conversation accordingly.
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
    country_code = session.get("country_code", "")

    # ── Language detection on first turn ──
    if turn == 1 and speech_result:
        detected_lang = detect_language(speech_result)
        if detected_lang != "en":
            session["language"] = detected_lang
            logger.info("[Twilio] Language detected: %s for call %s", detected_lang, call_sid)

    user_lang = session.get("language", "en")
    lang_cfg = get_language_config(user_lang)
    voice = lang_cfg["twilio_voice"]
    gather_lang = lang_cfg["twilio_lang"]

    # Translate user speech to English for processing
    english_speech = speech_result
    if user_lang != "en" and speech_result:
        english_speech = translate_to_english(speech_result, user_lang)

    session["message_history"].append({"role": "user", "content": english_speech})

    # ── 1. Extract symptoms (from English text) ──
    graph = None
    if is_knowledge_graph_enabled():
        try:
            from routers.knowledge_graph import get_graph
            graph = get_graph()
        except Exception:
            pass

    detected_symptoms: list[str] = []
    if graph:
        detected_symptoms = _extract_symptoms_from_text(english_speech, graph)

    if not detected_symptoms:
        _COMMON_SYMPTOMS = [
            "fever", "headache", "cough", "nausea", "vomiting", "diarrhea",
            "fatigue", "dizziness", "chest pain", "abdominal pain", "rash",
            "sore throat", "body aches", "chills", "shortness of breath",
            "back pain", "joint pain", "loss of appetite", "weight loss",
        ]
        text_lower = english_speech.lower()
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

    # ── 4. Emergency check (on English text) ──
    is_emergency = check_emergency_keywords(english_speech)
    emergency_flags: list[str] = []
    if is_emergency:
        from services.triage_service import EMERGENCY_KEYWORDS
        lower = english_speech.lower()
        emergency_flags = [kw.title() for kw in EMERGENCY_KEYWORDS if kw in lower]

    # ── 5. Completion criteria ───────────────────────────────────────────
    should_complete = (
        len(all_symptoms) >= MIN_SYMPTOMS_FOR_COMPLETE
        or graph_confidence > GRAPH_CONFIDENCE_THRESHOLD
        or turn >= MAX_TURNS_BEFORE_COMPLETE
        or is_emergency
    )

    # ── 6. Generate AI response (in English) ─────────────────────────────
    ai_response = None
    prior_history = session["message_history"][:-1]

    try:
        ai_response = _generate_claude_response(
            turn_number=turn,
            user_message=english_speech,
            all_symptoms=all_symptoms,
            suggested_questions=suggested_questions,
            activated_conditions=activated_conditions,
            body_systems=body_systems,
            is_emergency=is_emergency,
            emergency_flags=emergency_flags,
            should_complete=should_complete,
            message_history=prior_history,
            use_knowledge_graph=graph is not None,
            country_code=country_code,
            previous_ai_messages=session.get("ai_messages", []),
        )
        logger.info(
            "[Twilio] Claude+KG turn %s case=%s symptoms=%d graph=%s",
            turn,
            session.get("case_id"),
            len(all_symptoms),
            graph is not None,
        )
    except Exception as exc:
        logger.warning("[Twilio] Claude response failed, using fallback: %s", exc)
        ai_response = None

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

    # Track for anti-repetition
    session.setdefault("ai_messages", []).append(ai_response)

    # Translate response to user's language
    spoken_response = ai_response
    if user_lang != "en":
        spoken_response = translate_from_english(ai_response, user_lang)

    session["message_history"].append({"role": "assistant", "content": ai_response})
    session["turn"] = turn + 1

    base_url = str(request.base_url).rstrip("/")
    resp_play = _speak_twiml(spoken_response, voice, base_url)

    # ── 7. Emergency → advise caller + hangup ────────────────────────────
    if is_emergency:
        try:
            await _submit_twilio_case(db, session)
        except Exception as exc:
            logger.error("[Twilio] Emergency case submission failed: %s", exc)
        _call_sessions.pop(call_sid, None)

        emerg_msg = build_emergency_message(country_code, user_lang, emergency_flags)
        safe_emerg = _escape_xml(_truncate_for_tts(emerg_msg))
        return _twiml(
            f'  <Say voice="{voice}">{safe_emerg}</Say>\n'
            "  <Hangup/>"
        )

    # ── 8. Complete → submit case + summary + hangup ─────────────────────
    if should_complete:
        submit_ok = False
        try:
            await _submit_twilio_case(db, session)
            submit_ok = True
            logger.info("[Twilio] Case %s submitted successfully", session.get("case_id"))
        except Exception as exc:
            logger.error("[Twilio] Case submission failed: %s", exc, exc_info=True)
            # Retry once with a fresh DB session
            try:
                from database import SessionLocal
                retry_db = SessionLocal()
                await _submit_twilio_case(retry_db, session)
                retry_db.close()
                submit_ok = True
                logger.info("[Twilio] Case %s submitted on retry", session.get("case_id"))
            except Exception as exc2:
                logger.error("[Twilio] Retry also failed: %s", exc2)
        _call_sessions.pop(call_sid, None)

        symptom_list = ", ".join(all_symptoms) if all_symptoms else "your symptoms"
        if submit_ok:
            completion_msg = (
                f"Thank you for sharing this information. I've noted {symptom_list}. "
                "Your case has been submitted and a physician will review it shortly. "
                "If your condition worsens, please seek emergency care. Goodbye."
            )
        else:
            completion_msg = (
                f"Thank you. I've noted {symptom_list}. "
                "We experienced a technical issue but your information has been recorded. "
                "A physician will review it. If your condition worsens, seek emergency care. Goodbye."
            )
        if user_lang != "en":
            completion_msg = translate_from_english(completion_msg, user_lang)

        # Use <Say> for completion to avoid TTS timeout causing "application error"
        safe_completion = _escape_xml(_truncate_for_tts(completion_msg))
        return _twiml(
            f'{resp_play}'
            '  <Pause length="1"/>\n'
            f'  <Say voice="{voice}">{safe_completion}</Say>\n'
            "  <Hangup/>"
        )

    # ── 9. Continue → respond + gather next turn ─────────────────────────
    listen_prompt = "Go ahead, I'm listening."
    if user_lang != "en":
        listen_prompt = translate_from_english(listen_prompt, user_lang)
    listen_play = _speak_twiml(listen_prompt, voice, base_url)

    no_input_msg = "I didn't catch that. Please call back when you're ready."
    if user_lang != "en":
        no_input_msg = translate_from_english(no_input_msg, user_lang)
    noinput_play = _speak_twiml(no_input_msg, voice, base_url)

    return _twiml(
        f'{resp_play}'
        f'  <Gather input="speech" action="/twilio/gather" method="POST"'
        f' speechTimeout="auto" speechModel="experimental_conversations"'
        f' language="{gather_lang}">\n'
        f'{listen_play}'
        "  </Gather>\n"
        f'{noinput_play}'
    )


# ─── Internal: submit case from voice session ──────────────────────────────

async def _submit_twilio_case(db: Session, session: dict) -> None:
    """Build intake data from the voice session state and finalize the case."""
    import re

    case_id = session["case_id"]
    symptoms = session["collected_symptoms"]
    history = session["message_history"]

    transcript = " | ".join(f"{m['role']}: {m['content']}" for m in history)
    user_text = " ".join(m["content"] for m in history if m.get("role") == "user")

    all_text = " ".join(symptoms) + " " + transcript
    is_emergency = check_emergency_keywords(all_text)
    red_flags: list[str] = []
    if is_emergency:
        from services.triage_service import EMERGENCY_KEYWORDS
        lower = all_text.lower()
        red_flags = [kw.title() for kw in EMERGENCY_KEYWORDS if kw in lower]

    if is_emergency:
        triage_level = "RED"
    elif len(symptoms) >= 4 or red_flags:
        triage_level = "YELLOW"
    else:
        triage_level = "GREEN"

    # Extract duration from user messages
    duration = ""
    dur_match = re.search(r'(\d+\s*(?:days?|weeks?|months?|hours?|years?))', user_text, re.IGNORECASE)
    if dur_match:
        duration = dur_match.group(1)
    else:
        since_match = re.search(r'since\s+(yesterday|last\s+\w+)', user_text, re.IGNORECASE)
        if since_match:
            duration = f"since {since_match.group(1)}"

    # Extract severity from user messages
    severity = 5
    sev_match = re.search(r'(?:severity|pain|level|scale).*?(\d+)|(\d+)\s*(?:out of|/)\s*10', user_text, re.IGNORECASE)
    if sev_match:
        raw = next((g for g in sev_match.groups() if g), None)
        if raw and 1 <= int(raw) <= 10:
            severity = int(raw)

    # Build concise clinical summary from symptoms + context
    symptom_str = ", ".join(symptoms) if symptoms else "unspecified symptoms"
    summary = f"Patient reports: {symptom_str}."
    if duration:
        summary += f" Duration: {duration}."
    if severity != 5:
        summary += f" Severity: {severity}/10."

    intake_data = {
        "main_symptom": symptoms[0] if symptoms else "",
        "duration": duration,
        "severity": severity,
        "associated_symptoms": symptoms[1:] if len(symptoms) > 1 else [],
        "medical_history": [],
        "current_medications": [],
        "allergies": [],
        "triage_level": triage_level,
        "recommended_specialty": "general",
        "body_area": "",
        "red_flag_indicators": red_flags,
        "patient_summary": summary,
    }

    # ICD-11 mapping (non-blocking)
    try:
        icd11_results = await map_intake_to_icd11(intake_data)
        icd11_flat = [
            code
            for item in icd11_results
            for code in item.get("icd11_codes", [])
        ]
    except Exception as exc:
        logger.warning("[Twilio] ICD-11 mapping failed (non-blocking): %s", exc)
        icd11_flat = []

    # KG enrichment for voice calls too
    if is_knowledge_graph_enabled() and symptoms:
        try:
            from routers.knowledge_graph import _graph, _navigator_sessions
            if _graph:
                from knowledge_graph.navigator import ConversationNavigator
                nav = ConversationNavigator(_graph, case_id=case_id)
                kg_context = nav.process_symptoms(symptoms)
                if kg_context.get("suggested_specialties"):
                    intake_data["recommended_specialty"] = kg_context["suggested_specialties"][0]["specialty"]
                intake_data["kg_insights"] = {
                    "activated_conditions": kg_context.get("activated_conditions", [])[:5],
                    "suggested_specialties": kg_context.get("suggested_specialties", [])[:3],
                    "graph_confidence": kg_context.get("graph_confidence", 0),
                }
                _navigator_sessions[case_id] = nav
        except Exception as exc:
            logger.warning("[Twilio] KG enrichment failed (non-blocking): %s", exc)

    complete_intake(db, case_id, intake_data, icd11_flat)
    move_to_pending(db, case_id)

    logger.info(
        "[Twilio] Case %s submitted — %d symptoms, triage=%s, lang=%s",
        case_id, len(symptoms), triage_level, session.get("language", "en"),
    )
