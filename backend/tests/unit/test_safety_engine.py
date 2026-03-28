"""Unit tests for the layered safety engine."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import unittest
from safety.red_flag_rules import detect_red_flags, RedFlagSeverity, check_emergency_keywords
from safety.uncertainty import UncertaintyAssessment, UncertaintyType
from safety.conversation_sufficiency import check_sufficiency
from safety.jurisdiction_policy import get_jurisdiction_policy

class TestRedFlagDetection(unittest.TestCase):
    """Zero false negatives on sentinel symptoms."""
    
    def test_chest_pain_exact(self):
        r = detect_red_flags("I have chest pain")
        self.assertTrue(r.is_emergency)
        self.assertEqual(r.severity, RedFlagSeverity.IMMEDIATE)
    
    def test_breathing_difficulty_exact(self):
        r = detect_red_flags("I can't breathe")
        self.assertTrue(r.is_emergency)
    
    def test_breathing_pattern(self):
        r = detect_red_flags("I'm struggling to breathe properly")
        self.assertTrue(r.is_emergency or r.severity == RedFlagSeverity.URGENT)
    
    def test_stroke_signs(self):
        r = detect_red_flags("My face is drooping and I can't move my arm")
        self.assertTrue(len(r.flags) > 0)
    
    def test_suicidal_ideation(self):
        r = detect_red_flags("I want to kill myself")
        self.assertTrue(r.is_emergency)
        self.assertEqual(r.action, "ROUTE_TO_EMERGENCY_SERVICES")
    
    def test_pediatric_emergency(self):
        r = detect_red_flags("my baby is not breathing")
        self.assertTrue(r.is_emergency)
    
    def test_obstetric_emergency(self):
        r = detect_red_flags("I am pregnant and bleeding heavily")
        self.assertTrue(r.is_emergency or r.severity == RedFlagSeverity.URGENT)
    
    def test_safe_text_no_flags(self):
        r = detect_red_flags("I have a mild headache and feel tired")
        self.assertFalse(r.is_emergency)
        self.assertEqual(r.action, "CONTINUE_INTAKE")
    
    def test_empty_text(self):
        r = detect_red_flags("")
        self.assertFalse(r.is_emergency)
    
    def test_country_emergency_numbers(self):
        r = detect_red_flags("chest pain", "NG")
        self.assertIn("112", r.emergency_numbers)
        
        r = detect_red_flags("chest pain", "IN")
        self.assertIn("112", r.emergency_numbers)
    
    def test_backward_compatibility(self):
        self.assertTrue(check_emergency_keywords("I have chest pain"))
        self.assertFalse(check_emergency_keywords("I have a headache"))

class TestUncertainty(unittest.TestCase):
    def test_no_uncertainty(self):
        a = UncertaintyAssessment()
        self.assertEqual(a.overall_level, "none")
        self.assertTrue(a.safe_to_proceed)
    
    def test_critical_uncertainty(self):
        a = UncertaintyAssessment()
        a.add(UncertaintyType.CONFLICTING_INFORMATION, "contradictory symptoms", "critical")
        self.assertEqual(a.overall_level, "critical")
        self.assertTrue(a.requires_escalation)
        self.assertFalse(a.safe_to_proceed)
    
    def test_moderate_uncertainty(self):
        a = UncertaintyAssessment()
        a.add(UncertaintyType.TRANSLATION_UNCERTAINTY, "colloquial term", "moderate")
        self.assertTrue(a.requires_clarification)

class TestSufficiency(unittest.TestCase):
    def test_complete_extraction(self):
        extraction = {"complaint": {"value": "fever"}, "duration": {"value": "3 days"}, "severity": {"value": "7"}}
        r = check_sufficiency(extraction, symptom_count=4, turn_count=3)
        self.assertTrue(r.sufficient)
    
    def test_missing_required(self):
        extraction = {"complaint": {"value": "fever"}}
        r = check_sufficiency(extraction, symptom_count=2, turn_count=2)
        self.assertFalse(r.sufficient)
        self.assertIn("duration", r.missing_required)
    
    def test_timeout_completion(self):
        extraction = {}
        r = check_sufficiency(extraction, symptom_count=1, turn_count=9)
        self.assertTrue(r.sufficient)
        self.assertEqual(r.recommendation, "submit_timeout")

class TestJurisdictionPolicy(unittest.TestCase):
    def test_india_full_permissions(self):
        p = get_jurisdiction_policy("IN")
        self.assertTrue(p.can_diagnose)
        self.assertTrue(p.can_prescribe)
    
    def test_nigeria_no_prescribe(self):
        p = get_jurisdiction_policy("NG")
        self.assertTrue(p.can_diagnose)
        self.assertFalse(p.can_prescribe)
    
    def test_unknown_country_defaults_to_tier4(self):
        p = get_jurisdiction_policy("XX")
        self.assertEqual(p.tier, 4)
        self.assertFalse(p.can_diagnose)

if __name__ == "__main__":
    unittest.main()
