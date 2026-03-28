"""
Medical Knowledge Scraper — Powered by Scrapling.

Scrapes medical data from public sources to populate the knowledge graph:
1. WHO ICD-11 — Disease classification hierarchy + symptom associations
2. MedlinePlus — Symptom-condition relationships (consumer health)
3. NLM Clinical Tables — ICD-11 code search API
4. WHO GHO — Country health indicators for demographic risk
5. OpenFDA — Drug adverse events (medication → condition edges)

Uses Scrapling's Fetcher for API calls and StealthyFetcher for web pages.
Designed to be run once for initial seeding, then periodically for updates.

The scraper feeds directly into the knowledge graph, creating nodes and edges
with appropriate confidence scores based on source authority.
"""

import asyncio
import json
import logging
import time
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Source confidence ratings (0-1)
SOURCE_CONFIDENCE = {
    "icd11_who": 0.95,      # WHO ICD-11 — gold standard
    "nlm_clinical": 0.90,   # NLM Clinical Tables — authoritative
    "medlineplus": 0.85,    # MedlinePlus — NIH consumer health
    "openfda": 0.80,        # OpenFDA — real adverse event reports
    "who_gho": 0.85,        # WHO GHO — epidemiological data
    "medical_textbook": 0.95,  # Curated from medical references
    "learned": 0.30,        # Auto-discovered via co-occurrence
}


class MedicalDataScraper:
    """
    Scrapes medical data from public APIs and websites.
    Uses Scrapling for web scraping and httpx for API calls.
    """

    def __init__(self, cache_dir: str = "./data/scraper_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._scrapling_available = self._check_scrapling()

    def _check_scrapling(self) -> bool:
        """Check if Scrapling is available."""
        try:
            import sys
            scrapling_path = "/Users/prady/Desktop/BOOK:LLM?/book-project/external/Scrapling"
            if scrapling_path not in sys.path:
                sys.path.insert(0, scrapling_path)
            from scrapling.fetchers import Fetcher
            return True
        except ImportError:
            logger.warning("[Scraper] Scrapling not available — using httpx fallback")
            return False

    # ── NLM ICD-11 Clinical Tables API ───────────────────────────────────

    async def scrape_icd11_codes(self, terms: list[str]) -> list[dict]:
        """
        Search NLM Clinical Tables API for ICD-11 codes.
        Returns structured data for each term with code, title, and hierarchy.
        """
        import httpx
        results = []
        base_url = "https://clinicaltables.nlm.nih.gov/api/icd11_codes/v3/search"

        async with httpx.AsyncClient(timeout=15) as client:
            for term in terms:
                try:
                    r = await client.get(base_url, params={"sf": "code,title", "terms": term, "maxList": 10})
                    if r.status_code == 200:
                        data = r.json()
                        # NLM returns [total_count, codes, extra, [display_strings]]
                        if len(data) >= 4 and data[3]:
                            for entry in data[3]:
                                if len(entry) >= 2:
                                    results.append({
                                        "code": entry[0],
                                        "title": entry[1],
                                        "search_term": term,
                                        "source": "nlm_clinical",
                                    })
                    await asyncio.sleep(0.2)  # rate limit
                except Exception as exc:
                    logger.warning("[Scraper] ICD-11 search failed for '%s': %s", term, exc)

        logger.info("[Scraper] ICD-11 scraped: %d codes from %d terms", len(results), len(terms))
        self._cache("icd11_codes", results)
        return results

    # ── MedlinePlus Health Topics ────────────────────────────────────────

    async def scrape_medlineplus_topics(self, topics: list[str]) -> list[dict]:
        """
        Scrape MedlinePlus for symptom-condition relationships.
        Uses the MedlinePlus Connect REST API for structured data.
        """
        import httpx
        results = []
        base_url = "https://connect.medlineplus.gov/service"

        async with httpx.AsyncClient(timeout=15) as client:
            for topic in topics:
                try:
                    # Search by keyword
                    r = await client.get(base_url, params={
                        "mainSearchCriteria.v.cs": "2.16.840.1.113883.6.90",
                        "mainSearchCriteria.v.dn": topic,
                        "informationRecipient.languageCode.c": "en",
                        "knowledgeResponseType": "application/json",
                    })
                    if r.status_code == 200:
                        data = r.json()
                        feed = data.get("feed", {})
                        entries = feed.get("entry", [])
                        for entry in entries:
                            title = entry.get("title", {}).get("_value", "")
                            summary = entry.get("summary", {}).get("_value", "")
                            results.append({
                                "topic": topic,
                                "title": title,
                                "summary": summary[:500],
                                "source": "medlineplus",
                            })
                    await asyncio.sleep(0.3)
                except Exception as exc:
                    logger.warning("[Scraper] MedlinePlus failed for '%s': %s", topic, exc)

        logger.info("[Scraper] MedlinePlus scraped: %d entries from %d topics", len(results), len(topics))
        self._cache("medlineplus", results)
        return results

    # ── WHO GHO Country Health Data ──────────────────────────────────────

    async def scrape_who_country_data(self, country_codes: list[str]) -> list[dict]:
        """
        Scrape WHO GHO OData API for country health indicators.
        Used to create demographic_risk edges in the knowledge graph.
        """
        import httpx
        base_url = "https://ghoapi.azureedge.net/api"
        indicators = {
            "physicians_per_10k": "HWF_0001",
            "hospital_beds_per_10k": "WHS6_102",
            "uhc_coverage_index": "UHC_SCI_CMPND",
            "neonatal_mortality": "MDG_0004",
            "maternal_mortality": "MDG_0000000026",
        }
        results = []

        async with httpx.AsyncClient(timeout=15) as client:
            for cc in country_codes:
                for indicator_name, code in indicators.items():
                    try:
                        url = f"{base_url}/{code}?$filter=SpatialDim eq '{cc}'"
                        r = await client.get(url)
                        if r.status_code == 200:
                            data = r.json()
                            values = data.get("value", [])
                            if values:
                                latest = max(values, key=lambda v: v.get("TimeDim", 0))
                                results.append({
                                    "country_code": cc,
                                    "indicator": indicator_name,
                                    "value": latest.get("NumericValue"),
                                    "year": latest.get("TimeDim"),
                                    "source": "who_gho",
                                })
                        await asyncio.sleep(0.1)
                    except Exception as exc:
                        logger.warning("[Scraper] WHO GHO failed for %s/%s: %s", cc, indicator_name, exc)

        logger.info("[Scraper] WHO GHO scraped: %d indicators for %d countries",
                     len(results), len(country_codes))
        self._cache("who_gho", results)
        return results

    # ── OpenFDA Drug Adverse Events ──────────────────────────────────────

    async def scrape_openfda_adverse_events(self, drugs: list[str]) -> list[dict]:
        """
        Scrape OpenFDA for drug adverse event data.
        Creates medication → condition contraindicates edges.
        """
        import httpx
        results = []
        base_url = "https://api.fda.gov/drug/event.json"

        async with httpx.AsyncClient(timeout=15) as client:
            for drug in drugs:
                try:
                    r = await client.get(base_url, params={
                        "search": f'patient.drug.medicinalproduct:"{drug}"',
                        "count": "patient.reaction.reactionmeddrapt.exact",
                        "limit": 10,
                    })
                    if r.status_code == 200:
                        data = r.json()
                        for result_item in data.get("results", []):
                            results.append({
                                "drug": drug,
                                "reaction": result_item.get("term", ""),
                                "count": result_item.get("count", 0),
                                "source": "openfda",
                            })
                    await asyncio.sleep(0.5)  # OpenFDA rate limits
                except Exception as exc:
                    logger.warning("[Scraper] OpenFDA failed for '%s': %s", drug, exc)

        logger.info("[Scraper] OpenFDA scraped: %d adverse events for %d drugs",
                     len(results), len(drugs))
        self._cache("openfda", results)
        return results

    # ── Scrapling-based Web Scraping ─────────────────────────────────────

    def scrape_symptom_checker_data(self) -> list[dict]:
        """
        Use Scrapling to scrape symptom-condition data from public health sites.
        Targets structured medical information pages.
        """
        if not self._scrapling_available:
            logger.info("[Scraper] Scrapling not available — skipping web scrape")
            return []

        try:
            import sys
            scrapling_path = "/Users/prady/Desktop/BOOK:LLM?/book-project/external/Scrapling"
            if scrapling_path not in sys.path:
                sys.path.insert(0, scrapling_path)
            from scrapling.fetchers import Fetcher

            results = []

            # Mayo Clinic Symptom Index (public, well-structured)
            symptom_categories = [
                "abdominal-pain", "chest-pain", "headache", "fever",
                "fatigue", "dizziness", "nausea", "back-pain",
                "joint-pain", "shortness-of-breath", "cough", "rash",
            ]

            for symptom_slug in symptom_categories:
                try:
                    url = f"https://www.mayoclinic.org/symptoms/{symptom_slug}/basics/causes/sym-20050728"
                    response = Fetcher.get(url)
                    if response.status == 200:
                        # Extract cause listings
                        causes = response.css(".content-within .content li::text").getall()
                        if not causes:
                            causes = response.css("article li::text").getall()

                        for cause in causes[:20]:  # cap at 20 per symptom
                            clean = cause.strip()
                            if clean and len(clean) > 3:
                                results.append({
                                    "symptom": symptom_slug.replace("-", " "),
                                    "possible_cause": clean,
                                    "source": "mayo_clinic",
                                })

                    time.sleep(1.0)  # polite scraping
                except Exception as exc:
                    logger.warning("[Scraper] Mayo Clinic failed for '%s': %s", symptom_slug, exc)

            logger.info("[Scraper] Scrapling web scrape: %d symptom-cause pairs", len(results))
            self._cache("symptom_checker", results)
            return results

        except Exception as exc:
            logger.error("[Scraper] Scrapling scrape failed: %s", exc)
            return []

    # ── Full Pipeline ────────────────────────────────────────────────────

    async def run_full_scrape(self, country_codes: Optional[list[str]] = None) -> dict:
        """
        Run the complete scraping pipeline.
        Returns a summary of all scraped data.
        """
        countries = country_codes or ["NGA", "IND", "PHL", "KEN"]
        summary = {"timestamp": time.time(), "sources": {}}

        # Parallel API scrapes
        common_symptoms = [
            "headache", "fever", "cough", "chest pain", "abdominal pain",
            "back pain", "fatigue", "nausea", "dizziness", "shortness of breath",
            "joint pain", "rash", "diarrhea", "vomiting", "sore throat",
            "difficulty breathing", "swelling", "bleeding", "numbness", "weight loss",
        ]

        common_conditions = [
            "malaria", "typhoid", "tuberculosis", "pneumonia", "hypertension",
            "diabetes", "HIV", "dengue", "cholera", "hepatitis",
            "anemia", "asthma", "heart failure", "stroke", "meningitis",
            "gastroenteritis", "urinary tract infection", "appendicitis",
            "eczema", "depression",
        ]

        common_drugs = [
            "paracetamol", "amoxicillin", "metformin", "ibuprofen",
            "omeprazole", "amlodipine", "ciprofloxacin", "artemether",
        ]

        # Run API scrapes in parallel
        icd11_task = self.scrape_icd11_codes(common_symptoms + common_conditions)
        who_task = self.scrape_who_country_data(countries)
        fda_task = self.scrape_openfda_adverse_events(common_drugs)
        medline_task = self.scrape_medlineplus_topics(common_conditions[:10])

        icd11_results, who_results, fda_results, medline_results = await asyncio.gather(
            icd11_task, who_task, fda_task, medline_task,
            return_exceptions=True,
        )

        summary["sources"]["icd11"] = len(icd11_results) if isinstance(icd11_results, list) else 0
        summary["sources"]["who_gho"] = len(who_results) if isinstance(who_results, list) else 0
        summary["sources"]["openfda"] = len(fda_results) if isinstance(fda_results, list) else 0
        summary["sources"]["medlineplus"] = len(medline_results) if isinstance(medline_results, list) else 0

        # Scrapling web scrape (sync, runs in executor)
        loop = asyncio.get_event_loop()
        try:
            web_results = await loop.run_in_executor(None, self.scrape_symptom_checker_data)
            summary["sources"]["web_scrape"] = len(web_results)
        except Exception:
            summary["sources"]["web_scrape"] = 0

        total = sum(summary["sources"].values())
        logger.info("[Scraper] Full scrape complete: %d total data points | %s", total, summary["sources"])
        summary["total_data_points"] = total

        return summary

    # ── Cache Helpers ────────────────────────────────────────────────────

    def _cache(self, name: str, data: list[dict]) -> None:
        """Cache scraped data to disk."""
        path = self.cache_dir / f"{name}.json"
        path.write_text(json.dumps(data, indent=2))

    def load_cache(self, name: str) -> list[dict]:
        """Load cached data."""
        path = self.cache_dir / f"{name}.json"
        if path.exists():
            return json.loads(path.read_text())
        return []
