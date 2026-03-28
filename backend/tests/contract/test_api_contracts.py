"""Contract tests verifying API response shapes match portal expectations."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import unittest
import httpx

BASE = os.environ.get("TEST_API_URL", "http://localhost:8000")

class TestCaseContract(unittest.TestCase):
    """Verify /cases/patient-cases returns the shape doctor-portal expects."""
    
    def setUp(self):
        self.client = httpx.Client(base_url=BASE, timeout=10)
        try:
            self.client.get("/health-check")
        except Exception:
            self.skipTest("Backend not running")
    
    def test_patient_cases_shape(self):
        r = self.client.get("/cases/patient-cases")
        self.assertEqual(r.status_code, 200)
        cases = r.json()
        self.assertIsInstance(cases, list)
        if cases:
            c = cases[0]
            required = ["caseId", "patientAlias", "country", "urgency", "priorityScore"]
            for field in required:
                self.assertIn(field, c, f"Missing field: {field}")

class TestKGContract(unittest.TestCase):
    def setUp(self):
        self.client = httpx.Client(base_url=BASE, timeout=10)
        try:
            self.client.get("/health-check")
        except Exception:
            self.skipTest("Backend not running")
    
    def test_kg_stats_shape(self):
        r = self.client.get("/kg/stats")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("total_nodes", d)
        self.assertIn("total_edges", d)
    
    def test_kg_query_shape(self):
        r = self.client.post("/kg/query", json={"symptoms": ["fever"]})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("activated_conditions", d)
        self.assertIn("suggested_questions", d)

class TestDoctorContract(unittest.TestCase):
    def setUp(self):
        self.client = httpx.Client(base_url=BASE, timeout=10)
        try:
            self.client.get("/health-check")
        except Exception:
            self.skipTest("Backend not running")
    
    def test_doctor_list_shape(self):
        r = self.client.get("/doctors/")
        self.assertEqual(r.status_code, 200)
        docs = r.json()
        self.assertIsInstance(docs, list)

if __name__ == "__main__":
    unittest.main()
