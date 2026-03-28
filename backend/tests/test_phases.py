"""
Phase 01-08 unit and integration tests.

Tests:
- Conversation model & fact extraction (Phase 01)
- Triage score breakdown (Phase 01)
- Case state machine transitions (Phase 01/04)
- Layered red flag detection (Phase 03)
- Conversation guard / sufficiency (Phase 03)
- Auth middleware (Phase 02)
- FHIR mapping (Phase 06)
- Contract alignment (Phase 05)
"""
from __future__ import annotations

import os
import sys
import unittest

# Configure before any backend imports
os.environ.setdefault("ENABLE_KNOWLEDGE_GRAPH", "false")
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

_db_path = os.path.join(_root, "test_phases.db")
if os.path.exists(_db_path):
    try:
        os.remove(_db_path)
    except OSError:
        pass
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"


class TestConversationModel(unittest.TestCase):
    """Phase 01: Canonical conversation model."""

    def test_case_status_valid_transitions(self):
        from models.conversation import validate_transition, CaseStatus
        # Valid
        self.assertTrue(validate_transition("created", "active_intake"))
        self.assertTrue(validate_transition("active_intake", "pending_review"))
        self.assertTrue(validate_transition("pending_review", "assigned"))
        self.assertTrue(validate_transition("assigned", "in_review"))
        self.assertTrue(validate_transition("in_review", "responded"))
        self.assertTrue(validate_transition("responded", "closed"))
        # Emergency escalation from any active state
        self.assertTrue(validate_transition("active_intake", "escalated"))
        self.assertTrue(validate_transition("in_review", "escalated"))
        # Recovery from escalated
        self.assertTrue(validate_transition("escalated", "assigned"))

    def test_case_status_invalid_transitions(self):
        from models.conversation import validate_transition
        # Cannot go backwards
        self.assertFalse(validate_transition("assigned", "created"))
        self.assertFalse(validate_transition("responded", "active_intake"))
        # Closed is terminal
        self.assertFalse(validate_transition("closed", "assigned"))
        self.assertFalse(validate_transition("closed", "escalated"))
        # Invalid status strings
        self.assertFalse(validate_transition("bogus", "assigned"))

    def test_extracted_fact_creation(self):
        from models.conversation import ExtractedFact, FactSource
        fact = ExtractedFact(
            fact_type="symptom",
            value="fever",
            source=FactSource.PATIENT_STATED,
            confidence=0.9,
            turn_number=1,
            raw_text="I have a fever",
        )
        self.assertEqual(fact.fact_type, "symptom")
        self.assertEqual(fact.confidence, 0.9)
        self.assertEqual(fact.source, FactSource.PATIENT_STATED)

    def test_conversation_summary_get_symptoms(self):
        from models.conversation import (
            ConversationSummary, ExtractedFact, FactSource,
        )
        summary = ConversationSummary()
        summary.extracted_facts = [
            ExtractedFact(fact_type="symptom", value="fever", source=FactSource.PATIENT_STATED),
            ExtractedFact(fact_type="symptom", value="cough", source=FactSource.PATIENT_STATED),
            ExtractedFact(fact_type="severity", value="7", source=FactSource.PATIENT_STATED),
            ExtractedFact(fact_type="duration", value="3 days", source=FactSource.PATIENT_STATED),
        ]
        symptoms = summary.get_symptoms()
        self.assertEqual(symptoms, ["fever", "cough"])
        self.assertEqual(summary.get_severity(), 7)
        self.assertEqual(summary.get_duration(), "3 days")

    def test_triage_score_breakdown_compute(self):
        from models.conversation import TriageScoreBreakdown
        breakdown = TriageScoreBreakdown(
            triage_level="YELLOW",
            base_score=50.0,
            severity_score=20.0,
            red_flag_score=15.0,
            country_tier_score=30.0,
        )
        total = breakdown.compute_total()
        self.assertEqual(total, 115.0)
        self.assertEqual(breakdown.total_priority, 115.0)


class TestTriageBreakdown(unittest.TestCase):
    """Phase 01: Explainable triage scoring."""

    def test_red_triage_high_severity(self):
        from services.triage_service import build_triage_breakdown
        bd = build_triage_breakdown(
            triage_level="RED",
            severity=9,
            red_flags=["Chest Pain", "Difficulty Breathing"],
            symptom_count=4,
            duration="2 hours",
            kg_confidence=0.8,
            country_tier=3,
        )
        self.assertEqual(bd["triage_level"], "RED")
        self.assertGreater(bd["total_priority"], 100)
        self.assertGreater(bd["red_flag_score"], 0)
        self.assertGreater(bd["severity_score"], 0)
        self.assertIn("RED", bd["explanation"])

    def test_green_triage_low_severity(self):
        from services.triage_service import build_triage_breakdown
        bd = build_triage_breakdown(
            triage_level="GREEN",
            severity=2,
            red_flags=[],
            symptom_count=1,
            duration="1 week",
        )
        self.assertEqual(bd["triage_level"], "GREEN")
        self.assertLess(bd["total_priority"], 80)
        self.assertEqual(bd["red_flag_score"], 0)

    def test_duration_acute_vs_chronic(self):
        from services.triage_service import build_triage_breakdown
        acute = build_triage_breakdown("YELLOW", duration="2 hours")
        chronic = build_triage_breakdown("YELLOW", duration="3 months")
        self.assertGreater(acute["duration_score"], chronic["duration_score"])


class TestRedFlagRules(unittest.TestCase):
    """Phase 03: Layered emergency detection."""

    def test_english_keywords_detect_chest_pain(self):
        from safety.red_flag_rules import detect_red_flags
        result = detect_red_flags("I'm having severe chest pain and can't breathe")
        self.assertTrue(result.is_emergency)
        self.assertTrue(result.should_complete)
        layers = [f["layer"] for f in result.flags]
        self.assertIn("keyword", layers)

    def test_spanish_multilingual_detection(self):
        from safety.red_flag_rules import detect_red_flags
        result = detect_red_flags(
            "Tengo dolor de pecho muy fuerte",
            language="es",
            english_text="I have very strong chest pain",
        )
        self.assertTrue(result.is_emergency)
        layers = [f["layer"] for f in result.flags]
        # Should detect via both keyword (english) and multilingual (spanish)
        self.assertIn("keyword", layers)

    def test_hindi_multilingual_detection(self):
        from safety.red_flag_rules import detect_red_flags
        result = detect_red_flags(
            "मुझे छाती में दर्द है",
            language="hi",
        )
        self.assertTrue(result.is_emergency)
        layers = [f["layer"] for f in result.flags]
        self.assertIn("multilingual_pattern", layers)

    def test_non_emergency_text(self):
        from safety.red_flag_rules import detect_red_flags
        result = detect_red_flags("I have a mild headache and runny nose")
        self.assertFalse(result.is_emergency)
        self.assertEqual(len(result.flags), 0)

    def test_suicidal_ideation_detected(self):
        from safety.red_flag_rules import detect_red_flags
        result = detect_red_flags("I want to kill myself")
        self.assertTrue(result.is_emergency)
        self.assertTrue(result.should_complete)


class TestConversationGuard(unittest.TestCase):
    """Phase 03: Conversation guard / sufficiency check."""

    def test_emergency_forces_completion(self):
        from models.conversation import ConversationSummary
        from safety.conversation_guard import check_conversation_sufficiency
        summary = ConversationSummary(emergency_flags=["chest pain"])
        verdict = check_conversation_sufficiency(summary, turn_number=1)
        self.assertTrue(verdict.force_complete)
        self.assertFalse(verdict.should_continue)

    def test_max_turns_forces_completion(self):
        from models.conversation import ConversationSummary
        from safety.conversation_guard import check_conversation_sufficiency
        summary = ConversationSummary()
        verdict = check_conversation_sufficiency(summary, turn_number=12)
        self.assertTrue(verdict.force_complete)
        self.assertEqual(verdict.reason, "max_turns_reached")

    def test_sufficient_info_triggers_completion(self):
        from models.conversation import ConversationSummary, ExtractedFact, FactSource
        from safety.conversation_guard import check_conversation_sufficiency
        summary = ConversationSummary()
        summary.extracted_facts = [
            ExtractedFact(fact_type="symptom", value="fever", source=FactSource.PATIENT_STATED),
            ExtractedFact(fact_type="symptom", value="cough", source=FactSource.PATIENT_STATED),
            ExtractedFact(fact_type="symptom", value="headache", source=FactSource.PATIENT_STATED),
            ExtractedFact(fact_type="severity", value="7", source=FactSource.PATIENT_STATED),
            ExtractedFact(fact_type="duration", value="3 days", source=FactSource.PATIENT_STATED),
        ]
        verdict = check_conversation_sufficiency(summary, turn_number=3)
        self.assertTrue(verdict.should_complete)
        self.assertEqual(verdict.reason, "sufficient_information")

    def test_stale_conversation_completes(self):
        from models.conversation import ConversationSummary
        from safety.conversation_guard import check_conversation_sufficiency
        summary = ConversationSummary()
        verdict = check_conversation_sufficiency(
            summary, turn_number=4, consecutive_stale_turns=3,
        )
        self.assertTrue(verdict.should_complete)
        self.assertEqual(verdict.reason, "stale_conversation")

    def test_early_turns_continue(self):
        from models.conversation import ConversationSummary
        from safety.conversation_guard import check_conversation_sufficiency
        summary = ConversationSummary()
        verdict = check_conversation_sufficiency(summary, turn_number=1)
        self.assertTrue(verdict.should_continue)
        self.assertFalse(verdict.should_complete)

    def test_fact_extraction_severity(self):
        from safety.conversation_guard import extract_facts_from_text
        facts = extract_facts_from_text("Pain is 8 out of 10", turn_number=1, existing_symptoms=[])
        severity_facts = [f for f in facts if f.fact_type == "severity"]
        self.assertEqual(len(severity_facts), 1)
        self.assertEqual(severity_facts[0].value, "8")

    def test_fact_extraction_duration(self):
        from safety.conversation_guard import extract_facts_from_text
        facts = extract_facts_from_text("I've had this for 3 days", turn_number=1, existing_symptoms=[])
        duration_facts = [f for f in facts if f.fact_type == "duration"]
        self.assertEqual(len(duration_facts), 1)
        self.assertEqual(duration_facts[0].value, "3 days")

    def test_fact_extraction_symptoms(self):
        from safety.conversation_guard import extract_facts_from_text
        facts = extract_facts_from_text(
            "I have fever and headache with nausea",
            turn_number=1,
            existing_symptoms=[],
        )
        symptom_facts = [f for f in facts if f.fact_type == "symptom"]
        symptom_values = [f.value for f in symptom_facts]
        self.assertIn("fever", symptom_values)
        self.assertIn("headache", symptom_values)
        self.assertIn("nausea", symptom_values)

    def test_fact_extraction_dedup(self):
        from safety.conversation_guard import extract_facts_from_text
        facts = extract_facts_from_text(
            "I also have cough",
            turn_number=2,
            existing_symptoms=["fever", "cough"],  # cough already known
        )
        symptom_facts = [f for f in facts if f.fact_type == "symptom"]
        symptom_values = [f.value for f in symptom_facts]
        self.assertNotIn("cough", symptom_values)

    def test_repetition_detection(self):
        from safety.conversation_guard import check_repetition
        prev = [
            "Can you tell me more about your symptoms?",
            "How long have you been experiencing this?",
        ]
        # Similar message
        self.assertTrue(check_repetition(
            "Can you tell me more about your symptoms please?",
            prev, threshold=0.7,
        ))
        # Different message
        self.assertFalse(check_repetition(
            "What medications are you currently taking?",
            prev,
        ))


class TestAuthMiddleware(unittest.TestCase):
    """Phase 02: Auth middleware token creation and verification."""

    def test_create_and_verify_doctor_token(self):
        from auth.middleware import create_doctor_token, verify_doctor_token
        token = create_doctor_token("doc-123", role="doctor", tier=2)
        payload = verify_doctor_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "doc-123")
        self.assertEqual(payload["role"], "doctor")
        self.assertEqual(payload["tier"], 2)

    def test_invalid_token_rejected(self):
        from auth.middleware import verify_doctor_token
        self.assertIsNone(verify_doctor_token("invalid.token"))
        self.assertIsNone(verify_doctor_token(""))
        self.assertIsNone(verify_doctor_token("a.b.c"))

    def test_tampered_token_rejected(self):
        from auth.middleware import create_doctor_token, verify_doctor_token
        token = create_doctor_token("doc-123")
        parts = token.split(".")
        tampered = parts[0] + ".0000000000000000"
        self.assertIsNone(verify_doctor_token(tampered))

    def test_caller_session_creation(self):
        from auth.middleware import create_caller_session, verify_caller_session
        token = create_caller_session("case-abc-123")
        self.assertTrue(verify_caller_session("case-abc-123", token))
        self.assertFalse(verify_caller_session("case-abc-123", "wrong-token"))
        self.assertFalse(verify_caller_session("wrong-case", token))


class TestFHIRMapper(unittest.TestCase):
    """Phase 06: FHIR R4 resource mapping."""

    def test_patient_resource(self):
        from adapters.fhir_mapper import map_patient_to_fhir
        fhir = map_patient_to_fhir("p-123", "KE", "sw", "abc123hash")
        self.assertEqual(fhir["resourceType"], "Patient")
        self.assertEqual(fhir["id"], "p-123")
        self.assertEqual(fhir["address"][0]["country"], "KE")
        self.assertEqual(fhir["communication"][0]["language"]["coding"][0]["code"], "sw")

    def test_encounter_resource(self):
        from adapters.fhir_mapper import map_case_to_encounter
        fhir = map_case_to_encounter(
            "c-456", "p-123", "assigned", "RED", "KE", "Severe headache",
        )
        self.assertEqual(fhir["resourceType"], "Encounter")
        self.assertEqual(fhir["status"], "in-progress")
        self.assertEqual(fhir["priority"]["coding"][0]["code"], "EM")
        self.assertEqual(fhir["subject"]["reference"], "Patient/p-123")

    def test_conditions_with_icd11(self):
        from adapters.fhir_mapper import map_symptoms_to_conditions
        fhir = map_symptoms_to_conditions(
            "c-456", "p-123",
            symptoms=["fever", "headache"],
            icd11_codes=["MG30", "8A80"],
        )
        self.assertEqual(len(fhir), 2)
        self.assertEqual(fhir[0]["resourceType"], "Condition")
        self.assertEqual(fhir[0]["code"]["coding"][0]["code"], "MG30")
        self.assertEqual(fhir[1]["code"]["coding"][0]["code"], "8A80")

    def test_severity_observation(self):
        from adapters.fhir_mapper import map_severity_to_observation
        fhir = map_severity_to_observation("c-456", "p-123", 8)
        self.assertEqual(fhir["resourceType"], "Observation")
        self.assertEqual(fhir["valueInteger"], 8)
        self.assertEqual(fhir["code"]["coding"][0]["code"], "72514-3")

    def test_consent_resource(self):
        from adapters.fhir_mapper import map_consent_to_fhir
        fhir = map_consent_to_fhir("p-123", "c-456", True, "IN")
        self.assertEqual(fhir["resourceType"], "Consent")
        self.assertEqual(fhir["status"], "active")

    def test_full_bundle(self):
        from adapters.fhir_mapper import build_case_bundle
        bundle = build_case_bundle(
            case_id="c-789",
            patient_id="p-123",
            status="assigned",
            triage_level="YELLOW",
            symptoms=["fever", "cough"],
            severity=6,
            icd11_codes=["MG30"],
            country_code="NG",
            chief_complaint="Fever and cough",
            consent_given=True,
            doctor_id="d-001",
            doctor_name="Dr. Test",
            doctor_specialty="General Medicine",
        )
        self.assertEqual(bundle["resourceType"], "Bundle")
        self.assertEqual(bundle["type"], "collection")
        resource_types = [e["resource"]["resourceType"] for e in bundle["entry"]]
        self.assertIn("Patient", resource_types)
        self.assertIn("Encounter", resource_types)
        self.assertIn("Consent", resource_types)
        self.assertIn("Condition", resource_types)
        self.assertIn("Observation", resource_types)
        self.assertIn("Practitioner", resource_types)


class TestContractAlignment(unittest.TestCase):
    """Phase 05: Backend ↔ Frontend contract tests."""

    @classmethod
    def setUpClass(cls):
        from database import init_db, SessionLocal
        from services.country_service import seed_country_permissions
        init_db()
        db = SessionLocal()
        try:
            seed_country_permissions(db)
        finally:
            db.close()
        from fastapi.testclient import TestClient
        from main import app
        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)

    def test_patient_cases_contract_shape(self):
        """GET /cases/patient-cases returns the shape doctor-portal expects."""
        r = self.client.get("/cases/patient-cases")
        self.assertEqual(r.status_code, 200)
        cases = r.json()
        self.assertIsInstance(cases, list)
        # If we have cases, verify shape
        if cases:
            c = cases[0]
            for key in ["caseId", "urgency", "country", "status"]:
                self.assertIn(key, c, f"Missing expected key: {key}")

    def test_submit_produces_triage_breakdown(self):
        """POST /caller/session/submit should include triage_breakdown."""
        c = self.client
        r = c.post("/caller/session/start", json={"phone_number": "+254799888777"})
        self.assertEqual(r.status_code, 200)
        case_id = r.json()["case_id"]

        sub = c.post("/caller/session/submit", json={
            "case_id": case_id,
            "symptoms": ["fever", "headache", "chest pain"],
            "transcript_summary": "Patient reports fever and chest pain",
            "severity": 8,
            "duration": "2 days",
            "body_area": "chest",
        })
        self.assertEqual(sub.status_code, 200, sub.text)
        data = sub.json()
        self.assertIn("triage_level", data)
        self.assertIn("priority_score", data)
        self.assertGreater(data["priority_score"], 0)

    def test_fhir_bundle_endpoint(self):
        """GET /cases/{id}/fhir should return a FHIR Bundle."""
        c = self.client
        r = c.post("/caller/session/start", json={"phone_number": "+919876512345"})
        case_id = r.json()["case_id"]
        c.post("/caller/session/submit", json={
            "case_id": case_id,
            "symptoms": ["fever"],
            "severity": 4,
        })

        fhir = c.get(f"/cases/{case_id}/fhir")
        self.assertEqual(fhir.status_code, 200, fhir.text)
        bundle = fhir.json()
        self.assertEqual(bundle["resourceType"], "Bundle")
        self.assertEqual(bundle["type"], "collection")
        resource_types = [e["resource"]["resourceType"] for e in bundle["entry"]]
        self.assertIn("Patient", resource_types)
        self.assertIn("Encounter", resource_types)


if __name__ == "__main__":
    unittest.main(verbosity=2)
