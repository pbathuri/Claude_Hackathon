import asyncio
import base64
import json
import logging
import subprocess
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from src.config import Configuration
from src.graph import graph


# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan: build LLM once at startup ──────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = Configuration().from_runnable_config()
    app.state.cfg       = cfg
    app.state.smart_llm = cfg.get_smart_llm()
    logger.info("Startup complete | smart_llm=%s | whisper=%s | piper=%s:%d",
                cfg.smart_llm, cfg.whisper_model, cfg.piper_host, cfg.piper_port)
    yield
    logger.info("Shutdown")


app = FastAPI(title="Whisper-Ollama Voice API", lifespan=lifespan)


def _extract_clinical_facts(history: list[dict]) -> tuple[int, str, str]:
    """
    Extract severity, duration, and body_area from conversation history.
    Returns (severity: int, duration: str, body_area: str) with best-effort extraction.
    Falls back to conservative defaults rather than hardcoded mid-range.
    """
    import re

    all_patient_text = " ".join(
        m.get("content", "") for m in history if m.get("role") in ("user", "human")
    ).lower()

    # Severity: look for "N out of 10", "pain N", severity-implying keywords
    severity = 5  # conservative default
    sev_match = re.search(r"(\d+)\s*(?:out of|/)\s*10", all_patient_text)
    if sev_match:
        severity = min(10, max(1, int(sev_match.group(1))))
    elif any(kw in all_patient_text for kw in ["severe", "worst", "unbearable", "excruciating", "10"]):
        severity = 8
    elif any(kw in all_patient_text for kw in ["moderate", "quite bad", "pretty bad"]):
        severity = 6
    elif any(kw in all_patient_text for kw in ["mild", "slight", "little", "minor"]):
        severity = 3

    # Duration: "for N days/weeks/hours"
    duration = ""
    dur_patterns = [
        r"(?:for|since|past|last)\s+(\d+\s+(?:day|week|month|hour|year)s?)",
        r"(\d+\s+(?:day|week|month|hour|year)s?)\s+(?:ago|now)",
        r"(?:started|began)\s+(\d+\s+(?:day|week|month|hour|year)s?\s+ago)",
        r"(?:for|since|past|last)\s+(a\s+(?:day|week|month|hour|year|few days|couple days))",
    ]
    for pattern in dur_patterns:
        m = re.search(pattern, all_patient_text)
        if m:
            duration = m.group(1).strip()
            break

    # Body area: keyword mapping
    body_area = ""
    area_map = {
        "head": ["headache", "head", "migraine", "skull", "temple"],
        "chest": ["chest", "heart", "rib", "lung"],
        "abdomen": ["stomach", "abdomen", "belly", "abdominal", "tummy", "gut"],
        "throat": ["throat", "tonsil", "neck"],
        "back": ["back", "spine", "lower back"],
        "whole body": ["whole body", "everywhere", "all over", "body aches", "chills", "fever"],
        "limbs": ["arm", "leg", "knee", "ankle", "wrist", "elbow", "shoulder", "hip"],
        "skin": ["skin", "rash", "lesion", "wound", "itch"],
    }
    for area, keywords in area_map.items():
        if any(kw in all_patient_text for kw in keywords):
            body_area = area
            break

    logger.info(
        "[FactExtract] severity=%d | duration='%s' | body_area='%s'",
        severity, duration, body_area,
    )
    return severity, duration, body_area


# ── Audio normalisation ───────────────────────────────────────────────────────
async def _normalise_audio(raw: bytes) -> bytes:
    """
    Convert any phone audio (µ-law, G.711, MP3, etc.) to 16 kHz mono WAV.
    Whisper expects 16 kHz; phone carriers typically deliver 8 kHz µ-law.
    ffmpeg is pre-installed in the Docker image.
    """
    loop = asyncio.get_event_loop()

    def _run() -> bytes:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i",  "pipe:0",   # read from stdin
                "-ar", "16000",    # resample to 16 kHz
                "-ac", "1",        # mono
                "-f",  "wav",
                "pipe:1",          # write to stdout
            ],
            input=raw,
            capture_output=True,
            check=True,
        )
        return result.stdout

    try:
        return await loop.run_in_executor(None, _run)
    except subprocess.CalledProcessError as exc:
        logger.error("[Audio] ffmpeg conversion failed: %s", exc.stderr.decode())
        raise HTTPException(status_code=422, detail="Audio conversion failed — unsupported format.")


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health(request: Request):
    cfg: Configuration = request.app.state.cfg
    return {
        "status":        "ok",
        "smart_llm":     cfg.smart_llm,
        "whisper_model": cfg.whisper_model,
        "piper_host":    cfg.piper_host,
        "piper_port":    cfg.piper_port,
        "piper_voice":   cfg.piper_voice,
    }


# ── Chat ──────────────────────────────────────────────────────────────────────
@app.post("/chat")
async def chat(
    request:         Request,
    audio:           Optional[UploadFile] = File(default=None),
    text:            Optional[str]        = Form(default=None),
    symptoms:        str                  = Form(default="[]"),
    message_history: str                  = Form(default="[]"),
    phone_number:    Optional[str]        = Form(default=None),
    case_id:         Optional[str]        = Form(default=None),
):
    """
    One turn of the diagnostic conversation.

    Supply either:
      - audio  : an audio file (WAV, MP3, µ-law — any format ffmpeg understands)
      - text   : a plain-text string (skips Whisper entirely)

    Always supply on subsequent calls:
      - symptoms        : JSON array from the previous response
      - message_history : JSON array from the previous response

    Response fields:
      - transcript           : what Whisper heard (or the text you sent)
      - message              : assistant reply text
      - symptoms             : updated symptom list (pass back on next call)
      - message_history      : updated history   (pass back on next call)
      - audio                : base64-encoded raw PCM (16-bit, 22050 Hz, mono)
      - conversation_complete: true when enough symptoms have been collected
      - turns                : total turns so far
    """
    if not audio and not text:
        raise HTTPException(
            status_code=422,
            detail="Provide either 'audio' (file) or 'text' (string).",
        )

    # ── Parse previous state ──────────────────────────────────────────────────
    try:
        prev_symptoms: list[str]  = json.loads(symptoms)
        prev_history:  list[dict] = json.loads(message_history)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid JSON in symptoms/message_history: {exc}")

    # ── Prepare audio bytes ───────────────────────────────────────────────────
    audio_bytes: Optional[bytes] = None
    if audio:
        raw = await audio.read()
        logger.info("[API] Received audio file '%s' (%d bytes)", audio.filename, len(raw))
        audio_bytes = await _normalise_audio(raw)
        logger.info("[API] Normalised audio: %d bytes", len(audio_bytes))

    # ── Build initial state ───────────────────────────────────────────────────
    initial_state = {
        "symptoms":              prev_symptoms,
        "message_history":       prev_history,
        "audio_input":           audio_bytes,
        "transcript":            text or None,   # pre-fill if text was supplied
        "audio_output":          None,
        "conversation_complete": False,
    }

    # ── Backend integration: start session on first turn ─────────────
    cfg: Configuration = request.app.state.cfg
    backend = cfg.backend_url

    if phone_number and not case_id:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(f"{backend}/caller/session/start", json={
                    "phone_number": phone_number,
                })
            if r.status_code == 200:
                session_data = r.json()
                case_id = session_data["case_id"]

                disclosure = session_data.get("verbal_disclosure", "")
                if disclosure:
                    initial_state["message_history"] = prev_history + [
                        {"role": "assistant", "content": disclosure}
                    ]

                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(f"{backend}/caller/session/consent", json={
                        "case_id": case_id,
                        "consent_given": True,
                    })

                logger.info("[Backend] Session started | case_id=%s | country=%s | tier=%d",
                            case_id, session_data.get("country_name"), session_data.get("country_tier"))
            elif r.status_code == 403:
                error_data = r.json().get("detail", {})
                return JSONResponse(content={
                    "transcript": None,
                    "message": f"We're sorry, telehealth is not yet available in {error_data.get('country', 'your region')}. Please contact local health services.",
                    "symptoms": [],
                    "message_history": prev_history,
                    "audio": None,
                    "conversation_complete": True,
                    "turns": len(prev_history),
                    "case_id": None,
                })
        except httpx.ConnectError:
            logger.warning("[Backend] Backend unreachable — continuing without session")

    # ── Run graph ─────────────────────────────────────────────────────────────
    cfg: Configuration = request.app.state.cfg
    runnable_config = {
        "configurable": {
            "smart_llm": request.app.state.smart_llm,
        }
    }

    logger.info(
        "[API] Invoking graph | turns_so_far=%d | audio=%s | text=%r",
        len(prev_history),
        f"{len(audio_bytes)} bytes" if audio_bytes else "None",
        text,
    )

    try:
        result = await graph.ainvoke(initial_state, config=runnable_config)
    except Exception as exc:
        logger.error("[API] Graph error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {exc}")

    # ── Extract response fields ───────────────────────────────────────────────
    history: list[dict] = result.get("message_history", [])
    assistant_msgs       = [m for m in history if m.get("role") == "assistant"]
    reply_text           = assistant_msgs[-1]["content"] if assistant_msgs else ""

    audio_out: Optional[bytes] = result.get("audio_output")
    audio_b64 = base64.b64encode(audio_out).decode() if audio_out else None

    response_body = {
        "transcript":            result.get("transcript"),
        "message":               reply_text,
        "symptoms":              result.get("symptoms", []),
        "message_history":       history,
        "audio":                 audio_b64,
        "conversation_complete": result.get("conversation_complete", False),
        "turns":                 len(history),
    }

    # ── Backend integration: submit completed conversation ───────────
    if response_body["conversation_complete"] and case_id:
        try:
            # Extract severity, duration, body_area from conversation history
            _severity, _duration, _body_area = _extract_clinical_facts(history)

            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(f"{backend}/caller/session/submit", json={
                    "case_id":              case_id,
                    "symptoms":             response_body["symptoms"],
                    "message_history":      history,
                    "transcript_summary":   reply_text,
                    "severity":             _severity,
                    "duration":             _duration,
                    "body_area":            _body_area,
                })
            if r.status_code == 200:
                backend_result = r.json()
                response_body["backend_case"] = backend_result
                logger.info(
                    "[Backend] Case submitted | case_id=%s | triage=%s | priority=%.0f",
                    backend_result["case_id"],
                    backend_result["triage_level"],
                    backend_result["priority_score"],
                )
        except Exception as exc:
            logger.error("[Backend] Submit failed (non-blocking): %s", exc)

    response_body["case_id"] = case_id

    logger.info(
        "[API] Response | turns=%d | symptoms=%s | complete=%s | audio=%s",
        response_body["turns"],
        response_body["symptoms"],
        response_body["conversation_complete"],
        f"{len(audio_out)} bytes" if audio_out else "None",
    )

    return JSONResponse(content=response_body)
