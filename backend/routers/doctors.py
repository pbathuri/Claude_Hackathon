"""
Doctors router: doctor registration, profile management, availability.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import DoctorProfile, Case
from auth.middleware import get_current_actor

router = APIRouter(prefix="/doctors", tags=["doctors"])


class DoctorCreateRequest(BaseModel):
    full_name: str
    email: str
    specialization: str
    country_code: str
    languages: list[str] = ["en"]
    license_number: str | None = None
    medical_school: str | None = None


class DoctorUpdateRequest(BaseModel):
    availability: str | None = None  # online/offline/busy
    specialization: str | None = None
    languages: list[str] | None = None


@router.post("/")
def register_doctor(
    req: DoctorCreateRequest,
    db: Session = Depends(get_db),
    _actor: dict = Depends(get_current_actor),
):
    """Register a new doctor profile."""
    existing = db.query(DoctorProfile).filter_by(email=req.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    doctor = DoctorProfile(
        full_name=req.full_name,
        email=req.email,
        specialization=req.specialization,
        country_code=req.country_code,
        languages=req.languages,
        license_number=req.license_number,
        medical_school=req.medical_school,
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)

    return {
        "id": doctor.id,
        "full_name": doctor.full_name,
        "email": doctor.email,
        "specialization": doctor.specialization,
        "country_code": doctor.country_code,
        "verified": doctor.verified,
    }


@router.get("/")
def list_doctors(
    country_code: str | None = None,
    specialization: str | None = None,
    available_only: bool = False,
    db: Session = Depends(get_db),
):
    """List doctors with optional filters."""
    q = db.query(DoctorProfile)
    if country_code:
        q = q.filter(DoctorProfile.country_code == country_code)
    if specialization:
        q = q.filter(DoctorProfile.specialization == specialization)
    if available_only:
        q = q.filter(DoctorProfile.availability == "online")
    doctors = q.all()

    return [
        {
            "id": d.id,
            "full_name": d.full_name,
            "specialization": d.specialization,
            "country_code": d.country_code,
            "languages": d.languages,
            "availability": d.availability,
            "verified": d.verified,
            "license_verified": d.license_verified,
        }
        for d in doctors
    ]


@router.get("/{doctor_id}")
def get_doctor(doctor_id: str, db: Session = Depends(get_db)):
    """Get a doctor's full profile."""
    doctor = db.query(DoctorProfile).filter_by(id=doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    # Count assigned cases
    active_cases = (
        db.query(Case)
        .filter(
            Case.assigned_doctor_id == doctor_id,
            Case.status.in_(["assigned", "in_progress"]),
        )
        .count()
    )

    return {
        "id": doctor.id,
        "full_name": doctor.full_name,
        "email": doctor.email,
        "specialization": doctor.specialization,
        "country_code": doctor.country_code,
        "languages": doctor.languages,
        "license_number": doctor.license_number,
        "license_verified": doctor.license_verified,
        "medical_school": doctor.medical_school,
        "availability": doctor.availability,
        "verified": doctor.verified,
        "active_cases": active_cases,
        "created_at": doctor.created_at.isoformat() if doctor.created_at else None,
    }


@router.patch("/{doctor_id}")
def update_doctor(
    doctor_id: str,
    req: DoctorUpdateRequest,
    db: Session = Depends(get_db),
    _actor: dict = Depends(get_current_actor),
):
    """Update doctor availability or profile fields."""
    doctor = db.query(DoctorProfile).filter_by(id=doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    if req.availability is not None:
        doctor.availability = req.availability
    if req.specialization is not None:
        doctor.specialization = req.specialization
    if req.languages is not None:
        doctor.languages = req.languages

    db.commit()
    db.refresh(doctor)

    return {"status": "updated", "doctor_id": doctor.id, "availability": doctor.availability}


@router.post("/{doctor_id}/verify")
def verify_doctor(
    doctor_id: str,
    db: Session = Depends(get_db),
    _actor: dict = Depends(get_current_actor),
):
    """Mark a doctor as verified (admin action)."""
    doctor = db.query(DoctorProfile).filter_by(id=doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    doctor.verified = True
    doctor.license_verified = True
    db.commit()

    return {"status": "verified", "doctor_id": doctor.id}
