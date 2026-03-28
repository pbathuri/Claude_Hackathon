"""
Medical Data Pipeline — Production scraping & enrichment for the knowledge graph.

Fetches structured medical data from authoritative public APIs:
1. WHO ICD-11 API — disease classification codes, definitions, hierarchy
2. MedlinePlus Connect API — consumer health topics, symptom–condition links
3. WHO GHO OData API — country-specific health indicators (NG, IN, PH, KE)

All data is cached to disk for offline reproducibility. The pipeline enriches
the knowledge graph with ICD-11 codes, new symptom→condition edges,
country-specific prevalence weights, and demographic risk connections.

Uses httpx for REST API calls. Scrapling is reserved for HTML scraping only.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx

from .graph_engine import (
    EdgeType,
    GraphEdge,
    MedicalKnowledgeGraph,
    NodeType,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "data" / "cache"

SOURCE_CONFIDENCE = {
    "icd11_who": 0.95,
    "medlineplus": 0.85,
    "who_gho": 0.85,
    "pipeline_enriched": 0.80,
}

TARGET_COUNTRIES = {
    "NG": "Nigeria",
    "IN": "India",
    "PH": "Philippines",
    "KE": "Kenya",
}

WHO_GHO_INDICATORS = {
    "WHS3_40": "malaria_incidence",
    "MDG_0000000020": "tb_incidence",
    "WHS_HIM_TB_HIV_PREV": "hiv_prevalence",
    "MDG_0000000026": "maternal_mortality",
    "WHOSIS_000001": "life_expectancy",
}

INDICATOR_TO_CONDITIONS: dict[str, list[str]] = {
    "malaria_incidence": ["Malaria"],
    "tb_incidence": ["Tuberculosis"],
    "hiv_prevalence": ["HIV/AIDS"],
    "maternal_mortality": ["Pre-eclampsia", "Postpartum Hemorrhage", "Ectopic Pregnancy"],
    "life_expectancy": [],
}

DEMOGRAPHIC_DEFINITIONS = [
    {"name": "Children (0-5)", "metadata": {"age_min": 0, "age_max": 5, "group": "pediatric"}},
    {"name": "Children (6-12)", "metadata": {"age_min": 6, "age_max": 12, "group": "pediatric"}},
    {"name": "Adolescents (13-17)", "metadata": {"age_min": 13, "age_max": 17, "group": "adolescent"}},
    {"name": "Young Adults (18-35)", "metadata": {"age_min": 18, "age_max": 35, "group": "young_adult"}},
    {"name": "Adults (36-55)", "metadata": {"age_min": 36, "age_max": 55, "group": "adult"}},
    {"name": "Older Adults (56-70)", "metadata": {"age_min": 56, "age_max": 70, "group": "senior"}},
    {"name": "Elderly (70+)", "metadata": {"age_min": 70, "age_max": 120, "group": "elderly"}},
    {"name": "Male", "metadata": {"sex": "male"}},
    {"name": "Female", "metadata": {"sex": "female"}},
    {"name": "Pregnant", "metadata": {"sex": "female", "pregnant": True}},
]

DEMOGRAPHIC_CONDITION_RISKS: list[tuple[str, str, float, float]] = [
    # (demographic_name, condition_name, base_weight, confidence)
    ("Children (0-5)", "Malaria", 0.7, 0.90),
    ("Children (0-5)", "Gastroenteritis", 0.6, 0.85),
    ("Children (0-5)", "Pneumonia", 0.65, 0.90),
    ("Children (0-5)", "Malnutrition", 0.5, 0.85),
    ("Children (6-12)", "Malaria", 0.6, 0.85),
    ("Children (6-12)", "Otitis Media", 0.5, 0.80),
    ("Adolescents (13-17)", "Major Depressive Disorder", 0.3, 0.75),
    ("Young Adults (18-35)", "Sexually Transmitted Infection", 0.4, 0.80),
    ("Young Adults (18-35)", "Urinary Tract Infection", 0.35, 0.80),
    ("Adults (36-55)", "Hypertension", 0.5, 0.90),
    ("Adults (36-55)", "Type 2 Diabetes", 0.45, 0.85),
    ("Adults (36-55)", "Coronary Artery Disease", 0.35, 0.80),
    ("Older Adults (56-70)", "Hypertension", 0.65, 0.90),
    ("Older Adults (56-70)", "Type 2 Diabetes", 0.55, 0.85),
    ("Older Adults (56-70)", "Osteoarthritis", 0.5, 0.85),
    ("Older Adults (56-70)", "COPD", 0.4, 0.80),
    ("Elderly (70+)", "Heart Failure", 0.5, 0.85),
    ("Elderly (70+)", "Stroke", 0.4, 0.85),
    ("Elderly (70+)", "Chronic Kidney Disease", 0.35, 0.80),
    ("Elderly (70+)", "Osteoarthritis", 0.6, 0.85),
    ("Male", "Prostate Cancer", 0.3, 0.90),
    ("Male", "Coronary Artery Disease", 0.35, 0.80),
    ("Male", "Gout", 0.3, 0.80),
    ("Female", "Breast Cancer", 0.25, 0.90),
    ("Female", "Urinary Tract Infection", 0.4, 0.85),
    ("Female", "Osteoarthritis", 0.35, 0.80),
    ("Female", "Anemia", 0.4, 0.85),
    ("Pregnant", "Pre-eclampsia", 0.35, 0.90),
    ("Pregnant", "Gestational Diabetes", 0.3, 0.85),
    ("Pregnant", "Postpartum Hemorrhage", 0.2, 0.85),
    ("Pregnant", "Ectopic Pregnancy", 0.15, 0.90),
    ("Pregnant", "Anemia", 0.45, 0.85),
]


# ── Cache Helpers ─────────────────────────────────────────────────────────────

def _ensure_cache_dir() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def _load_cache(name: str) -> Optional[dict[str, Any]]:
    path = CACHE_DIR / f"{name}_cache.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning("[Pipeline] Corrupt cache file %s — will re-fetch", path)
    return None


def _save_cache(name: str, data: dict[str, Any]) -> None:
    _ensure_cache_dir()
    path = CACHE_DIR / f"{name}_cache.json"
    path.write_text(json.dumps(data, indent=2, default=str))
    logger.info("[Pipeline] Cache saved → %s (%d bytes)", path.name, path.stat().st_size)


# ── HTTP Helpers ──────────────────────────────────────────────────────────────

@dataclass
class PipelineStats:
    """Tracks enrichment counts for the pipeline report."""
    icd11_codes_updated: int = 0
    icd11_definitions_added: int = 0
    medlineplus_topics_fetched: int = 0
    new_symptom_edges: int = 0
    who_indicators_fetched: int = 0
    country_risk_edges: int = 0
    demographic_nodes_added: int = 0
    demographic_edges_added: int = 0
    api_errors: int = 0
    cache_hits: int = 0
    started_at: float = field(default_factory=time.time)

    def elapsed(self) -> float:
        return time.time() - self.started_at

    def to_dict(self) -> dict:
        return {
            "icd11_codes_updated": self.icd11_codes_updated,
            "icd11_definitions_added": self.icd11_definitions_added,
            "medlineplus_topics_fetched": self.medlineplus_topics_fetched,
            "new_symptom_edges": self.new_symptom_edges,
            "who_indicators_fetched": self.who_indicators_fetched,
            "country_risk_edges": self.country_risk_edges,
            "demographic_nodes_added": self.demographic_nodes_added,
            "demographic_edges_added": self.demographic_edges_added,
            "api_errors": self.api_errors,
            "cache_hits": self.cache_hits,
            "elapsed_seconds": round(self.elapsed(), 2),
        }


async def _fetch_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    **kwargs: Any,
) -> Optional[httpx.Response]:
    for attempt in range(1, max_retries + 1):
        try:
            resp = await client.request(method, url, **kwargs)
            if resp.status_code == 429:
                wait = retry_delay * attempt
                logger.warning("[Pipeline] Rate limited (429) on %s — retrying in %.1fs", url, wait)
                await asyncio.sleep(wait)
                continue
            return resp
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
            if attempt == max_retries:
                logger.error("[Pipeline] Failed after %d retries: %s → %s", max_retries, url, exc)
                return None
            wait = retry_delay * attempt
            logger.warning("[Pipeline] Attempt %d/%d failed for %s: %s — retrying in %.1fs",
                           attempt, max_retries, url, exc, wait)
            await asyncio.sleep(wait)
    return None


# ── ICD-11 API Scraper ────────────────────────────────────────────────────────

async def fetch_icd11_data(terms: list[str], *, use_cache: bool = True) -> dict[str, Any]:
    """
    Fetch ICD-11 search results from the WHO ICD API for each term.
    Returns a dict keyed by search term with code, definition, parents, and related terms.
    """
    cache_name = "icd11"
    if use_cache:
        cached = _load_cache(cache_name)
        if cached is not None:
            logger.info("[ICD-11] Loaded %d entries from cache", len(cached.get("results", {})))
            return cached

    results: dict[str, list[dict]] = {}
    headers = {
        "Accept": "application/json",
        "API-Version": "v2",
        "Accept-Language": "en",
    }
    base_url = "https://id.who.int/icd/entity/search"

    async with httpx.AsyncClient(timeout=20, headers=headers) as client:
        for term in terms:
            resp = await _fetch_with_retry(client, "GET", base_url, params={"q": term})
            if resp and resp.status_code == 200:
                try:
                    data = resp.json()
                    entities = data.get("destinationEntities", [])
                    term_results = []
                    for ent in entities[:5]:
                        entry = {
                            "id": ent.get("id", ""),
                            "title": ent.get("title", ""),
                            "icd_code": ent.get("theCode", ""),
                            "definition": ent.get("definition", ""),
                            "chapter": ent.get("chapter", ""),
                            "score": ent.get("score", 0),
                        }
                        term_results.append(entry)
                    results[term] = term_results
                except Exception as exc:
                    logger.warning("[ICD-11] Parse error for '%s': %s", term, exc)
            else:
                logger.warning("[ICD-11] No results for '%s' (status=%s)",
                               term, resp.status_code if resp else "timeout")
            await asyncio.sleep(1.0)

    payload = {"fetched_at": time.time(), "term_count": len(terms), "results": results}
    _save_cache(cache_name, payload)
    logger.info("[ICD-11] Fetched data for %d/%d terms", len(results), len(terms))
    return payload


# ── MedlinePlus Connect API ───────────────────────────────────────────────────

async def fetch_medlineplus_data(
    icd_codes: dict[str, str],
    *,
    use_cache: bool = True,
) -> dict[str, Any]:
    """
    Fetch health topic info from MedlinePlus Connect for each ICD code.
    icd_codes: mapping of condition_name → icd_code (e.g. {"Malaria": "1F40"}).
    """
    cache_name = "medlineplus"
    if use_cache:
        cached = _load_cache(cache_name)
        if cached is not None:
            logger.info("[MedlinePlus] Loaded %d entries from cache", len(cached.get("results", {})))
            return cached

    results: dict[str, dict] = {}
    base_url = "https://connect.medlineplus.gov/service"

    async with httpx.AsyncClient(timeout=20) as client:
        for cond_name, icd_code in icd_codes.items():
            params = {
                "mainSearchCriteria.v.cs": "2.16.840.1.113883.6.90",
                "mainSearchCriteria.v.c": icd_code,
                "knowledgeResponseType": "application/json",
            }
            resp = await _fetch_with_retry(client, "GET", base_url, params=params)
            if resp and resp.status_code == 200:
                try:
                    data = resp.json()
                    feed = data.get("feed", {})
                    entries = feed.get("entry", [])
                    parsed_entries = []
                    for entry in entries:
                        title = entry.get("title", {}).get("_value", "")
                        summary_raw = entry.get("summary", {}).get("_value", "")
                        links = [
                            lnk.get("href", "")
                            for lnk in entry.get("link", [])
                            if lnk.get("href")
                        ]
                        symptoms = _extract_symptoms_from_summary(summary_raw)
                        parsed_entries.append({
                            "title": title,
                            "summary": summary_raw[:1000],
                            "links": links[:3],
                            "extracted_symptoms": symptoms,
                        })
                    if parsed_entries:
                        results[cond_name] = {
                            "icd_code": icd_code,
                            "entries": parsed_entries,
                        }
                except Exception as exc:
                    logger.warning("[MedlinePlus] Parse error for '%s': %s", cond_name, exc)
            await asyncio.sleep(0.5)

    payload = {"fetched_at": time.time(), "condition_count": len(icd_codes), "results": results}
    _save_cache(cache_name, payload)
    logger.info("[MedlinePlus] Fetched data for %d/%d conditions", len(results), len(icd_codes))
    return payload


def _extract_symptoms_from_summary(html_summary: str) -> list[str]:
    """
    Best-effort extraction of symptom-like terms from MedlinePlus HTML summaries.
    Looks for list items and common symptom patterns.
    """
    text = re.sub(r"<[^>]+>", " ", html_summary)
    text = re.sub(r"\s+", " ", text).strip()

    symptom_patterns = [
        r"(?:symptoms?\s+(?:include|are|may include|such as))\s*:?\s*([^.]+)",
        r"(?:signs?\s+and\s+symptoms?)\s*:?\s*([^.]+)",
        r"(?:you may (?:have|experience|notice))\s*:?\s*([^.]+)",
    ]
    found: list[str] = []
    for pat in symptom_patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            chunk = match.group(1)
            parts = re.split(r"[,;]|\band\b", chunk)
            for p in parts:
                clean = p.strip().lower()
                if 3 < len(clean) < 60:
                    found.append(clean)
    return found[:20]


# ── WHO GHO OData API ─────────────────────────────────────────────────────────

async def fetch_who_gho_data(
    country_codes: Optional[list[str]] = None,
    *,
    use_cache: bool = True,
) -> dict[str, Any]:
    """
    Fetch country-specific health indicators from the WHO GHO OData API.
    Indicators: malaria incidence, TB incidence, HIV prevalence, maternal mortality, life expectancy.
    """
    cache_name = "who_gho"
    if use_cache:
        cached = _load_cache(cache_name)
        if cached is not None:
            logger.info("[WHO-GHO] Loaded %d country entries from cache",
                        len(cached.get("results", {})))
            return cached

    countries = country_codes or list(TARGET_COUNTRIES.keys())
    results: dict[str, dict[str, Any]] = {}
    base_url = "https://ghoapi.azureedge.net/api"

    async with httpx.AsyncClient(timeout=20) as client:
        for cc in countries:
            country_data: dict[str, Any] = {}
            for indicator_code, indicator_name in WHO_GHO_INDICATORS.items():
                url = f"{base_url}/{indicator_code}"
                params = {"$filter": f"SpatialDim eq '{cc}'"}
                resp = await _fetch_with_retry(client, "GET", url, params=params)
                if resp and resp.status_code == 200:
                    try:
                        data = resp.json()
                        values = data.get("value", [])
                        if values:
                            latest = max(values, key=lambda v: int(v.get("TimeDim", 0) or 0))
                            country_data[indicator_name] = {
                                "value": latest.get("NumericValue"),
                                "year": latest.get("TimeDim"),
                                "indicator_code": indicator_code,
                                "dim_type": latest.get("Dim1", ""),
                            }
                    except Exception as exc:
                        logger.warning("[WHO-GHO] Parse error for %s/%s: %s", cc, indicator_name, exc)
                await asyncio.sleep(0.3)

            if country_data:
                results[cc] = {
                    "country_name": TARGET_COUNTRIES.get(cc, cc),
                    "indicators": country_data,
                }
            logger.info("[WHO-GHO] Fetched %d indicators for %s", len(country_data), cc)

    payload = {"fetched_at": time.time(), "country_count": len(countries), "results": results}
    _save_cache(cache_name, payload)
    logger.info("[WHO-GHO] Fetched data for %d/%d countries", len(results), len(countries))
    return payload


# ── Graph Enrichment Functions ────────────────────────────────────────────────

def enrich_icd11_codes(graph: MedicalKnowledgeGraph, icd11_data: dict[str, Any], stats: PipelineStats) -> None:
    """
    For each condition node, update or add the ICD-11 code and definition from API data.
    """
    api_results = icd11_data.get("results", {})
    conditions = graph.get_nodes_by_type(NodeType.CONDITION)

    for cond in conditions:
        cond_lower = cond.name.lower()
        matches = api_results.get(cond_lower) or api_results.get(cond.name)
        if not matches:
            for term, entries in api_results.items():
                if cond_lower in term.lower() or term.lower() in cond_lower:
                    matches = entries
                    break

        if matches and isinstance(matches, list) and len(matches) > 0:
            best = matches[0]
            new_code = best.get("icd_code", "")
            definition = best.get("definition", "")

            if new_code and (not cond.icd11_code or cond.icd11_code != new_code):
                cond.icd11_code = new_code
                stats.icd11_codes_updated += 1

            if definition:
                cond.metadata["icd11_definition"] = definition[:500]
                cond.metadata["icd11_chapter"] = best.get("chapter", "")
                stats.icd11_definitions_added += 1

    logger.info("[Enrich] ICD-11: %d codes updated, %d definitions added",
                stats.icd11_codes_updated, stats.icd11_definitions_added)


def enrich_symptom_condition_edges(
    graph: MedicalKnowledgeGraph,
    medlineplus_data: dict[str, Any],
    stats: PipelineStats,
) -> None:
    """
    From MedlinePlus data, discover new symptom→condition edges not present in the seed data.
    """
    api_results = medlineplus_data.get("results", {})

    for cond_name, cond_info in api_results.items():
        cond_node = graph.find_node(cond_name, NodeType.CONDITION)
        if not cond_node:
            continue

        for entry in cond_info.get("entries", []):
            for symptom_text in entry.get("extracted_symptoms", []):
                sym_node = graph.find_node(symptom_text, NodeType.SYMPTOM)
                if not sym_node:
                    sym_node = _fuzzy_match_symptom(graph, symptom_text)
                if not sym_node:
                    continue

                existing = graph.get_edge(sym_node.id, cond_node.id)
                if not existing:
                    graph.add_edge(
                        sym_node.id,
                        cond_node.id,
                        EdgeType.INDICATES,
                        base_weight=0.25,
                        confidence=SOURCE_CONFIDENCE["medlineplus"],
                        source="medlineplus",
                    )
                    stats.new_symptom_edges += 1

    logger.info("[Enrich] MedlinePlus: %d new symptom→condition edges", stats.new_symptom_edges)


def _fuzzy_match_symptom(graph: MedicalKnowledgeGraph, text: str) -> Optional[Any]:
    """Try to match a symptom text against existing symptom nodes with substring matching."""
    text_lower = text.lower().strip()
    all_symptoms = graph.get_nodes_by_type(NodeType.SYMPTOM)
    for sym in all_symptoms:
        sym_lower = sym.name.lower()
        if sym_lower == text_lower:
            return sym
        if sym_lower in text_lower or text_lower in sym_lower:
            return sym
        aka = sym.metadata.get("aka", "")
        if isinstance(aka, str) and aka.lower() in text_lower:
            return sym
    return None


def enrich_country_prevalence(
    graph: MedicalKnowledgeGraph,
    who_gho_data: dict[str, Any],
    stats: PipelineStats,
) -> None:
    """
    From WHO GHO data, create country demographic nodes and add DEMOGRAPHIC_RISK edges
    weighted by actual incidence/prevalence data.
    """
    api_results = who_gho_data.get("results", {})

    for cc, country_info in api_results.items():
        country_name = country_info.get("country_name", cc)
        country_node = graph.add_node(
            country_name,
            NodeType.DEMOGRAPHIC,
            metadata={"country_code": cc, "demographic_type": "country"},
        )

        indicators = country_info.get("indicators", {})
        for indicator_name, ind_data in indicators.items():
            value = ind_data.get("value")
            if value is None:
                continue

            related_conditions = INDICATOR_TO_CONDITIONS.get(indicator_name, [])
            for cond_name in related_conditions:
                cond_node = graph.find_node(cond_name, NodeType.CONDITION)
                if not cond_node:
                    continue

                existing = graph.get_edge(country_node.id, cond_node.id)
                if existing:
                    continue

                weight = _indicator_value_to_weight(indicator_name, value)
                graph.add_edge(
                    country_node.id,
                    cond_node.id,
                    EdgeType.DEMOGRAPHIC_RISK,
                    base_weight=weight,
                    confidence=SOURCE_CONFIDENCE["who_gho"],
                    source="who_gho",
                    metadata={
                        "indicator": indicator_name,
                        "raw_value": value,
                        "year": ind_data.get("year"),
                    },
                )
                stats.country_risk_edges += 1
        stats.who_indicators_fetched += len(indicators)

    logger.info("[Enrich] WHO-GHO: %d country→condition risk edges", stats.country_risk_edges)


def _indicator_value_to_weight(indicator_name: str, value: Any) -> float:
    """
    Convert a raw WHO indicator value to a 0–1 edge weight.
    Higher incidence/prevalence → higher weight.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.3

    if indicator_name == "malaria_incidence":
        return min(0.9, v / 500.0)
    elif indicator_name == "tb_incidence":
        return min(0.9, v / 600.0)
    elif indicator_name == "hiv_prevalence":
        return min(0.9, v / 30.0)
    elif indicator_name == "maternal_mortality":
        return min(0.9, v / 1000.0)
    elif indicator_name == "life_expectancy":
        return max(0.1, 1.0 - (v / 85.0))
    return 0.3


def add_demographic_nodes(graph: MedicalKnowledgeGraph, stats: PipelineStats) -> None:
    """
    Create demographic nodes (age groups, sex) and connect them to conditions
    via DEMOGRAPHIC_RISK edges based on established medical epidemiology.
    """
    for demo_def in DEMOGRAPHIC_DEFINITIONS:
        graph.add_node(
            demo_def["name"],
            NodeType.DEMOGRAPHIC,
            metadata={**demo_def["metadata"], "demographic_type": "group"},
        )
        stats.demographic_nodes_added += 1

    for demo_name, cond_name, weight, confidence in DEMOGRAPHIC_CONDITION_RISKS:
        demo_node = graph.find_node(demo_name, NodeType.DEMOGRAPHIC)
        cond_node = graph.find_node(cond_name, NodeType.CONDITION)
        if demo_node and cond_node:
            existing = graph.get_edge(demo_node.id, cond_node.id)
            if not existing:
                graph.add_edge(
                    demo_node.id,
                    cond_node.id,
                    EdgeType.DEMOGRAPHIC_RISK,
                    base_weight=weight,
                    confidence=confidence,
                    source="pipeline_enriched",
                )
                stats.demographic_edges_added += 1

    logger.info("[Enrich] Demographics: %d nodes, %d edges",
                stats.demographic_nodes_added, stats.demographic_edges_added)


# ── Pipeline Runner ───────────────────────────────────────────────────────────

class MedicalDataPipeline:
    """
    Orchestrates fetching from all medical data sources and enriching the graph.
    Supports running individual stages or the full pipeline.
    """

    def __init__(
        self,
        graph: MedicalKnowledgeGraph,
        *,
        use_cache: bool = True,
        country_codes: Optional[list[str]] = None,
    ):
        self.graph = graph
        self.use_cache = use_cache
        self.country_codes = country_codes or list(TARGET_COUNTRIES.keys())
        self.stats = PipelineStats()
        _ensure_cache_dir()

    def _get_condition_terms(self) -> list[str]:
        """Extract condition names from the graph for API lookups."""
        return [n.name.lower() for n in self.graph.get_nodes_by_type(NodeType.CONDITION)]

    def _get_condition_icd_map(self) -> dict[str, str]:
        """Map condition name → ICD-11 code for conditions that have one."""
        result = {}
        for node in self.graph.get_nodes_by_type(NodeType.CONDITION):
            if node.icd11_code:
                result[node.name] = node.icd11_code
        return result

    async def run_icd11(self) -> dict[str, Any]:
        """Fetch ICD-11 data and enrich graph condition nodes."""
        logger.info("[Pipeline] Starting ICD-11 enrichment...")
        terms = self._get_condition_terms()
        data = await fetch_icd11_data(terms, use_cache=self.use_cache)
        if not data.get("results"):
            self.stats.cache_hits += 1
        enrich_icd11_codes(self.graph, data, self.stats)
        return data

    async def run_medlineplus(self) -> dict[str, Any]:
        """Fetch MedlinePlus data and discover new symptom→condition edges."""
        logger.info("[Pipeline] Starting MedlinePlus enrichment...")
        icd_map = self._get_condition_icd_map()
        if not icd_map:
            logger.warning("[Pipeline] No ICD codes available — skipping MedlinePlus")
            return {}
        data = await fetch_medlineplus_data(icd_map, use_cache=self.use_cache)
        self.stats.medlineplus_topics_fetched = len(data.get("results", {}))
        enrich_symptom_condition_edges(self.graph, data, self.stats)
        return data

    async def run_who_gho(self) -> dict[str, Any]:
        """Fetch WHO GHO data and create country prevalence edges."""
        logger.info("[Pipeline] Starting WHO GHO enrichment...")
        data = await fetch_who_gho_data(self.country_codes, use_cache=self.use_cache)
        enrich_country_prevalence(self.graph, data, self.stats)
        return data

    def run_demographics(self) -> None:
        """Create demographic nodes and connect them to conditions."""
        logger.info("[Pipeline] Adding demographic nodes and edges...")
        add_demographic_nodes(self.graph, self.stats)

    async def run_full(self) -> dict[str, Any]:
        """
        Run the complete enrichment pipeline:
        1. ICD-11 codes & definitions
        2. MedlinePlus symptom–condition edges
        3. WHO GHO country prevalence
        4. Demographic risk connections
        """
        logger.info("=" * 60)
        logger.info("[Pipeline] Starting full medical data pipeline")
        logger.info("=" * 60)

        graph_stats_before = self.graph.stats()

        await self.run_icd11()
        await self.run_medlineplus()
        await self.run_who_gho()
        self.run_demographics()

        graph_stats_after = self.graph.stats()

        report = {
            "pipeline_stats": self.stats.to_dict(),
            "graph_before": {
                "nodes": graph_stats_before["total_nodes"],
                "edges": graph_stats_before["total_edges"],
            },
            "graph_after": {
                "nodes": graph_stats_after["total_nodes"],
                "edges": graph_stats_after["total_edges"],
            },
            "nodes_added": graph_stats_after["total_nodes"] - graph_stats_before["total_nodes"],
            "edges_added": graph_stats_after["total_edges"] - graph_stats_before["total_edges"],
        }

        logger.info("=" * 60)
        logger.info("[Pipeline] Complete in %.1fs", self.stats.elapsed())
        logger.info("[Pipeline] Nodes: %d → %d (+%d)",
                     report["graph_before"]["nodes"], report["graph_after"]["nodes"], report["nodes_added"])
        logger.info("[Pipeline] Edges: %d → %d (+%d)",
                     report["graph_before"]["edges"], report["graph_after"]["edges"], report["edges_added"])
        logger.info("[Pipeline] Stats: %s", self.stats.to_dict())
        logger.info("=" * 60)

        if self.graph.persist_path:
            self.graph.save()

        return report


# ── Integration with builder.py ───────────────────────────────────────────────

def enrich_graph_from_pipeline(
    graph: MedicalKnowledgeGraph,
    *,
    use_cache: bool = True,
    country_codes: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Synchronous entry point for the builder to call after seeding.
    Uses cached data if available; fetches from APIs otherwise.
    Returns an enrichment summary report.
    """
    pipeline = MedicalDataPipeline(graph, use_cache=use_cache, country_codes=country_codes)

    has_any_cache = any(
        (CACHE_DIR / f"{name}_cache.json").exists()
        for name in ("icd11", "medlineplus", "who_gho")
    )

    if not has_any_cache and use_cache:
        logger.info("[Pipeline] No cache files found — running full pipeline fetch")

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, pipeline.run_full())
            return future.result()
    else:
        return asyncio.run(pipeline.run_full())


# ── CLI Entry Point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s │ %(levelname)-7s │ %(message)s",
        datefmt="%H:%M:%S",
    )

    # Build or load the graph so we have nodes to enrich
    sys.path.insert(0, str(BASE_DIR))
    from knowledge_graph.builder import build_medical_knowledge_graph

    persist_path = str(BASE_DIR / "data" / "knowledge_graph.json")
    graph = build_medical_knowledge_graph(persist_path=persist_path)

    logger.info("Graph loaded: %d nodes, %d edges", len(graph.nodes), len(graph.edges))

    skip_cache = "--no-cache" in sys.argv
    pipeline = MedicalDataPipeline(graph, use_cache=not skip_cache)

    report = asyncio.run(pipeline.run_full())

    print("\n" + "=" * 60)
    print("PIPELINE REPORT")
    print("=" * 60)
    for key, value in report.get("pipeline_stats", {}).items():
        print(f"  {key:30s}: {value}")
    print(f"\n  Nodes added: {report.get('nodes_added', 0)}")
    print(f"  Edges added: {report.get('edges_added', 0)}")
    print("=" * 60)
