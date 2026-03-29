"""
WHO-Aligned AI Telehealth Backend
Main FastAPI application with startup/shutdown lifecycle.
"""
import logging
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from database import init_db
from services.country_service import seed_country_permissions
from services.scheduler_service import start_scheduler, stop_scheduler
from database import SessionLocal

from routers import intake, cases, doctors, health_data, caller
from config import is_knowledge_graph_enabled
from routers.knowledge_graph import router as kg_router, init_knowledge_graph
from routers.twilio_voice import router as twilio_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Feature flags
DEMO_MODE = os.environ.get("DEMO_MODE", "1") == "1"
if DEMO_MODE:
    logger.warning("DEMO_MODE is enabled — authentication is bypassed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup
    logger.info("Initializing database...")
    init_db()

    logger.info("Seeding country permissions...")
    db = SessionLocal()
    try:
        seed_country_permissions(db)
    finally:
        db.close()

    logger.info("Starting background scheduler...")
    start_scheduler()

    if is_knowledge_graph_enabled():
        logger.info("Initializing medical knowledge graph...")
        init_knowledge_graph(persist_path="./data/knowledge_graph.json")
    else:
        logger.info(
            "ENABLE_KNOWLEDGE_GRAPH is disabled — skipping graph init; "
            "/kg endpoints will return 503 until enabled."
        )

    logger.info("WHO Telehealth Backend ready")
    yield

    # Shutdown
    logger.info("Stopping background scheduler...")
    stop_scheduler()
    logger.info("Shutdown complete")


app = FastAPI(
    title="WHO-Aligned AI Telehealth Backend",
    description=(
        "AI-powered telehealth platform for underserved populations. "
        "Phone-based medical intake, START triage, ICD-11 mapping, "
        "priority-based doctor routing, and country permission enforcement."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for doctor portal frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://doctor-portal-flax.vercel.app",
        "https://claude-hackathon-u86l.onrender.com",
        "http://localhost:3001",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from observability.middleware import RequestIDMiddleware
app.add_middleware(RequestIDMiddleware)

# Register routers
app.include_router(intake.router)
app.include_router(cases.router)
app.include_router(doctors.router)
app.include_router(health_data.router)
app.include_router(caller.router)
app.include_router(kg_router)
app.include_router(twilio_router)


os.makedirs("static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/call")
def call_redirect():
    return RedirectResponse(url="/static/caller.html")


@app.get("/")
def root():
    return {
        "service": "WHO-Aligned AI Telehealth Backend",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "docs": "/docs",
            "intake": "/intake",
            "cases": "/cases",
            "doctors": "/doctors",
            "health": "/health",
            "knowledge_graph": "/kg",
            "caller_simulator": "/call",
        },
    }


@app.get("/health-check")
def health_check():
    from config import (
        ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL_ID,
        REDIS_URL, TWILIO_ACCOUNT_SID, ANTHROPIC_API_KEY,
        CONVERSATION_MODEL,
    )
    return {
        "status": "healthy",
        "apis": {
            "claude": bool(ANTHROPIC_API_KEY),
            "claude_model": CONVERSATION_MODEL,
            "claude_key_len": len(ANTHROPIC_API_KEY),
            "elevenlabs": bool(ELEVENLABS_API_KEY),
            "twilio": bool(TWILIO_ACCOUNT_SID),
            "redis": bool(REDIS_URL),
            "knowledge_graph": is_knowledge_graph_enabled(),
            "hf_token": bool(os.environ.get("HF_TOKEN", "")),
        },
    }


@app.get("/debug/claude-test")
def debug_claude():
    """Quick test of Claude API to verify connectivity."""
    from config import ANTHROPIC_API_KEY, CONVERSATION_MODEL
    if not ANTHROPIC_API_KEY:
        return {"error": "ANTHROPIC_API_KEY not set", "key_len": 0}
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=CONVERSATION_MODEL,
            max_tokens=50,
            messages=[{"role": "user", "content": "Say hello in one sentence."}],
        )
        return {
            "ok": True,
            "model": CONVERSATION_MODEL,
            "response": resp.content[0].text,
            "key_len": len(ANTHROPIC_API_KEY),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "model": CONVERSATION_MODEL, "key_len": len(ANTHROPIC_API_KEY)}
