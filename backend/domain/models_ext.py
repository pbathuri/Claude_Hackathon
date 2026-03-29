"""Extended domain models for production hardening.
These supplement the existing models.py without breaking existing code."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Float, Boolean, DateTime, ForeignKey,
)

from database import Base
from db_types import JSONCompat


class ConversationTurnRecord(Base):
    __tablename__ = "conversation_turns"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String, ForeignKey("cases.id"), nullable=False, index=True)
    turn_index = Column(Integer, nullable=False)
    actor_type = Column(String(20), nullable=False)
    channel = Column(String(20), default="web")
    language = Column(String(10), default="en")
    text = Column(Text, nullable=False)
    original_text = Column(Text, nullable=True)
    original_language = Column(String(10), nullable=True)
    language_confidence = Column(Float, nullable=True)
    translated_text = Column(Text, nullable=True)
    translation_confidence = Column(Float, nullable=True)
    transcript_confidence = Column(Float, nullable=True)
    metadata_json = Column(JSONCompat, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class ConsentEventRecord(Base):
    __tablename__ = "consent_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String, ForeignKey("cases.id"), nullable=True, index=True)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=True, index=True)
    consent_type = Column(String(50), nullable=False)
    version = Column(String(20), default="1.0")
    language = Column(String(10), default="en")
    channel = Column(String(20), default="web")
    accepted = Column(Boolean, default=False)
    consent_text_hash = Column(String(64), nullable=True)
    captured_at = Column(DateTime, default=datetime.utcnow)
    metadata_json = Column(JSONCompat, default=dict)


class ClinicalExtractionRecord(Base):
    __tablename__ = "clinical_extractions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String, ForeignKey("cases.id"), nullable=False, unique=True, index=True)
    extraction_json = Column(JSONCompat, nullable=False, default=dict)
    overall_confidence = Column(Float, default=0.0)
    extraction_complete = Column(Boolean, default=False)
    uncertainty_flags = Column(JSONCompat, default=list)
    scoring_json = Column(JSONCompat, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


