"""
ICD-11 code mapping via NLM Clinical Tables API (zero authentication required).
Maps free-text symptom descriptions to standardized ICD-11 codes.
"""
import logging

import httpx

from config import NLM_ICD11_URL

logger = logging.getLogger(__name__)


async def search_icd11(term: str, max_results: int = 5) -> list[dict]:
    """
    Search ICD-11 codes via NLM Clinical Tables API.
    Returns list of {code, title} dicts. Returns empty list on failure.
    """
    if not term or not term.strip():
        return []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                NLM_ICD11_URL,
                params={
                    "terms": term.strip(),
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
    except httpx.TimeoutException:
        logger.warning("[ICD-11] NLM API timeout for term: %s", term)
    except httpx.HTTPStatusError as exc:
        logger.warning("[ICD-11] NLM API HTTP %d for term: %s", exc.response.status_code, term)
    except Exception as exc:
        logger.warning("[ICD-11] NLM API error for term '%s': %s", term, exc)

    return []


def search_icd11_sync(term: str, max_results: int = 5) -> list[dict]:
    """Synchronous version for non-async contexts."""
    if not term or not term.strip():
        return []

    try:
        import requests
        resp = requests.get(
            NLM_ICD11_URL,
            params={
                "terms": term.strip(),
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
    except Exception as exc:
        logger.warning("[ICD-11] Sync search failed for '%s': %s", term, exc)

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
    Given a structured intake result, extract symptoms, red flags,
    and body area, then map them all to ICD-11 codes.
    Returns empty list on complete failure (non-blocking).
    """
    try:
        symptoms = []

        # Main symptom
        main = intake_data.get("main_symptom")
        if main:
            symptoms.append(main)

        # Associated symptoms
        associated = intake_data.get("associated_symptoms", [])
        symptoms.extend(associated)

        # Red flag indicators (often have good ICD-11 matches)
        red_flags = intake_data.get("red_flag_indicators", [])
        for flag in red_flags:
            if flag and flag not in symptoms:
                symptoms.append(flag)

        # Body area as additional search term
        body_area = intake_data.get("body_area", "")
        if body_area and body_area not in symptoms:
            symptoms.append(f"{body_area} pain")

        return await map_symptoms_to_icd11(symptoms)

    except Exception as exc:
        logger.warning("[ICD-11] map_intake_to_icd11 failed (non-blocking): %s", exc)
        return []
