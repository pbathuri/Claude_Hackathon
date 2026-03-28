"""
Concentrated test: simulated voice-style multi-turn conversation (POST /caller/ai-turn)
with client-held state (collected_symptoms + message_history) across turns — same pattern
as static/caller.html — then submit and verify doctor-portal contract.

Dashboard charts (doctor-portal app/page.tsx) use getCases() → GET /cases/patient-cases:
- PieChart "Triage Distribution" uses urgency counts (High / Medium / Low)
- BarChart "Cases by Country" uses country field

This test asserts API data that feeds those charts includes the submitted case.
"""
from __future__ import annotations

import os
import sys
import unittest

# Configure before any backend imports (database reads DATABASE_URL at import time)
os.environ.setdefault("ENABLE_KNOWLEDGE_GRAPH", "false")
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

_db_path = os.path.join(_root, "test_voice_conversation_state.db")
if os.path.exists(_db_path):
    try:
        os.remove(_db_path)
    except OSError:
        pass
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from database import init_db, SessionLocal  # noqa: E402
from services.country_service import seed_country_permissions  # noqa: E402


def _turn(client: TestClient, case_id: str, turn: int, user_message: str, collected: list[str], history: list[dict]):
    return client.post(
        "/caller/ai-turn",
        json={
            "case_id": case_id,
            "user_message": user_message,
            "turn_number": turn,
            "collected_symptoms": collected,
            "message_history": history,
            "language": "en",
        },
    )


class VoiceConversationStateTest(unittest.TestCase):
    """LLM/voice loop: user message → ai-turn → client updates state → repeat."""

    @classmethod
    def setUpClass(cls):
        init_db()
        db = SessionLocal()
        try:
            seed_country_permissions(db)
        finally:
            db.close()
        # Lifespan (scheduler, etc.) runs inside the context manager
        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)

    def test_symptoms_accumulate_across_turns_then_appear_in_patient_cases(self):
        c = self.client
        r = c.post("/caller/session/start", json={"phone_number": "+2349012345678"})
        self.assertEqual(r.status_code, 200, r.text)
        case_id = r.json()["case_id"]

        r = c.post("/caller/session/consent", json={"case_id": case_id, "consent_given": True})
        self.assertEqual(r.status_code, 200, r.text)

        history: list[dict] = []
        collected: list[str] = []

        # Turn 1 — user "voice" utterance (keyword STT when KG off)
        t1 = _turn(c, case_id, 1, "I have fever and headache", collected, history)
        self.assertEqual(t1.status_code, 200, t1.text)
        d1 = t1.json()
        s1 = d1.get("all_symptoms_so_far") or []
        self.assertGreaterEqual(len(s1), 1, "Expected at least one symptom detected in turn 1")
        self.assertTrue(d1.get("ai_message"), "Expected AI reply text")

        history.append({"role": "user", "text": "I have fever and headache"})
        history.append({"role": "assistant", "text": d1["ai_message"]})
        collected = list(s1)

        # Turn 2 — must retain turn 1 symptoms in collected_symptoms (browser pattern)
        t2 = _turn(c, case_id, 2, "Also cough and sore throat", collected, history)
        self.assertEqual(t2.status_code, 200, t2.text)
        d2 = t2.json()
        s2 = d2.get("all_symptoms_so_far") or []
        for x in s1:
            self.assertIn(
                x,
                s2,
                "Turn 2 should retain all symptoms from turn 1 (state across the call)",
            )
        self.assertGreater(len(s2), len(s1), "Turn 2 should add new symptoms")

        history.append({"role": "user", "text": "Also cough and sore throat"})
        history.append({"role": "assistant", "text": d2["ai_message"]})
        collected = list(s2)

        # Turn 3 — push to >=5 symptoms to complete (keyword list includes these)
        t3 = _turn(
            c,
            case_id,
            3,
            "I also have fatigue nausea and chest pain",
            collected,
            history,
        )
        self.assertEqual(t3.status_code, 200, t3.text)
        d3 = t3.json()
        s3 = d3.get("all_symptoms_so_far") or []
        for x in s2:
            self.assertIn(x, s3, "Turn 3 should retain prior symptoms")
        self.assertGreaterEqual(len(s3), 5, "Need enough symptoms to finish intake")
        self.assertTrue(d3.get("should_complete"), "Expected conversation completion flag")

        # Submit — same as caller pipeline after voice loop
        sub = c.post(
            "/caller/session/submit",
            json={
                "case_id": case_id,
                "symptoms": s3,
                "message_history": history,
                "transcript_summary": d3.get("transcript_summary") or "Multi-turn voice intake",
                "severity": 6,
                "duration": "2 days",
                "body_area": "Chest",
            },
        )
        self.assertEqual(sub.status_code, 200, sub.text)

        # Doctor portal data source for dashboard charts (Pie + Bar)
        pc = c.get("/cases/patient-cases")
        self.assertEqual(pc.status_code, 200, pc.text)
        cases = pc.json()
        self.assertIsInstance(cases, list)
        match = next((x for x in cases if x.get("caseId") == case_id), None)
        self.assertIsNotNone(match, "Submitted case must appear in GET /cases/patient-cases")

        # Fields consumed by dashboard (page.tsx): urgency → PieChart; country → BarChart
        self.assertIn(match.get("urgency"), ("High", "Medium", "Low"))
        self.assertTrue(match.get("country"))
        self.assertTrue(match.get("symptomSummary"), "symptomSummary feeds case list/detail text")

        # Simulate dashboard aggregation (same as app/page.tsx)
        high = sum(1 for x in cases if x.get("urgency") == "High")
        med = sum(1 for x in cases if x.get("urgency") == "Medium")
        low = sum(1 for x in cases if x.get("urgency") == "Low")
        self.assertEqual(high + med + low, len(cases), "Pie chart segments sum to case count")
        by_country: dict[str, int] = {}
        for x in cases:
            co = x.get("country") or ""
            by_country[co] = by_country.get(co, 0) + 1
        self.assertGreaterEqual(by_country.get(match["country"], 0), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
