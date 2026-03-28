"""
ICD-11 code mapping via NLM Clinical Tables API (zero authentication required).
Maps free-text symptom descriptions to standardized ICD-11 codes.
"""
import httpx

from config import NLM_ICD11_URL


async def search_icd11(term: str, max_results: int = 5) -> list[dict]:
    """
    Search ICD-11 codes via NLM Clinical Tables API.
    Returns list of {code, title} dicts.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            NLM_ICD11_URL,
            params={
                "terms": term,
                "sf": "code,title",
                "df": "code,title",
                "maxList": max_results,
            },
        )
        resp.raise_for_status()

    data = resp.json()
    # NLM API returns [total, codes, null, [[code, title], ...]]
    if len(data) >= 4 and data[3]:
        return [{"code": r[0], "title": r[1]} for r in data[3]]
    return []


def search_icd11_sync(term: str, max_results: int = 5) -> list[dict]:
    """Synchronous version for non-async contexts."""
    import requests
    resp = requests.get(
        NLM_ICD11_URL,
        params={
            "terms": term,
            "sf": "code,title",
            "df": "code,title",
            "maxList": max_results,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if len(data) >= 4 and data[3]:
        return [{"code": r[0], "title": r[1]} for r in data[3]]
    return []


async def map_symptoms_to_icd11(symptoms: list[str]) -> list[dict]:
    """
    Map a list of symptom strings to ICD-11 codes.
    Returns list of {symptom, icd11_codes} dicts.
    """
    results = []
    for symptom in symptoms:
        codes = await search_icd11(symptom, max_results=3)
        results.append({
            "symptom": symptom,
            "icd11_codes": codes,
        })
    return results


async def map_intake_to_icd11(intake_data: dict) -> list[dict]:
    """
    Given a structured intake result from Claude, extract symptoms
    and map them to ICD-11 codes.
    """
    symptoms = []

    # Main symptom
    main = intake_data.get("main_symptom")
    if main:
        symptoms.append(main)

    # Associated symptoms
    associated = intake_data.get("associated_symptoms", [])
    symptoms.extend(associated)

    return await map_symptoms_to_icd11(symptoms)
