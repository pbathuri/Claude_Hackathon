"""
Database models aligned with WHO SMART Guidelines and the product architecture.
Covers: patients, cases, symptom records, doctor profiles, country permissions,
triage scores, doctor responses, follow-up schedules, image uploads, audit log.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey,
    JSON, Enum as SAEnum, Index,
)
from sqlalchemy.orm import relationship

from database import Base


def gen_uuid():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


# ──────────────────────────────────────────────
# PATIENTS
# ──────────────────────────────────────────────
class Patient(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True, default=gen_uuid)
    phone_hash = Column(String, unique=True, nullable=False, index=True)
    country_code = Column(String(3), nullable=False)  # ISO 3166-1 alpha-2
    language = Column(String(5), default="en")
    consent_given = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    cases = relationship("Case", back_populates="patient")


# ──────────────────────────────────────────────
# DOCTOR PROFILES
# ──────────────────────────────────────────────
class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    id = Column(String, primary_key=True, default=gen_uuid)
    full_name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    specialization = Column(String(100), nullable=False)
    country_code = Column(String(3), nullable=False)
    languages = Column(JSON, default=["en"])
    license_number = Column(String(100))
    license_verified = Column(Boolean, default=False)
    medical_school = Column(String(200))
    availability = Column(String(20), default="offline")  # online/offline/busy
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    assigned_cases = relationship("Case", back_populates="assigned_doctor")
    responses = relationship("DoctorResponse", back_populates="doctor")


# ──────────────────────────────────────────────
# CASES (the core entity)
# ──────────────────────────────────────────────
class Case(Base):
    __tablename__ = "cases"

    id = Column(String, primary_key=True, default=gen_uuid)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    assigned_doctor_id = Column(String, ForeignKey("doctor_profiles.id"), nullable=True)

    # Status: open -> intake_complete -> pending -> assigned -> in_progress -> resolved -> closed
    #         Also: escalated, expired
    status = Column(String(30), nullable=False, default="open")
    triage_level = Column(String(10), nullable=True)  # RED, YELLOW, GREEN, BLACK
    chief_complaint = Column(Text, nullable=True)
    country_code = Column(String(3), nullable=False)

    # Intake data from Claude (structured JSON)
    intake_data = Column(JSON, nullable=True)
    icd11_codes = Column(JSON, default=[])
    recommended_specialty = Column(String(100), nullable=True)

    # Frontend-facing fields
    patient_alias = Column(String(20), nullable=True)   # e.g. "PT-2048"
    body_area = Column(String(100), nullable=True)       # e.g. "Abdomen", "Head"
    red_flag_indicators = Column(JSON, default=[])       # e.g. ["Persistent pain", "Fever"]

    # Priority scoring
    priority_score = Column(Float, default=0.0)
    is_followup = Column(Boolean, default=False)
    parent_case_id = Column(String, nullable=True)

    # Timestamps for lifecycle tracking
    opened_at = Column(DateTime, default=utcnow)
    intake_completed_at = Column(DateTime, nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    escalated_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Permission context
    permission_tier = Column(String(20), nullable=True)
    disclaimer_shown = Column(Boolean, default=False)

    patient = relationship("Patient", back_populates="cases")
    assigned_doctor = relationship("DoctorProfile", back_populates="assigned_cases")
    symptom_records = relationship("SymptomRecord", back_populates="case")
    images = relationship("ImageUpload", back_populates="case")
    responses = relationship("DoctorResponse", back_populates="case")
    followups = relationship("FollowUpSchedule", back_populates="case")

    __table_args__ = (
        Index("ix_cases_status", "status"),
        Index("ix_cases_triage", "triage_level"),
        Index("ix_cases_country", "country_code"),
    )


# ──────────────────────────────────────────────
# SYMPTOM RECORDS
# ──────────────────────────────────────────────
class SymptomRecord(Base):
    __tablename__ = "symptom_records"

    id = Column(String, primary_key=True, default=gen_uuid)
    case_id = Column(String, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    symptoms_json = Column(JSON, default=[])
    icd11_codes = Column(JSON, default=[])
    severity = Column(Integer, nullable=True)
    transcript_text = Column(Text, nullable=True)
    recorded_at = Column(DateTime, default=utcnow)

    case = relationship("Case", back_populates="symptom_records")


# ──────────────────────────────────────────────
# IMAGE UPLOADS
# ──────────────────────────────────────────────
class ImageUpload(Base):
    __tablename__ = "image_uploads"

    id = Column(String, primary_key=True, default=gen_uuid)
    case_id = Column(String, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    upload_token = Column(String(20), unique=True, nullable=False)
    file_path = Column(String(500), nullable=True)
    content_type = Column(String(50), nullable=True)
    uploaded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    case = relationship("Case", back_populates="images")


# ──────────────────────────────────────────────
# DOCTOR RESPONSES
# ──────────────────────────────────────────────
class DoctorResponse(Base):
    __tablename__ = "doctor_responses"

    id = Column(String, primary_key=True, default=gen_uuid)
    case_id = Column(String, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    doctor_id = Column(String, ForeignKey("doctor_profiles.id"), nullable=False)
    guidance_text = Column(Text, nullable=False)
    is_emergency_referral = Column(Boolean, default=False)
    compliance_acknowledged = Column(Boolean, default=False)  # "I am not diagnosing"
    created_at = Column(DateTime, default=utcnow)

    case = relationship("Case", back_populates="responses")
    doctor = relationship("DoctorProfile", back_populates="responses")


# ──────────────────────────────────────────────
# FOLLOW-UP SCHEDULES
# ──────────────────────────────────────────────
class FollowUpSchedule(Base):
    __tablename__ = "follow_up_schedules"

    id = Column(String, primary_key=True, default=gen_uuid)
    case_id = Column(String, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    channel = Column(String(10), default="sms")  # sms, call, whatsapp
    status = Column(String(20), default="pending")  # pending, sent, replied, escalated
    patient_reply = Column(String(10), nullable=True)  # 1=better, 2=same, 3=worse
    sent_at = Column(DateTime, nullable=True)
    replied_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    case = relationship("Case", back_populates="followups")


# ──────────────────────────────────────────────
# COUNTRY PERMISSION MATRIX
# ──────────────────────────────────────────────
class CountryPermission(Base):
    __tablename__ = "country_permissions"

    country_code = Column(String(3), primary_key=True)
    country_name = Column(String(100), nullable=False)
    permission_tier = Column(String(20), nullable=False, default="advice_only")
    country_tier = Column(Integer, nullable=False, default=3)  # 1=regulated, 2=limited, 3=emerging
    allows_teleconsult = Column(Boolean, default=True)
    allows_ai_triage = Column(Boolean, default=True)
    allows_prescription = Column(Boolean, default=False)
    requires_local_doctor = Column(Boolean, default=True)
    cross_border_allowed = Column(Boolean, default=False)
    data_residency_required = Column(Boolean, default=False)
    max_retention_days = Column(Integer, default=90)
    regulatory_basis = Column(Text, nullable=True)
    data_law = Column(Text, nullable=True)
    disclaimer_text = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)


# ──────────────────────────────────────────────
# AUDIT LOG (append-only)
# ──────────────────────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=utcnow, nullable=False)
    actor_id = Column(String, nullable=True)  # doctor_id, system, patient_hash
    actor_type = Column(String(20), nullable=True)  # doctor, system, patient
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String, nullable=True)
    details = Column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_audit_timestamp", "timestamp"),
        Index("ix_audit_resource", "resource_type", "resource_id"),
    )
