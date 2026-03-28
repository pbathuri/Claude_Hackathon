"""Unit tests for FHIR R4 mapping adapters."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import unittest
from interoperability.fhir_mappers import (
    map_patient_to_fhir, map_encounter_to_fhir, map_symptom_to_observation,
    map_condition_to_fhir, map_consent_to_fhir, map_practitioner_to_fhir,
    map_audit_event,
)

class TestFHIRPatient(unittest.TestCase):
    def test_basic_patient(self):
        r = map_patient_to_fhir("p1", "NG", "en", "PT-1234")
        self.assertEqual(r["resourceType"], "Patient")
        self.assertEqual(r["id"], "p1")
        self.assertTrue(r["active"])

class TestFHIREncounter(unittest.TestCase):
    def test_encounter_status_mapping(self):
        r = map_encounter_to_fhir("c1", "p1", "pending_review")
        self.assertEqual(r["status"], "in-progress")
        
        r = map_encounter_to_fhir("c1", "p1", "closed")
        self.assertEqual(r["status"], "finished")

class TestFHIRObservation(unittest.TestCase):
    def test_symptom_observation(self):
        r = map_symptom_to_observation("c1", "p1", "fever", 7, "1F40")
        self.assertEqual(r["resourceType"], "Observation")
        self.assertEqual(r["valueInteger"], 7)

class TestFHIRCondition(unittest.TestCase):
    def test_condition_with_icd11(self):
        r = map_condition_to_fhir("c1", "p1", "Malaria", "1F40", "d1")
        self.assertEqual(r["code"]["text"], "Malaria")
        self.assertEqual(r["code"]["coding"][0]["code"], "1F40")

class TestFHIRConsent(unittest.TestCase):
    def test_accepted_consent(self):
        r = map_consent_to_fhir("p1", "data_processing", True)
        self.assertEqual(r["status"], "active")

class TestFHIRAuditEvent(unittest.TestCase):
    def test_audit(self):
        r = map_audit_event("create", "system", "c1")
        self.assertEqual(r["resourceType"], "AuditEvent")
        self.assertEqual(r["action"], "C")

if __name__ == "__main__":
    unittest.main()
