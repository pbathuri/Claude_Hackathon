"""Unit tests for domain enums and state machine."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import unittest
from domain.enums import CaseStatus, validate_transition, TriageLevel, VALID_TRANSITIONS

class TestCaseStatusTransitions(unittest.TestCase):
    def test_valid_transitions(self):
        self.assertTrue(validate_transition(CaseStatus.CREATED, CaseStatus.INTAKE_COMPLETE))
        self.assertTrue(validate_transition(CaseStatus.INTAKE_COMPLETE, CaseStatus.PENDING_REVIEW))
        self.assertTrue(validate_transition(CaseStatus.PENDING_REVIEW, CaseStatus.ASSIGNED))
        self.assertTrue(validate_transition(CaseStatus.ASSIGNED, CaseStatus.IN_REVIEW))
        self.assertTrue(validate_transition(CaseStatus.IN_REVIEW, CaseStatus.RESPONDED))
        self.assertTrue(validate_transition(CaseStatus.RESPONDED, CaseStatus.CLOSED))

    def test_invalid_transitions(self):
        self.assertFalse(validate_transition(CaseStatus.CREATED, CaseStatus.RESPONDED))
        self.assertFalse(validate_transition(CaseStatus.CLOSED, CaseStatus.INTAKE_COMPLETE))
        self.assertFalse(validate_transition(CaseStatus.PENDING_REVIEW, CaseStatus.CLOSED))
        self.assertFalse(validate_transition(CaseStatus.CREATED, CaseStatus.CLOSED))

    def test_closed_is_terminal(self):
        self.assertEqual(VALID_TRANSITIONS[CaseStatus.CLOSED], set())

    def test_escalation_from_any_active_state(self):
        escalatable = [
            CaseStatus.INTAKE_COMPLETE, CaseStatus.PENDING_REVIEW,
            CaseStatus.ASSIGNED, CaseStatus.IN_REVIEW,
        ]
        for status in escalatable:
            self.assertTrue(
                validate_transition(status, CaseStatus.ESCALATED),
                f"{status} should be escalatable"
            )

    def test_all_statuses_have_transitions(self):
        for status in CaseStatus:
            self.assertIn(status, VALID_TRANSITIONS,
                         f"{status} missing from transition map")

class TestTriageLevel(unittest.TestCase):
    def test_all_levels_exist(self):
        for level in ["RED", "YELLOW", "GREEN", "BLACK", "UNKNOWN"]:
            self.assertEqual(TriageLevel(level), level)

if __name__ == "__main__":
    unittest.main()
