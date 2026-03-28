"""
WHO Global Health Observatory (GHO) OData API integration.
Fetches country health indicators: physician density, hospital beds, UHC index.
Free, no authentication required.
"""
import httpx

from config import WHO_GHO_BASE_URL, WHO_INDICATORS


async def get_indicator(indicator_code: str, country_alpha3: str) -> dict:
    """
    Fetch a single WHO indicator value for a country.
    Returns {value, year} for the most recent data point.
    """
    url = f"{WHO_GHO_BASE_URL}/{indicator_code}"
    params = {"$filter": f"SpatialDim eq '{country_alpha3}'"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()

    data = resp.json().get("value", [])
    if not data:
        return {"value": None, "year": None}

    # Get the most recent data point
    latest = sorted(data, key=lambda x: x.get("TimeDim", 0), reverse=True)[0]
    return {
        "value": latest.get("NumericValue"),
        "year": latest.get("TimeDim"),
    }


async def build_health_profile(country_alpha3: str) -> dict:
    """
    Build a comprehensive health profile for a country using WHO indicators.
    """
    profile = {}
    for name, code in WHO_INDICATORS.items():
        profile[name] = await get_indicator(code, country_alpha3)
    return profile


def get_indicator_sync(indicator_code: str, country_alpha3: str) -> dict:
    """Synchronous version for non-async contexts."""
    import requests
    url = f"{WHO_GHO_BASE_URL}/{indicator_code}"
    params = {"$filter": f"SpatialDim eq '{country_alpha3}'"}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json().get("value", [])
    if not data:
        return {"value": None, "year": None}
    latest = sorted(data, key=lambda x: x.get("TimeDim", 0), reverse=True)[0]
    return {
        "value": latest.get("NumericValue"),
        "year": latest.get("TimeDim"),
    }


def build_health_profile_sync(country_alpha3: str) -> dict:
    """Synchronous version."""
    profile = {}
    for name, code in WHO_INDICATORS.items():
        profile[name] = get_indicator_sync(code, country_alpha3)
    return profile
