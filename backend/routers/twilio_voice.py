"""
Twilio Voice Webhook router.
Handles inbound phone calls via Twilio with strict scripted intake:
name → age → gender → phone confirm → consent → chief symptom →
body → pain → duration → allergies → medications → delivery, then submit.

Emergency red-flag detection after consent can short-circuit to submit + advisory hangup.
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
from models import CountryPermission, Case, Patient
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
    INTAKE_MODEL,
)
from services.twilio_intake_flow import (
    GATHER_TIMEOUT_SEC,
    GATHER_SPEECH_TIMEOUT,
    READY_TONE_DURATION_SEC,
    advance_twilio_intake_step,
    extract_body_area_from_speech,
    extract_duration_from_speech,
    claude_symptom_summary_and_fill,
    symptoms_from_chief_text,
)
from routers.caller import (
    _build_verbal_disclosure,
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
    duration_sec: float = READY_TONE_DURATION_SEC,
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
        async with httpx.AsyncClient(timeout=8.5) as client:
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
            "intake_phase": "name",
            "caller_e164": phone_info.get("e164", ""),
        },
    )

    logger.info("[Twilio] Incoming call %s from %s — case %s", call_sid, country_code, case.id)

    # Default language config (English); will switch after first utterance
    lang_cfg = get_language_config("en")
    voice = lang_cfg["twilio_voice"]
    gather_lang = lang_cfg["twilio_lang"]

    base_url = str(request.base_url).rstrip("/")
    welcome_text = (
        f"Welcome to the WHO Health Access Service. {shortened} "
        "Please say your full name."
    )
    welcome_play = _speak_twiml(welcome_text, voice, base_url)
    ready_play = _gather_ready_play()
    noinput_text = "I didn't catch that. Please call back when you're ready."
    noinput_play = _speak_twiml(noinput_text, voice, base_url)

    return _twiml(
        f'{welcome_play}'
        f'  <Gather input="speech" action="/twilio/gather" method="POST"'
        f' timeout="{GATHER_TIMEOUT_SEC}" speechTimeout="{GATHER_SPEECH_TIMEOUT}"'
        f' speechModel="experimental_conversations"'
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
    Twilio <Gather> callback — receives transcribed speech and advances
    the scripted intake state machine (one question per turn).

    On first speech: detects language and pins it for the rest of the call.
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
    country_code = session.get("country_code", "")

    # ── Language detection (once per call; demographics may hold turn=1 several times) ──
    if speech_result and not session.get("language_pinned"):
        detected_lang = detect_language(speech_result)
        if detected_lang != "en":
            session["language"] = detected_lang
            logger.info("[Twilio] Language detected: %s for call %s", detected_lang, call_sid)
        session["language_pinned"] = True

    user_lang = session.get("language", "en")
    lang_cfg = get_language_config(user_lang)
    voice = lang_cfg["twilio_voice"]
    gather_lang = lang_cfg["twilio_lang"]

    # Translate user speech to English for processing
    english_speech = speech_result
    if user_lang != "en" and speech_result:
        english_speech = translate_to_english(speech_result, user_lang)

    session["message_history"].append({"role": "user", "content": english_speech})

    base_url = str(request.base_url).rstrip("/")

    # ── Scripted intake (single state machine; one question per Gather) ──
    _phase = session.get("intake_phase", "name")
    if _phase != "done":
        prev_phase = _phase
        result = await advance_twilio_intake_step(
            session,
            english_speech,
            anthropic_api_key=ANTHROPIC_API_KEY,
            intake_model=INTAKE_MODEL,
        )
        session["intake_phase"] = result.next_phase
        session["message_history"].append({"role": "assistant", "content": result.reply_en})
        session["turn"] = turn + 1

        if prev_phase == "consent" and result.next_phase == "sq_chief":
            case_row = db.query(Case).filter_by(id=session["case_id"]).first()
            if case_row:
                patient = db.query(Patient).filter_by(id=case_row.patient_id).first()
                if patient:
                    patient.consent_given = True
                    db.commit()

        if result.action == "consent_refused":
            case_row = db.query(Case).filter_by(id=session["case_id"]).first()
            if case_row:
                patient = db.query(Patient).filter_by(id=case_row.patient_id).first()
                if patient:
                    patient.consent_given = False
                    db.commit()
            session_store.twilio_session_delete(call_sid)
            clear_navigator(session.get("case_id", ""))
            goodbye_en = result.reply_en
            spoken = (
                translate_from_english(goodbye_en, user_lang) if user_lang != "en" else goodbye_en
            )
            safe = _escape_xml(_truncate_for_tts(spoken))
            return _twiml(
                f'  <Say voice="{voice}">{safe}</Say>\n'
                "  <Hangup/>"
            )

        if session.get("intake_consent_granted") and speech_result:
            rf_e = detect_red_flags(
                speech_result,
                country_code,
                language=user_lang,
                english_text=english_speech,
            )
            if rf_e.is_emergency:
                emergency_flags = [
                    (f.get("matched_text") or f.get("flag") or "").strip()
                    for f in rf_e.flags
                    if (f.get("matched_text") or f.get("flag"))
                ]
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

        if result.action == "submit_case":
            submit_ok = False
            try:
                await _submit_twilio_case(db, session)
                submit_ok = True
                logger.info("[Twilio] Case %s submitted successfully", session.get("case_id"))
            except Exception as exc:
                logger.error("[Twilio] Case submission failed: %s", exc, exc_info=True)
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
            done_en = result.reply_en
            if not submit_ok:
                done_en = (
                    "Thank you. We had a technical issue saving your case, but please call back "
                    "if you need help. Goodbye."
                )
            spoken_done = (
                translate_from_english(done_en, user_lang) if user_lang != "en" else done_en
            )
            safe_done = _escape_xml(_truncate_for_tts(spoken_done))
            return _twiml(
                f'  <Say voice="{voice}">{safe_done}</Say>\n'
                "  <Hangup/>"
            )

        session_store.twilio_session_set(call_sid, session)
        spoken_response = (
            translate_from_english(result.reply_en, user_lang) if user_lang != "en" else result.reply_en
        )
        resp_play = _speak_twiml(spoken_response, voice, base_url)
        listen_play = _gather_ready_play()
        no_input_msg = "I didn't catch that. Please call back when you're ready."
        if user_lang != "en":
            no_input_msg = translate_from_english(no_input_msg, user_lang)
        noinput_play = _speak_twiml(no_input_msg, voice, base_url)
        return _twiml(
            f'{resp_play}'
            f'  <Gather input="speech" action="/twilio/gather" method="POST"'
            f' timeout="{GATHER_TIMEOUT_SEC}" speechTimeout="{GATHER_SPEECH_TIMEOUT}"'
            f' speechModel="experimental_conversations"'
            f' language="{gather_lang}">\n'
            f'{listen_play}'
            "  </Gather>\n"
            f'{noinput_play}'
        )

    # Session should not reach here normally (done clears session on submit).
    logger.warning("[Twilio] Gather with intake_phase=done for call %s", call_sid)
    return _twiml(
        '  <Say voice="Polly.Joanna">Your session has ended. Goodbye.</Say>\n'
        "  <Hangup/>"
    )


# ─── Internal: submit case from voice session ──────────────────────────────

async def _submit_twilio_case(db: Session, session: dict) -> None:
    """Build intake data from the voice session state and finalize the case."""
    import re

    case_id = session["case_id"]
    symptoms = list(session.get("collected_symptoms") or [])
    chief_text = (session.get("sq_chief_text") or "").strip()
    allergies_text = (session.get("allergies_text") or "").strip() or "0"
    medications_list = list(session.get("medications_list") or [])
    patient_age = session.get("patient_age")
    history = session["message_history"]

    transcript = " | ".join(f"{m['role']}: {m['content']}" for m in history)
    user_text = " ".join(m["content"] for m in history if m.get("role") == "user")

    if chief_text and not symptoms:
        symptoms = symptoms_from_chief_text(chief_text)

    all_text = " ".join(symptoms) + " " + transcript + " " + chief_text
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

    _pain = session.get("twilio_pain_score")
    severity = int(_pain) if _pain is not None else 5
    if _pain is None:
        sev_match = re.search(
            r'(?:severity|pain|level|scale).*?(\d+)|(\d+)\s*(?:out of|/)\s*10',
            user_text,
            re.IGNORECASE,
        )
        if sev_match:
            raw = next((g for g in sev_match.groups() if g), None)
            if raw and 0 <= int(raw) <= 10:
                severity = int(raw)

    duration = session.get("twilio_stored_duration") or ""
    if not duration:
        dur_match = re.search(
            r'(\d+\s*(?:days?|weeks?|months?|hours?|years?))', user_text, re.IGNORECASE
        )
        if dur_match:
            duration = dur_match.group(1)
        else:
            since_match = re.search(r'since\s+(yesterday|last\s+\w+)', user_text, re.IGNORECASE)
            if since_match:
                duration = f"since {since_match.group(1)}"

    body_area = session.get("twilio_stored_body_area") or extract_body_area_from_speech(user_text)

    filled = await claude_symptom_summary_and_fill(
        transcript=transcript,
        symptoms=symptoms,
        patient_gender=session.get("patient_gender") or "unspecified",
        patient_name=session.get("patient_name") or "",
        patient_dob="",
        patient_phone=session.get("patient_phone") or session.get("caller_e164", ""),
        patient_age=patient_age if isinstance(patient_age, int) else None,
        delivery_preference=session.get("delivery_preference") or "",
        duration_guess=duration,
        body_guess=body_area,
        severity=severity,
        allergies=allergies_text,
        medications=medications_list,
        chief_text=chief_text,
        api_key=ANTHROPIC_API_KEY,
        model=INTAKE_MODEL,
    )
    duration = filled.get("duration") or duration
    body_area = filled.get("body_area") or body_area
    symptom_summary_text = filled.get("symptom_summary") or ""

    main_symptom = chief_text[:500] if chief_text else (symptoms[0] if symptoms else "")
    intake_data = {
        "main_symptom": main_symptom,
        "duration": duration,
        "severity": severity,
        "associated_symptoms": symptoms[1:] if len(symptoms) > 1 else [],
        "medical_history": [],
        "current_medications": medications_list,
        "allergies": allergies_text,
        "triage_level": triage_level,
        "recommended_specialty": "general",
        "body_area": body_area,
        "red_flag_indicators": red_flags,
        "patient_summary": symptom_summary_text,
        "symptom_summary": symptom_summary_text,
        "patient_gender": session.get("patient_gender") or "unspecified",
        "patient_name": session.get("patient_name") or "",
        "patient_dob": "",
        "patient_phone": session.get("patient_phone") or session.get("caller_e164", ""),
        "delivery_preference": session.get("delivery_preference") or "",
    }
    if isinstance(patient_age, int):
        intake_data["patient_age"] = patient_age

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
    clinical_note = symptom_summary_text or intake_data.get("patient_summary", "")
    if ANTHROPIC_API_KEY and symptoms and len(clinical_note) < 80:
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
