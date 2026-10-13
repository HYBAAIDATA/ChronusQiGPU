"""Tests for independent task verification and acceptance criteria in RepositoryIntelligenceExecutor."""
from __future__ import annotations

import unittest
from pathlib import Path

from euclid.cognition.production import (
    RepositoryIntelligenceExecutor,
    TaskVerificationVerdict,
    verify_task_evidence,
)


class StubEngineer:
    def __init__(self, evidence: dict):
        self.evidence = evidence

    def ask(self, action: str) -> dict:
        return {"routes": ["stub-route"], "evidence": self.evidence, "task_id": "task-stub-1"}


class TaskVerificationTests(unittest.TestCase):
    def test_unavailable_tests_yields_unavailable(self) -> None:
        evidence = {"focused_tests": {"available": False}}
        goal_met, verdict = verify_task_evidence("test", {"action": "test"}, evidence)
        self.assertFalse(goal_met)
        self.assertEqual(verdict, TaskVerificationVerdict.UNAVAILABLE)

        executor = RepositoryIntelligenceExecutor(StubEngineer(evidence))
        result = executor.execute("test", {"action": "test"})
        self.assertFalse(result["goal_met"])
        self.assertEqual(result["verification_verdict"], TaskVerificationVerdict.UNAVAILABLE.value)

    def test_failed_tests_yields_verified_failure(self) -> None:
        evidence = {"focused_tests": {"returncode": 1, "output": "assertion error"}}
        goal_met, verdict = verify_task_evidence("test", {"action": "test"}, evidence)
        self.assertFalse(goal_met)
        self.assertEqual(verdict, TaskVerificationVerdict.VERIFIED_FAILURE)

        executor = RepositoryIntelligenceExecutor(StubEngineer(evidence))
        result = executor.execute("test", {"action": "test"})
        self.assertFalse(result["goal_met"])
        self.assertEqual(result["verification_verdict"], TaskVerificationVerdict.VERIFIED_FAILURE.value)

    def test_passing_import_audit_does_not_mask_failed_tests(self) -> None:
        evidence = {
            "import_audit": {"finding_count": 0},
            "focused_tests": {"returncode": 1},
        }
        goal_met, verdict = verify_task_evidence("test", {"action": "test"}, evidence)
        self.assertFalse(goal_met)
        self.assertEqual(verdict, TaskVerificationVerdict.VERIFIED_FAILURE)

        executor = RepositoryIntelligenceExecutor(StubEngineer(evidence))
        result = executor.execute("test", {"action": "test"})
        self.assertFalse(result["goal_met"])
        self.assertEqual(result["verification_verdict"], TaskVerificationVerdict.VERIFIED_FAILURE.value)

    def test_passing_tests_yields_verified_success(self) -> None:
        evidence = {"focused_tests": {"returncode": 0, "passed": 10}}
        goal_met, verdict = verify_task_evidence("test", {"action": "test"}, evidence)
        self.assertTrue(goal_met)
        self.assertEqual(verdict, TaskVerificationVerdict.VERIFIED_SUCCESS)

        executor = RepositoryIntelligenceExecutor(StubEngineer(evidence))
        result = executor.execute("test", {"action": "test"})
        self.assertTrue(result["goal_met"])
        self.assertEqual(result["verification_verdict"], TaskVerificationVerdict.VERIFIED_SUCCESS.value)

    def test_import_audit_satisfies_audit_task_only(self) -> None:
        evidence = {"import_audit": {"finding_count": 0}}
        # Audit goal: satisfies
        goal_met_audit, verdict_audit = verify_task_evidence(
            "audit", {"goal": "verify import audit clean"}, evidence
        )
        self.assertTrue(goal_met_audit)
        self.assertEqual(verdict_audit, TaskVerificationVerdict.VERIFIED_SUCCESS)

        # Unrelated test goal: does NOT satisfy
        goal_met_test, verdict_test = verify_task_evidence(
            "test", {"goal": "run pytest suite"}, evidence
        )
        self.assertFalse(goal_met_test)
        self.assertEqual(verdict_test, TaskVerificationVerdict.UNVERIFIED)

    def test_empty_evidence_yields_unavailable(self) -> None:
        goal_met, verdict = verify_task_evidence("test", {}, {})
        self.assertFalse(goal_met)
        self.assertEqual(verdict, TaskVerificationVerdict.UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
