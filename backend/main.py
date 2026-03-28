"""
WHO-Aligned AI Telehealth Backend
Main FastAPI application with startup/shutdown lifecycle.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from services.country_service import seed_country_permissions
from services.scheduler_service import start_scheduler, stop_scheduler
from database import SessionLocal

from routers import intake, cases, doctors, health_data, caller
from routers.knowledge_graph import router as kg_router, init_knowledge_graph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


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

    logger.info("Initializing medical knowledge graph...")
    init_knowledge_graph(persist_path="./data/knowledge_graph.json")

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
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(intake.router)
app.include_router(cases.router)
app.include_router(doctors.router)
app.include_router(health_data.router)
app.include_router(caller.router)
app.include_router(kg_router)


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
        },
    }


@app.get("/health-check")
def health_check():
    return {"status": "healthy"}
