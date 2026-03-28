"""
Health data router: WHO GHO indicators, ICD-11 search, country permissions.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import CountryPermission
from services.who_service import build_health_profile, get_indicator
from services.icd11_service import search_icd11
from services.country_service import ALPHA2_TO_ALPHA3

router = APIRouter(prefix="/health", tags=["health-data"])


@router.get("/icd11/search")
async def icd11_search(
    term: str = Query(..., min_length=2, description="Search term for ICD-11 codes"),
    max_results: int = Query(default=5, le=20),
):
    """Search ICD-11 codes via NLM Clinical Tables API."""
    results = await search_icd11(term, max_results)
    return {"term": term, "results": results}


@router.get("/who/profile/{country_code}")
async def who_country_profile(country_code: str):
    """
    Get WHO health indicators for a country.
    Accepts ISO alpha-2 (NG) or alpha-3 (NGA) codes.
    """
    alpha3 = ALPHA2_TO_ALPHA3.get(country_code.upper(), country_code.upper())
    profile = await build_health_profile(alpha3)
    return {"country": alpha3, "indicators": profile}


@router.get("/who/indicator/{indicator_code}")
async def who_indicator(
    indicator_code: str,
    country: str = Query(..., description="ISO alpha-3 country code (e.g., NGA)"),
):
    """Fetch a specific WHO indicator for a country."""
    result = await get_indicator(indicator_code, country)
    return {"indicator": indicator_code, "country": country, "data": result}


@router.get("/permissions")
def list_permissions(db: Session = Depends(get_db)):
    """List all country permission entries."""
    perms = db.query(CountryPermission).all()
    return [
        {
            "country_code": p.country_code,
            "country_name": p.country_name,
            "permission_tier": p.permission_tier,
            "allows_teleconsult": p.allows_teleconsult,
            "allows_ai_triage": p.allows_ai_triage,
            "allows_prescription": p.allows_prescription,
            "requires_local_doctor": p.requires_local_doctor,
            "cross_border_allowed": p.cross_border_allowed,
            "max_retention_days": p.max_retention_days,
            "regulatory_basis": p.regulatory_basis,
            "data_law": p.data_law,
            "disclaimer_text": p.disclaimer_text,
        }
        for p in perms
    ]


@router.get("/permissions/{country_code}")
def get_permission(country_code: str, db: Session = Depends(get_db)):
    """Get permission details for a specific country."""
    perm = db.query(CountryPermission).filter_by(country_code=country_code).first()
    if not perm:
        return {"error": f"Country {country_code} not found in permission matrix"}
    return {
        "country_code": perm.country_code,
        "country_name": perm.country_name,
        "permission_tier": perm.permission_tier,
        "allows_teleconsult": perm.allows_teleconsult,
        "allows_ai_triage": perm.allows_ai_triage,
        "allows_prescription": perm.allows_prescription,
        "requires_local_doctor": perm.requires_local_doctor,
        "cross_border_allowed": perm.cross_border_allowed,
        "data_residency_required": perm.data_residency_required,
        "max_retention_days": perm.max_retention_days,
        "regulatory_basis": perm.regulatory_basis,
        "data_law": perm.data_law,
        "disclaimer_text": perm.disclaimer_text,
        "notes": perm.notes,
    }
