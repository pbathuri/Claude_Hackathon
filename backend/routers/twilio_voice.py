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
import math
import os
import struct
from urllib.parse import quote

from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
import httpx
import logging

from database import get_db
from models import CountryPermission, Case
from services.country_service import (
    normalize_caller_jurisdiction,
    check_teleconsult_allowed,
    get_or_create_patient,
)
from safety.jurisdiction_policy import get_jurisdiction_policy
from security.twilio_signature import verify_twilio_webhook
from services.case_service import create_case, complete_intake, move_to_pending
from safety.red_flag_rules import detect_red_flags, RedFlagSeverity
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
    ANTHROPIC_API_KEY,
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
from services import session_store
from services.navigator_store import get_navigator, persist_navigator, clear_navigator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/twilio", tags=["twilio-voice"])


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


def _ready_tone_wav(
    duration_sec: float = 2.0,
    freq_hz: float = 660.0,
    sample_rate: int = 8000,
) -> bytes:
    """Short sine 'ready' tone for <Gather> (avoids spoken 'go ahead, I'm listening')."""
    n_samples = int(sample_rate * duration_sec)
    attack = max(1, int(0.04 * sample_rate))
    release_start = max(attack + 1, int((duration_sec - 0.12) * sample_rate))
    frames = bytearray()
    for i in range(n_samples):
        t = i / sample_rate
        amp = 0.32
        if i < attack:
            amp *= i / attack
        elif i >= release_start:
            amp *= max(0.0, (n_samples - i) / max(1, n_samples - release_start))
        sample = int(32767 * min(1.0, amp) * math.sin(2 * math.pi * freq_hz * t))
        frames.extend(struct.pack("<h", sample))
    data = bytes(frames)
    fmt_chunk = struct.pack(
        "<4sIHHIIHH",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        sample_rate * 2,
        2,
        16,
    )
    header = struct.pack("<4sI4s", b"RIFF", 36 + len(data), b"WAVE") + fmt_chunk
    return header + struct.pack("<4sI", b"data", len(data)) + data


def _gather_ready_play() -> str:
    """Relative URL; Twilio resolves against the webhook host."""
    return '  <Play>/twilio/ready-tone</Play>\n'


# ─── GET /twilio/ready-tone — short tone for <Gather> (no Twilio signature) ─

@router.get("/ready-tone")
def twilio_ready_tone():
    """Audio Twilio fetches for <Play> inside <Gather>; not webhook-signed."""
    return Response(
        content=_ready_tone_wav(),
        media_type="audio/wav",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# ─── GET /twilio/tts-audio — ElevenLabs audio for Twilio <Play> ────────────

@router.get("/tts-audio")
async def tts_audio_for_twilio(text: str):
    """Twilio fetches this URL from <Play> to stream ElevenLabs audio."""
    if not text or not text.strip():
        return Response(status_code=204)

    text = text[:2000]
    cache_key = _tts_hash(text)

    cached = session_store.tts_cache_get(cache_key)
    if cached:
        return Response(content=cached, media_type="audio/mpeg")

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
        session_store.tts_cache_set(cache_key, audio)
        return Response(content=audio, media_type="audio/mpeg")
    except Exception as exc:
        logger.warning("[TTS] ElevenLabs error for Twilio: %s", exc)
        return Response(status_code=502, content=b"TTS unavailable")


# ─── POST /twilio/voice — incoming call webhook ────────────────────────────

@router.post("/voice")
async def incoming_call(
    request: Request,
    db: Session = Depends(get_db),
    _twilio: None = Depends(verify_twilio_webhook),
):
    """
    Twilio webhook fired when someone dials the service number.
    Starts a case, plays the verbal disclosure, and opens the first
    speech Gather for symptom collection.
    """
    form = await request.form()
    caller_number = form.get("From", "")
    call_sid = form.get("CallSid", "unknown")

    j = normalize_caller_jurisdiction(db, caller_number)
    phone_info = j["phone_info"]
    country_code = j["jurisdiction_code"]
    detected_cc = j.get("detected_country_code")
    if detected_cc is None:
        logger.warning("[Twilio] Could not parse caller number — Tier 4 jurisdiction: %s", caller_number)

    perms = check_teleconsult_allowed(db, country_code)
    if not perms["allowed"]:
        logger.warning("[Twilio] Teleconsult not allowed for %s — using guidance-only flow", country_code)

    patient = get_or_create_patient(db, phone_info["e164"], country_code, "en")
    case = create_case(
        db,
        patient_id=patient.id,
        country_code=country_code,
        permission_tier=perms.get("permission_tier"),
        detected_country_code=detected_cc,
    )

    _jp = get_jurisdiction_policy(detected_cc or country_code)
    logger.info(
        "[Twilio] Jurisdiction=%s detected=%s policy_tier=%s",
        country_code,
        detected_cc,
        _jp.tier,
    )

    country_perm = (
        db.query(CountryPermission).filter_by(country_code=country_code).first()
    )
    verbal_disclosure = _build_verbal_disclosure(country_perm)

    sentences = verbal_disclosure.split(". ")
    shortened = ". ".join(sentences[:2]) + "." if len(sentences) > 2 else verbal_disclosure

    session_store.twilio_session_set(
        call_sid,
        {
            "case_id": case.id,
            "turn": 1,
            "collected_symptoms": [],
            "message_history": [],
            "ai_messages": [],  # for anti-repetition
            "country_code": country_code,
            "language": "en",  # will be updated after first speech
        },
    )

    logger.info("[Twilio] Incoming call %s from %s — case %s", call_sid, country_code, case.id)

    # Default language config (English); will switch after first utterance
    lang_cfg = get_language_config("en")
    voice = lang_cfg["twilio_voice"]
    gather_lang = lang_cfg["twilio_lang"]

    base_url = str(request.base_url).rstrip("/")
    welcome_text = f"Welcome to the WHO Health Access Service. {shortened} Please describe your symptoms."
    welcome_play = _speak_twiml(welcome_text, voice, base_url)
    ready_play = _gather_ready_play()
    noinput_text = "I didn't catch that. Please call back when you're ready."
    noinput_play = _speak_twiml(noinput_text, voice, base_url)

    return _twiml(
        f'{welcome_play}'
        f'  <Gather input="speech" action="/twilio/gather" method="POST"'
        f' speechTimeout="auto" speechModel="experimental_conversations"'
        f' language="{gather_lang}">\n'
        f'{ready_play}'
        "  </Gather>\n"
        f'{noinput_play}'
    )


# ─── POST /twilio/gather — speech recognition result ───────────────────────

@router.post("/gather")
async def gather_speech(
    request: Request,
    db: Session = Depends(get_db),
    _twilio: None = Depends(verify_twilio_webhook),
):
    """
    Twilio <Gather> callback — receives transcribed speech and drives
    the symptom-collection conversation turn by turn.

    On first turn: detects language and switches conversation accordingly.
    """
    form = await request.form()
    speech_result = form.get("SpeechResult", "")
    call_sid = form.get("CallSid", "unknown")

    session = session_store.twilio_session_get(call_sid)
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
    kg_context_for_safety: dict | None = None

    if graph and all_symptoms:
        try:
            case_id = session["case_id"]
            nav = get_navigator(case_id, graph)
            context = nav.process_symptoms(all_symptoms)
            persist_navigator(case_id, nav)
            kg_context_for_safety = context

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

    # ── 4. Layered safety engine (same path as REST /caller) ──
    rf = detect_red_flags(
        speech_result or "",
        country_code,
        language=user_lang,
        english_text=english_speech,
        kg_context=kg_context_for_safety,
    )
    # URGENT widens triage on submit; only IMMEDIATE stops the voice flow as "emergency".
    is_emergency = rf.is_emergency
    emergency_flags = [
        (f.get("matched_text") or f.get("flag") or "").strip()
        for f in rf.flags
        if (f.get("matched_text") or f.get("flag"))
    ]

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
        session_store.twilio_session_delete(call_sid)
        clear_navigator(session.get("case_id", ""))

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
        session_store.twilio_session_delete(call_sid)
        clear_navigator(session.get("case_id", ""))

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

    # ── 9. Continue → short ready tone + gather (no spoken "go ahead" prompt)
    listen_play = _gather_ready_play()

    no_input_msg = "I didn't catch that. Please call back when you're ready."
    if user_lang != "en":
        no_input_msg = translate_from_english(no_input_msg, user_lang)
    noinput_play = _speak_twiml(no_input_msg, voice, base_url)

    session_store.twilio_session_set(call_sid, session)

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
    case_row = db.query(Case).filter_by(id=case_id).first()
    cc = case_row.country_code if case_row else ""
    rf_submit = detect_red_flags(all_text, cc, english_text=all_text)
    red_flags = [
        (f.get("matched_text") or f.get("flag") or "").strip()
        for f in rf_submit.flags
        if (f.get("matched_text") or f.get("flag"))
    ]

    if rf_submit.is_emergency:
        triage_level = "RED"
    elif rf_submit.severity == RedFlagSeverity.URGENT or len(symptoms) >= 4 or red_flags:
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
            from routers.knowledge_graph import _graph
            if _graph:
                from services.navigator_store import get_navigator

                nav = get_navigator(case_id, _graph)
                kg_context = nav.process_symptoms(symptoms)
                persist_navigator(case_id, nav)
                if kg_context.get("suggested_specialties"):
                    intake_data["recommended_specialty"] = kg_context["suggested_specialties"][0]["specialty"]
                intake_data["kg_insights"] = {
                    "activated_conditions": kg_context.get("activated_conditions", [])[:5],
                    "suggested_specialties": kg_context.get("suggested_specialties", [])[:3],
                    "graph_confidence": kg_context.get("graph_confidence", 0),
                }
        except Exception as exc:
            logger.warning("[Twilio] KG enrichment failed (non-blocking): %s", exc)

    complete_intake(db, case_id, intake_data, icd11_flat)

    # Full transcript for doctor dashboard (Phase 5)
    log_payload = {
        "channel": "twilio_voice",
        "language": session.get("language", "en"),
        "turns": history,
        "symptoms_final": symptoms,
        "triage_level": triage_level,
    }
    clinical_note = intake_data.get("patient_summary", "")
    if ANTHROPIC_API_KEY and symptoms:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            note_resp = client.messages.create(
                model=CONVERSATION_MODEL,
                max_tokens=200,
                system=(
                    "Write one short clinical handoff paragraph for a physician. "
                    "No diagnosis. Symptoms, duration, severity if known."
                ),
                messages=[{"role": "user", "content": transcript[:4000]}],
            )
            clinical_note = note_resp.content[0].text.strip()
        except Exception as exc:
            logger.warning("[Twilio] Clinical note generation skipped: %s", exc)

    log_payload["clinical_note"] = clinical_note
    case_upd = db.query(Case).filter_by(id=case_id).first()
    if case_upd:
        case_upd.conversation_log = log_payload
        db.commit()

    move_to_pending(db, case_id)

    logger.info(
        "[Twilio] Case %s submitted — %d symptoms, triage=%s, lang=%s",
        case_id, len(symptoms), triage_level, session.get("language", "en"),
    )
