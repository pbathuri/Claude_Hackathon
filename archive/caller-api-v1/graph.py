import asyncio
import logging
import operator
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Annotated, Any, Optional

from faster_whisper import WhisperModel
from pydantic import BaseModel
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from typing import TypedDict

from src.prompts import human_interaction_prompt, continue_gate_prompt
from src.config import Configuration


# ── Logger ────────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)


# ── Whisper model cache ───────────────────────────────────────────────────────
@lru_cache(maxsize=None)
def _get_whisper_model(model: str, device: str, compute_type: str) -> WhisperModel:
    logger.info(
        "[Whisper] Loading model '%s' on %s (%s) — this only runs once",
        model, device, compute_type,
    )
    return WhisperModel(model, device=device, compute_type=compute_type)


# ── State Schema ──────────────────────────────────────────────────────────────
class MainState(TypedDict):
    symptoms:               Annotated[list[str],  operator.add]
    message_history:        Annotated[list[dict], operator.add]
    audio_input:            Optional[bytes]
    transcript:             Optional[str]
    audio_output:           Optional[bytes]
    conversation_complete:  bool


# ── Response Schema ───────────────────────────────────────────────────────────
class MessageDict(BaseModel):
    role: str
    content: str

class MainResponseSchema(BaseModel):
    message_history: MessageDict   # explicit nested model so small LLMs reliably fill it
    symptoms: list[str]


# ── Graph-level Config ────────────────────────────────────────────────────────
@dataclass
class Config:
    smart_llm: Any = field(default=None)

    @classmethod
    def from_runnable_config(cls, config: RunnableConfig) -> "Config":
        configurable = (config or {}).get("configurable", {})
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in configurable.items() if k in known})


# ── State snapshot helper ─────────────────────────────────────────────────────
def _log_state(label: str, state: MainState) -> None:
    logger.debug(
        "[State] %s | symptoms=%s | turns=%d | transcript=%r | "
        "audio_in=%s | audio_out=%s | complete=%s",
        label,
        state.get("symptoms", []),
        len(state.get("message_history", [])),
        state.get("transcript"),
        f"{len(state['audio_input'])} bytes" if state.get("audio_input") else "None",
        f"{len(state['audio_output'])} bytes" if state.get("audio_output") else "None",
        state.get("conversation_complete", False),
    )


# ── Router Node ───────────────────────────────────────────────────────────────
async def router(state: MainState, config: RunnableConfig) -> dict:
    _log_state("router:enter", state)
    return {}


def _route_from_router(state: MainState) -> str:
    if state.get("audio_input"):
        logger.info("[Router] audio_input present → speech_to_text")
        return "speech_to_text"
    logger.info(
        "[Router] no audio_input, transcript=%r → human_interaction",
        state.get("transcript"),
    )
    return "human_interaction"


# ── Speech-to-Text Node ───────────────────────────────────────────────────────
async def speech_to_text(state: MainState, config: RunnableConfig) -> dict:
    _log_state("speech_to_text:enter", state)

    audio_bytes: Optional[bytes] = state.get("audio_input")
    if not audio_bytes:
        logger.debug("[STT] No audio_input — skipping")
        return {"transcript": None}

    cfg = Configuration.from_runnable_config(config)
    logger.info("[STT] Transcribing %d bytes | model='%s'", len(audio_bytes), cfg.whisper_model)

    def _transcribe() -> str:
        model = _get_whisper_model(
            cfg.whisper_model,
            cfg.whisper_device,
            cfg.whisper_compute_type,
        )
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            segments, info = model.transcribe(
                tmp.name,
                beam_size=5,
                language=cfg.whisper_language,
            )
            text = " ".join(seg.text.strip() for seg in segments)
            logger.debug(
                "[STT] language='%s' (%.0f%%) | transcript=%r",
                info.language,
                info.language_probability * 100,
                text,
            )
            return text

    loop = asyncio.get_event_loop()
    transcript = await loop.run_in_executor(None, _transcribe)
    logger.info("[STT] Done: %r", transcript)
    return {"transcript": transcript, "audio_input": None}


# ── Emergency Check Node ─────────────────────────────────────────────────────
async def emergency_check(state: MainState, config: RunnableConfig) -> dict:
    """Check transcript for life-threatening keywords before LLM processes it."""
    transcript = state.get("transcript")
    if not transcript:
        return {}

    EMERGENCY_KEYWORDS = [
        "chest pain", "chest tightness", "can't breathe", "cannot breathe",
        "difficulty breathing", "shortness of breath", "stroke",
        "face drooping", "arm weakness", "slurred speech",
        "severe bleeding", "unconscious", "unresponsive",
        "suicidal", "self-harm", "throat swelling",
    ]
    lower = transcript.lower()
    if any(kw in lower for kw in EMERGENCY_KEYWORDS):
        logger.warning("[Emergency] Detected in transcript: %r", transcript)
        return {
            "conversation_complete": True,
            "message_history": [{
                "role": "assistant",
                "content": "This sounds like it could be a medical emergency. "
                           "Please call emergency services immediately. "
                           "If you are in Kenya, call 999. "
                           "If you are in Nigeria, call 112. "
                           "If you are in India, call 112.",
            }],
        }
    return {}


# ── Human Interaction Node ────────────────────────────────────────────────────
async def human_interaction(state: MainState, config: RunnableConfig) -> dict:
    _log_state("human_interaction:enter", state)

    cfg = Config.from_runnable_config(config)
    smart_llm = cfg.smart_llm.with_structured_output(MainResponseSchema)
    chain = human_interaction_prompt | smart_llm

    symptoms_str = ", ".join(state.get("symptoms", [])) or "none reported yet"
    transcript    = state.get("transcript") or "none"
    turn          = len(state.get("message_history", [])) + 1

    logger.info(
        "[LLM] human_interaction | turn=%d | symptoms=%r | transcript=%r",
        turn, symptoms_str, transcript,
    )

    response: MainResponseSchema = await chain.ainvoke(
        {"symptoms": symptoms_str, "transcript": transcript}
    )

    logger.info(
        "[LLM] response | role=%s | symptoms=%s | message=%r",
        response.message_history.role,
        response.symptoms,
        response.message_history.content[:120],
    )

    return {
        "message_history": [
            {
                "role":    response.message_history.role,
                "content": response.message_history.content,
            }
        ],
        "symptoms": response.symptoms,
    }


# ── Text-to-Speech Node ───────────────────────────────────────────────────────
async def text_to_speech(state: MainState, config: RunnableConfig) -> dict:
    _log_state("text_to_speech:enter", state)

    history = state.get("message_history", [])
    assistant_msgs = [m for m in history if m.get("role") == "assistant"]
    if not assistant_msgs:
        logger.debug("[TTS] No assistant message — skipping")
        return {"audio_output": None}

    text = assistant_msgs[-1]["content"]
    cfg  = Configuration.from_runnable_config(config)

    logger.info(
        "[TTS] Synthesising %d chars | host=%s:%d | voice=%s",
        len(text), cfg.piper_host, cfg.piper_port, cfg.piper_voice,
    )

    try:
        from wyoming.client import AsyncTcpClient
        from wyoming.tts import Synthesize, SynthesizeVoice
        from wyoming.audio import AudioChunk, AudioStop

        chunks: list[bytes] = []
        async with AsyncTcpClient(cfg.piper_host, cfg.piper_port) as client:
            await client.write_event(
                Synthesize(
                    text=text,
                    voice=SynthesizeVoice(name=cfg.piper_voice),
                ).event()
            )
            while True:
                event = await client.read_event()
                if event is None:
                    break
                if AudioChunk.is_type(event.type):
                    chunks.append(AudioChunk.from_event(event).audio)
                elif AudioStop.is_type(event.type):
                    break

        total = sum(len(c) for c in chunks)
        logger.info("[TTS] Done — %d bytes across %d chunks", total, len(chunks))
        return {"audio_output": b"".join(chunks)}

    except Exception as exc:
        logger.error("[TTS] Failed, continuing without audio: %s", exc, exc_info=True)
        return {"audio_output": None}


# ── Continue Gate Node ────────────────────────────────────────────────────────
async def continue_gate(state: MainState, config: RunnableConfig) -> dict:
    _log_state("continue_gate:enter", state)

    cfg   = Config.from_runnable_config(config)
    chain = continue_gate_prompt | cfg.smart_llm

    symptoms_str = ", ".join(state.get("symptoms", [])) or "none"
    turns        = len(state.get("message_history", []))

    logger.info("[LLM] continue_gate | turns=%d | symptoms=%r", turns, symptoms_str)

    decision = await chain.ainvoke({"symptoms": symptoms_str, "turns": turns})
    verdict: str = decision.content.strip().lower()
    complete = verdict == "end"

    logger.info("[LLM] continue_gate verdict=%r | conversation_complete=%s", verdict, complete)
    return {"conversation_complete": complete}


# ── Build & Compile Graph ─────────────────────────────────────────────────────
def build_graph() -> StateGraph:
    g = StateGraph(MainState)

    g.add_node("router",            router)
    g.add_node("speech_to_text",    speech_to_text)
    g.add_node("emergency_check",   emergency_check)
    g.add_node("human_interaction", human_interaction)
    g.add_node("text_to_speech",    text_to_speech)
    g.add_node("continue_gate",     continue_gate)

    g.set_entry_point("router")

    g.add_conditional_edges(
        "router",
        _route_from_router,
        {
            "speech_to_text":    "speech_to_text",
            "human_interaction": "human_interaction",
        },
    )

    g.add_edge("speech_to_text",    "emergency_check")
    g.add_edge("emergency_check",   "human_interaction")
    g.add_edge("human_interaction", "text_to_speech")
    g.add_edge("text_to_speech",    "continue_gate")
    g.add_edge("continue_gate",     END)

    return g.compile()


graph = build_graph()