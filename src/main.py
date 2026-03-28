import asyncio
import base64
import json
import logging
import subprocess
from contextlib import asynccontextmanager
from typing import Optional

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

    logger.info(
        "[API] Response | turns=%d | symptoms=%s | complete=%s | audio=%s",
        response_body["turns"],
        response_body["symptoms"],
        response_body["conversation_complete"],
        f"{len(audio_out)} bytes" if audio_out else "None",
    )

    return JSONResponse(content=response_body)
