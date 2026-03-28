"""
Country detection from phone numbers and permission matrix enforcement.
Uses Google's libphonenumber for parsing, DB-backed permission matrix.
"""
import hashlib
import phonenumbers
from phonenumbers import geocoder
from sqlalchemy.orm import Session

from models import CountryPermission, Patient


# ISO alpha-2 → alpha-3 mapping for WHO GHO API
ALPHA2_TO_ALPHA3 = {
    "NG": "NGA", "IN": "IND", "PH": "PHL",
    "US": "USA", "GB": "GBR", "KE": "KEN",
    "ZA": "ZAF", "BD": "BGD", "PK": "PAK",
}


def parse_phone(phone_str: str) -> dict:
    """Parse an international phone number into country info."""
    try:
        parsed = phonenumbers.parse(phone_str, None)
    except phonenumbers.NumberParseException:
        return {"error": "Could not parse phone number"}

    if not phonenumbers.is_valid_number(parsed):
        return {"error": "Invalid phone number"}

    cc = phonenumbers.region_code_for_number(parsed)
    return {
        "e164": phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.E164
        ),
        "country_code": cc,
        "country_alpha3": ALPHA2_TO_ALPHA3.get(cc, cc),
        "country_name": geocoder.description_for_number(parsed, "en"),
    }


def hash_phone(e164: str) -> str:
    """One-way SHA-256 hash for phone lookup (no storing raw numbers)."""
    return hashlib.sha256(e164.encode()).hexdigest()


def get_country_permissions(db: Session, country_code: str) -> CountryPermission | None:
    """Fetch the permission row for a country."""
    return db.query(CountryPermission).filter_by(country_code=country_code).first()


def check_teleconsult_allowed(db: Session, country_code: str) -> dict:
    """Return whether teleconsult is allowed and relevant disclaimers."""
    perm = get_country_permissions(db, country_code)
    if perm is None:
        return {
            "allowed": False,
            "reason": f"Country {country_code} not in permission matrix",
            "disclaimer": None,
        }
    return {
        "allowed": perm.allows_teleconsult,
        "permission_tier": perm.permission_tier,
        "requires_local_doctor": perm.requires_local_doctor,
        "allows_ai_triage": perm.allows_ai_triage,
        "allows_prescription": perm.allows_prescription,
        "disclaimer": perm.disclaimer_text,
        "data_law": perm.data_law,
        "max_retention_days": perm.max_retention_days,
    }


def get_or_create_patient(
    db: Session, phone_e164: str, country_code: str, language: str = "en"
) -> Patient:
    """Find existing patient by phone hash or create new one."""
    ph = hash_phone(phone_e164)
    patient = db.query(Patient).filter_by(phone_hash=ph).first()
    if patient:
        return patient
    patient = Patient(
        phone_hash=ph,
        country_code=country_code,
        language=language,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


# ── Seed data for the three target countries ──
SEED_COUNTRIES = [
    {
        "country_code": "NG",
        "country_name": "Nigeria",
        "permission_tier": "limited",
        "country_tier": 2,
        "allows_teleconsult": True,
        "allows_ai_triage": True,
        "allows_prescription": False,
        "requires_local_doctor": True,
        "cross_border_allowed": False,
        "data_residency_required": True,
        "max_retention_days": 90,
        "regulatory_basis": "MDCN Code of Ethics Rule 22; no dedicated telemedicine law",
        "data_law": "Nigeria Data Protection Act (NDPA) 2023",
        "disclaimer_text": (
            "This service provides health guidance only — not a medical diagnosis. "
            "A locally-licensed Nigerian doctor will review your case. "
            "If this is an emergency, call 112 or go to the nearest hospital."
        ),
        "notes": "Must register with CAC. Lagos requires HEFAMAA registration.",
    },
    {
        "country_code": "IN",
        "country_name": "India",
        "permission_tier": "regulated",
        "country_tier": 1,
        "allows_teleconsult": True,
        "allows_ai_triage": True,
        "allows_prescription": False,
        "requires_local_doctor": True,
        "cross_border_allowed": False,
        "data_residency_required": True,
        "max_retention_days": 90,
        "regulatory_basis": "Telemedicine Practice Guidelines 2020 (Appendix 5, IMC Regs)",
        "data_law": "IT Act 2000 + Digital Personal Data Protection Act 2023",
        "disclaimer_text": (
            "This service provides health guidance only — not a medical diagnosis. "
            "A locally-licensed Indian doctor will review your case. "
            "If this is an emergency, call 112 or go to the nearest hospital."
        ),
        "notes": "First consult can be remote. Patient-initiated = implied consent.",
    },
    {
        "country_code": "PH",
        "country_name": "Philippines",
        "permission_tier": "emerging",
        "country_tier": 3,
        "allows_teleconsult": True,
        "allows_ai_triage": True,
        "allows_prescription": False,
        "requires_local_doctor": True,
        "cross_border_allowed": False,
        "data_residency_required": False,
        "max_retention_days": 90,
        "regulatory_basis": "DOH-DILG-PHIC JAO 2021-0001; no dedicated law",
        "data_law": "Data Privacy Act 2012 (RA 10173)",
        "disclaimer_text": (
            "This service provides health guidance only — not a medical diagnosis. "
            "A PRC-licensed Filipino doctor will review your case. "
            "If this is an emergency, call 911 or go to the nearest hospital."
        ),
        "notes": "PRC-licensed physicians only. Informed consent required.",
    },
    {
        "country_code": "KE",
        "country_name": "Kenya",
        "permission_tier": "emerging",
        "country_tier": 3,
        "allows_teleconsult": True,
        "allows_ai_triage": True,
        "allows_prescription": False,
        "requires_local_doctor": True,
        "cross_border_allowed": False,
        "data_residency_required": False,
        "max_retention_days": 90,
        "regulatory_basis": "Kenya Health Act 2017; no dedicated telemedicine law",
        "data_law": "Data Protection Act 2019",
        "disclaimer_text": (
            "This service provides health guidance only — not a medical diagnosis. "
            "A locally-licensed Kenyan doctor will review your case. "
            "If this is an emergency, call 999 or go to the nearest hospital."
        ),
        "notes": "KMPDC-licensed physicians only. eHealth Strategy 2016-2030 supports telemedicine.",
    },
]


def seed_country_permissions(db: Session):
    """Insert seed country permission rows if they don't exist."""
    for data in SEED_COUNTRIES:
        existing = db.query(CountryPermission).filter_by(
            country_code=data["country_code"]
        ).first()
        if not existing:
            db.add(CountryPermission(**data))
    db.commit()
