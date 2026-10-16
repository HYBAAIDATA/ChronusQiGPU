"""Execution refusal regressions; internal gate acceptance is not qualification."""
import unittest
from unittest.mock import patch

from euclid_delegation import (
    DelegationController, DelegationTask, DelegationVerdict, EvidenceSource,
    ResearchDomain, create_organ, delegation_health_report,
)


class TestExecutionRefusal(unittest.TestCase):
    def dispatch(self, handler, validators=False):
        controller = DelegationController()
        controller.registry.register(create_organ(
            "math", "Math", ResearchDomain.MATHEMATICAL_ENGINE, handler=handler,
        ))
        task = DelegationTask("task", ResearchDomain.MATHEMATICAL_ENGINE, {}, "test", 1.0)
        calls = []
        if validators:
            def accept(*args):
                calls.append(args)
                return True, "unit port; not independent certification"
            controller.integration_gate.wire_validators(accept, accept, accept, accept)
        with patch("time.perf_counter", side_effect=[1.0, 1.001]):
            result, assessment, _ = controller.delegate(task)
        return controller, result, assessment, calls

    def assert_refused(self, handler, reason, validators=False):
        controller, result, assessment, calls = self.dispatch(handler, validators)
        self.assertIsNone(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.VETOED)
        self.assertIn(reason, assessment.veto_reason)
        self.assertEqual(calls, [])
        self.assertTrue(controller.verify_integrity())
        report = delegation_health_report(controller)
        self.assertEqual(report["accepted_events"], 0)
        self.assertEqual(report["vetoed_events"], 1)
        for name in ("coherence_source", "truth_source", "causal_source", "feedback_source"):
            self.assertIs(getattr(assessment, name), EvidenceSource.NONE)

    def test_missing_handler_refused(self):
        self.assert_refused(None, "no_handler")

    def test_exception_refused(self):
        def broken(payload):
            raise ValueError("failure")
        self.assert_refused(broken, "organ_execution_failed")

    def test_noncallable_handler_refused(self):
        self.assert_refused(42, "organ_execution_failed")

    def test_missing_handler_cannot_be_approved_by_validators(self):
        self.assert_refused(None, "no_handler", validators=True)

    def test_exception_cannot_be_approved_by_validators(self):
        def broken(payload):
            raise RuntimeError("failure")
        self.assert_refused(broken, "organ_execution_failed", validators=True)

    def test_success_remains_available_and_internal(self):
        controller, result, assessment, _ = self.dispatch(lambda payload: {"result": 49})
        self.assertEqual(result.output, {"result": 49})
        self.assertEqual(assessment.verdict, DelegationVerdict.ACCEPTED)
        self.assertIs(assessment.truth_source, EvidenceSource.INTERNAL_HEURISTIC)
        self.assertTrue(controller.verify_integrity())

    def test_null_result_still_refused_by_default_gate(self):
        controller, result, assessment, _ = self.dispatch(lambda payload: None)
        self.assertIsNone(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.VETOED)
        self.assertTrue(controller.verify_integrity())

    def test_success_still_receives_all_external_ports(self):
        _, result, assessment, calls = self.dispatch(lambda payload: {"result": 49}, True)
        self.assertIsNotNone(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.ACCEPTED)
        self.assertEqual(len(calls), 4)


if __name__ == "__main__":
    unittest.main()
