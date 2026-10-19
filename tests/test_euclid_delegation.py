"""
EUCLID Governed Delegation — Comprehensive Test Suite
========================================================

Tests cover:
  - Organ Registry (register, unregister, candidates, deduplication)
  - Confidence Arbitration (all-bounds rule, single-failure veto, no-candidates)
  - Organ Factory (default and custom configuration)
  - World-Integration Gate (all-four passed, single-gate failure, null output)
  - Delegation Controller pipeline (full accept, veto at arbitration, veto at gate)
  - Chronicle integrity (append-only, predecessor-linked, hash verification)
  - CNS Health Report (healthy, degraded, integrity failure)
  - Fail-Closed Veto (every failure mode)
  - External validator wiring
  - Multi-organ candidate selection
  - Organ with no handler (blueprint mode)

Author: EUCLID Organism CNS
Status: IMPLEMENTED — INTERNAL
Date: 19 July 2026
"""

from __future__ import annotations

import hashlib
import json
import time
import unittest

# Unique sentinel for _make_result
def _sentinel_func():
    pass
_SENTINEL = _sentinel_func

from euclid_delegation import (
    ResearchDomain,
    ConfidenceBound,
    IntegrationGate,
    DelegationVerdict,
    OrganCapability,
    OrganHealth,
    OrganPermission,
    ConfidenceProfile,
    DelegationTask,
    DelegationResult,
    IntegrationAssessment,
    DelegationChronicle,
    Organ,
    OrganRegistry,
    ConfidenceArbiter,
    WorldIntegrationGate,
    DelegationController,
    create_organ,
    delegation_health_report,
)


# =============================================================================
# Organ Registry Tests
# =============================================================================


class TestOrganRegistration(unittest.TestCase):
    """Test organ registration, lookup, and deduplication."""

    def setUp(self):
        self.registry = OrganRegistry()

    def test_register_single_organ(self):
        """A single organ registers and is retrievable."""
        organ = create_organ("math_01", "Mathematical Explorer", ResearchDomain.MATHEMATICAL_ENGINE)
        self.registry.register(organ)
        self.assertEqual(self.registry.organ_count(), 1)
        retrieved = self.registry.get_organ("math_01")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.organ_id, "math_01")

    def test_register_deduplicates_by_id(self):
        """Registering the same organ_id twice deduplicates."""
        organ1 = create_organ("math_01", "Math V1", ResearchDomain.MATHEMATICAL_ENGINE)
        organ2 = create_organ("math_01", "Math V2", ResearchDomain.MATHEMATICAL_ENGINE)
        self.registry.register(organ1)
        self.registry.register(organ2)
        self.assertEqual(self.registry.organ_count(), 1)
        retrieved = self.registry.get_organ("math_01")
        self.assertEqual(retrieved.name, "Math V2")  # Latest wins

    def test_unregister_removes_organ(self):
        """Unregister removes an organ from both the ID index and domain index."""
        organ = create_organ("math_01", "Math", ResearchDomain.MATHEMATICAL_ENGINE)
        self.registry.register(organ)
        self.registry.unregister("math_01")
        self.assertEqual(self.registry.organ_count(), 0)
        self.assertIsNone(self.registry.get_organ("math_01"))
        self.assertEqual(self.registry.get_candidates(ResearchDomain.MATHEMATICAL_ENGINE), [])

    def test_unregister_nonexistent_is_noop(self):
        """Unregistering a non-existent organ is a no-op."""
        self.registry.unregister("nonexistent")
        self.assertEqual(self.registry.organ_count(), 0)

    def test_get_candidates_by_domain(self):
        """Candidates are correctly indexed by domain."""
        math_organ = create_organ("math_01", "Math", ResearchDomain.MATHEMATICAL_ENGINE)
        creative_organ = create_organ("creative_01", "Creative", ResearchDomain.CREATIVE_SUBSTRATE)
        self.registry.register(math_organ)
        self.registry.register(creative_organ)

        math_candidates = self.registry.get_candidates(ResearchDomain.MATHEMATICAL_ENGINE)
        self.assertEqual(len(math_candidates), 1)
        self.assertEqual(math_candidates[0].organ_id, "math_01")

        creative_candidates = self.registry.get_candidates(ResearchDomain.CREATIVE_SUBSTRATE)
        self.assertEqual(len(creative_candidates), 1)
        self.assertEqual(creative_candidates[0].organ_id, "creative_01")

    def test_list_all_organs(self):
        """list_all returns all registered organs."""
        for i in range(5):
            organ = create_organ(f"org_{i}", f"Organ {i}", ResearchDomain.COHERENCE_EVALUATOR)
            self.registry.register(organ)
        self.assertEqual(self.registry.organ_count(), 5)
        self.assertEqual(len(self.registry.list_all()), 5)


# =============================================================================
# Confidence Arbitration Tests
# =============================================================================


class TestConfidenceArbitration(unittest.TestCase):
    """Test ALL-bounds-must-clear arbitration rule."""

    def setUp(self):
        self.arbiter = ConfidenceArbiter(confidence_threshold=0.70, safety_threshold=0.70)

    def test_all_bounds_clear_selects_organ(self):
        """When all bounds clear, the organ is selected."""
        organ = create_organ(
            "math_01", "Math Explorer", ResearchDomain.MATHEMATICAL_ENGINE,
            capability_score=0.90, health_status="healthy", uptime_ratio=0.99, error_rate=0.01,
        )
        selected, profile, reason = self.arbiter.arbitrate([organ], ResearchDomain.MATHEMATICAL_ENGINE)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.organ_id, "math_01")
        self.assertTrue(profile.all_clear)
        self.assertIn("ACCEPTED", reason)

    def test_single_bound_failure_vetoes(self):
        """A single failing bound vetoes the candidate."""
        # Unhealthy organ
        organ = create_organ(
            "sick_01", "Sick Organ", ResearchDomain.EMERGENCE_ENGINE,
            capability_score=0.90, health_status="unavailable", uptime_ratio=0.0, error_rate=1.0,
        )
        selected, profile, reason = self.arbiter.arbitrate([organ], ResearchDomain.EMERGENCE_ENGINE)
        self.assertIsNone(selected)
        self.assertFalse(profile.all_clear)
        self.assertIn("healthy", profile.failing_bounds)
        self.assertIn("VETOED", reason)

    def test_multiple_bound_failures_vetoes(self):
        """Multiple failing bounds all reported."""
        organ = create_organ(
            "bad_01", "Bad Organ", ResearchDomain.WORLD_SYSTEM_FORECASTER,
            capability_score=0.30, health_status="unavailable", uptime_ratio=0.0, error_rate=1.0,
        )
        # Override to have empty allowed domains
        organ.permissions.allowed_domains = []
        selected, profile, reason = self.arbiter.arbitrate([organ], ResearchDomain.WORLD_SYSTEM_FORECASTER)
        self.assertIsNone(selected)
        self.assertFalse(profile.all_clear)
        self.assertGreaterEqual(len(profile.failing_bounds), 2)
        self.assertIn("VETOED", reason)

    def test_no_candidates_vetoes(self):
        """Empty candidate list vetoes with clear reason."""
        selected, profile, reason = self.arbiter.arbitrate([], ResearchDomain.MATHEMATICAL_ENGINE)
        self.assertIsNone(selected)
        self.assertFalse(profile.all_clear)
        self.assertIn("VETOED", reason)
        self.assertIn("No candidates", reason)

    def test_not_permitted_vetoes(self):
        """An organ not permitted for the domain is vetoed."""
        # Register the organ under the MATH domain but restrict permissions to CREATIVE
        organ = create_organ(
            "wrong_perms", "Wrong Perms", ResearchDomain.MATHEMATICAL_ENGINE,
            allowed_domains=[ResearchDomain.CREATIVE_SUBSTRATE],
        )
        # Now the organ IS in the MATH candidate list (because domain=MATHEMATICAL_ENGINE)
        # but its permissions only allow CREATIVE_SUBSTRATE
        selected, profile, reason = self.arbiter.arbitrate([organ], ResearchDomain.MATHEMATICAL_ENGINE)
        self.assertIsNone(selected)
        self.assertIn("permitted", profile.failing_bounds)

    def test_highest_scoring_among_all_clear_selected(self):
        """Among organs that all clear, the highest aggregate is selected."""
        organ_a = create_organ("a", "A", ResearchDomain.COHERENCE_EVALUATOR,
                               capability_score=0.75)
        organ_b = create_organ("b", "B", ResearchDomain.COHERENCE_EVALUATOR,
                               capability_score=0.95)
        selected, profile, reason = self.arbiter.arbitrate(
            [organ_a, organ_b], ResearchDomain.COHERENCE_EVALUATOR
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected.organ_id, "b")

    def test_below_threshold_not_confident_vetoes(self):
        """Capability below threshold means not confident → veto."""
        organ = create_organ("weak", "Weak", ResearchDomain.EMERGENCE_ENGINE,
                             capability_score=0.30)
        selected, profile, reason = self.arbiter.arbitrate([organ], ResearchDomain.EMERGENCE_ENGINE)
        self.assertIsNone(selected)
        self.assertIn("confident", profile.failing_bounds)


# =============================================================================
# World-Integration Gate Tests
# =============================================================================


class TestWorldIntegrationGate(unittest.TestCase):
    """Test the four-gate world-integration barrier."""

    def setUp(self):
        self.gate = WorldIntegrationGate()
        self.valid_profile = ConfidenceProfile(
            capable=True, healthy=True, permitted=True,
            confident=True, safe=True,
            capable_score=0.90, healthy_score=0.90,
            permitted_score=1.0, confident_score=0.81,
            safe_score=0.90,
        )

    def _make_result(self, organ_id="org_01", output=_SENTINEL, output_hash=_SENTINEL,
                     execution_time=0.001, profile=None):
        if profile is None:
            profile = self.valid_profile
        return DelegationResult(
            task_id="task_001",
            organ_id=organ_id,
            domain=ResearchDomain.COHERENCE_EVALUATOR,
            output=output if output is not _SENTINEL else {"result": "test"},
            execution_time=execution_time,
            confidence_profile=profile,
            produced_at=time.time(),
            output_hash=output_hash if output_hash is not _SENTINEL else hashlib.sha256(b"test").hexdigest(),
        )

    def test_all_four_gates_pass_internal_heuristics(self):
        """With valid result, all four internal-heuristic gates pass."""
        result = self._make_result()
        assessment = self.gate.assess(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.ACCEPTED)
        self.assertTrue(assessment.coherence_passed)
        self.assertTrue(assessment.truth_evidence_supplied)
        self.assertTrue(assessment.causal_attribution_supplied)
        self.assertTrue(assessment.feedback_processing_completed)
        self.assertIsNone(assessment.veto_reason)

    def test_null_output_fails_coherence(self):
        """Null output fails coherence gate."""
        result = self._make_result(output=None, output_hash="")
        assessment = self.gate.assess(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.VETOED)
        self.assertFalse(assessment.coherence_passed)
        self.assertIn("coherence", (assessment.veto_reason or "").lower())

    def test_missing_output_hash_fails_coherence(self):
        """Missing output hash fails coherence gate."""
        result = self._make_result(output_hash="")
        assessment = self.gate.assess(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.VETOED)
        self.assertFalse(assessment.coherence_passed)

    def test_failing_confidence_fails_truth_evidence(self):
        """Non-all-clear confidence profile fails truth evidence gate."""
        bad_profile = ConfidenceProfile(
            capable=False, healthy=True, permitted=True,
            confident=False, safe=False,
            capable_score=0.30, healthy_score=0.90,
            permitted_score=1.0, confident_score=0.27,
            safe_score=0.30,
        )
        result = self._make_result(profile=bad_profile)
        assessment = self.gate.assess(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.VETOED)
        self.assertFalse(assessment.truth_evidence_supplied)

    def test_missing_organ_id_fails_causal_attribution(self):
        """Missing organ_id fails causal attribution gate."""
        result = self._make_result(organ_id="")
        assessment = self.gate.assess(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.VETOED)
        self.assertFalse(assessment.causal_attribution_supplied)

    def test_zero_execution_time_fails_feedback(self):
        """Zero execution time fails feedback processing gate."""
        result = self._make_result(execution_time=0.0)
        assessment = self.gate.assess(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.VETOED)
        self.assertFalse(assessment.feedback_processing_completed)

    def test_external_validator_wired_and_called(self):
        """External validators are called when wired."""
        call_log = []

        def mock_coherence(result, world_hash):
            call_log.append(("coherence", result.task_id))
            return (True, "External coherence passed.")

        self.gate.wire_validators(coherence=mock_coherence)
        result = self._make_result()
        self.gate.assess(result)
        self.assertEqual(len(call_log), 1)
        self.assertEqual(call_log[0][0], "coherence")


# =============================================================================
# Delegation Controller Pipeline Tests
# =============================================================================


class TestDelegationController(unittest.TestCase):
    """Test the full governed delegation pipeline."""

    def setUp(self):
        self.controller = DelegationController()
        # Register organs for each domain
        self.controller.registry.register(
            create_organ("math_01", "Math Explorer", ResearchDomain.MATHEMATICAL_ENGINE,
                         capability_score=0.90,
                         handler=lambda payload: {"result": dict(payload)})
        )
        self.controller.registry.register(
            create_organ("creative_01", "Creative Substrate", ResearchDomain.CREATIVE_SUBSTRATE,
                         capability_score=0.90,
                         handler=lambda payload: {"result": dict(payload)})
        )
        self.controller.registry.register(
            create_organ("forecast_01", "World Forecaster", ResearchDomain.WORLD_SYSTEM_FORECASTER,
                         capability_score=0.90,
                         handler=lambda payload: {"result": dict(payload)})
        )
        self.controller.registry.register(
            create_organ("emergence_01", "Emergence Engine", ResearchDomain.EMERGENCE_ENGINE,
                         capability_score=0.90,
                         handler=lambda payload: {"result": dict(payload)})
        )
        self.controller.registry.register(
            create_organ("coherence_01", "Coherence Evaluator", ResearchDomain.COHERENCE_EVALUATOR,
                         capability_score=0.90,
                         handler=lambda payload: {"result": dict(payload)})
        )

    def test_full_pipeline_accept(self):
        """A valid delegation task is accepted through the full pipeline."""
        task = DelegationTask(
            task_id="task_001",
            domain=ResearchDomain.MATHEMATICAL_ENGINE,
            payload={"operation": "factor", "number": 15},
            origin="CNS_research_scheduler",
            created_at=time.time(),
        )
        result, assessment, chronicle = self.controller.delegate(task)
        self.assertIsNotNone(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.ACCEPTED)
        self.assertEqual(chronicle.task.task_id, "task_001")
        self.assertEqual(self.controller.chronicle_length, 1)
        # Integrity must verify
        self.assertTrue(self.controller.verify_integrity())

    def test_veto_on_no_candidates(self):
        """Delegating to a domain with no registered organs vetoes."""
        fresh = DelegationController()
        task = DelegationTask(
            task_id="task_002",
            domain=ResearchDomain.MATHEMATICAL_ENGINE,
            payload={"op": "test"},
            origin="CNS",
            created_at=time.time(),
        )
        result, assessment, chronicle = fresh.delegate(task)
        self.assertIsNone(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.VETOED)
        self.assertIn("No candidates", assessment.veto_reason or "")
        self.assertEqual(fresh.chronicle_length, 1)  # Veto is still recorded

    def test_veto_on_unhealthy_organ(self):
        """Delegating when the only candidate is unhealthy vetoes."""
        fresh = DelegationController()
        sick_organ = create_organ(
            "sick_01", "Sick", ResearchDomain.EMERGENCE_ENGINE,
            health_status="unavailable", uptime_ratio=0.0, error_rate=1.0,
        )
        fresh.registry.register(sick_organ)
        task = DelegationTask(
            task_id="task_003",
            domain=ResearchDomain.EMERGENCE_ENGINE,
            payload={"op": "test"},
            origin="CNS",
            created_at=time.time(),
        )
        result, assessment, chronicle = fresh.delegate(task)
        self.assertIsNone(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.VETOED)
        self.assertIn("healthy", assessment.veto_reason or "")

    def test_veto_on_not_permitted_organ(self):
        """Delegating when organ lacks domain permission vetoes."""
        fresh = DelegationController()
        # Register under MATH domain but restrict to CREATIVE permissions
        # The organ is indexed under MATH (its primary domain) but isn't permitted for MATH
        restricted = create_organ(
            "restricted", "Restricted", ResearchDomain.MATHEMATICAL_ENGINE,
            allowed_domains=[ResearchDomain.CREATIVE_SUBSTRATE],
        )
        fresh.registry.register(restricted)
        task = DelegationTask(
            task_id="task_004",
            domain=ResearchDomain.MATHEMATICAL_ENGINE,
            payload={"op": "test"},
            origin="CNS",
            created_at=time.time(),
        )
        result, assessment, chronicle = fresh.delegate(task)
        self.assertIsNone(result)
        self.assertIn("permitted", assessment.veto_reason or "")

    def test_chronicle_is_append_only(self):
        """Chronicle grows monotonically."""
        for i in range(5):
            task = DelegationTask(
                task_id=f"task_{i:03d}",
                domain=ResearchDomain.COHERENCE_EVALUATOR,
                payload={"iteration": i},
                origin="CNS_test",
                created_at=time.time(),
            )
            self.controller.delegate(task)
        self.assertEqual(self.controller.chronicle_length, 5)
        # Verify ordering
        for i, entry in enumerate(self.controller.chronicle):
            self.assertTrue(entry.event_id.endswith(f"{i + 1:06d}"))

    def test_chronicle_integrity_verification(self):
        """Integrity chain verifies correctly after multiple delegations."""
        for i in range(3):
            task = DelegationTask(
                task_id=f"integrity_{i}",
                domain=ResearchDomain.CREATIVE_SUBSTRATE,
                payload={"test": i},
                origin="CNS",
                created_at=time.time(),
            )
            self.controller.delegate(task)
        self.assertTrue(self.controller.verify_integrity())

    def test_chronicle_integrity_fails_on_tamper(self):
        """Tampered chronicle fails integrity verification."""
        task = DelegationTask(
            task_id="tamper_test",
            domain=ResearchDomain.WORLD_SYSTEM_FORECASTER,
            payload={"test": True},
            origin="CNS",
            created_at=time.time(),
        )
        self.controller.delegate(task)
        # Tamper with the chronicle
        self.controller._chronicle[0].event_hash = "tampered_hash"
        self.assertFalse(self.controller.verify_integrity())


# =============================================================================
# Organ Handler Tests
# =============================================================================


class TestOrganHandler(unittest.TestCase):
    """Test organ handler execution and blueprint mode."""

    def test_organ_with_handler_executes(self):
        """An organ with a handler executes and returns output."""
        def square_handler(payload):
            x = payload.get("x", 0)
            return {"result": x * x}

        organ = create_organ(
            "math_01", "Math", ResearchDomain.MATHEMATICAL_ENGINE,
            handler=square_handler,
        )
        controller = DelegationController()
        controller.registry.register(organ)
        task = DelegationTask(
            task_id="handler_test",
            domain=ResearchDomain.MATHEMATICAL_ENGINE,
            payload={"x": 7},
            origin="CNS",
            created_at=time.time(),
        )
        result, assessment, _ = controller.delegate(task)
        self.assertIsNotNone(result)
        self.assertEqual(result.output, {"result": 49})

    def test_organ_without_handler_blueprint_mode(self):
        """An organ without a handler is inventoried but cannot complete delegation."""
        organ = create_organ(
            "blueprint_01", "Blueprint", ResearchDomain.EMERGENCE_ENGINE,
            handler=None,
        )
        controller = DelegationController()
        controller.registry.register(organ)
        task = DelegationTask(
            task_id="blueprint_test",
            domain=ResearchDomain.EMERGENCE_ENGINE,
            payload={},
            origin="CNS",
            created_at=time.time(),
        )
        result, assessment, _ = controller.delegate(task)
        self.assertIsNone(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.VETOED)
        self.assertIn("no_handler", assessment.veto_reason)
        self.assertTrue(controller.verify_integrity())

    def test_organ_handler_error_is_captured(self):
        """Handler exceptions are captured, not propagated."""
        def failing_handler(payload):
            raise ValueError("Intentional test failure")

        organ = create_organ(
            "failing_01", "Failing", ResearchDomain.MATHEMATICAL_ENGINE,
            handler=failing_handler,
        )
        controller = DelegationController()
        controller.registry.register(organ)
        task = DelegationTask(
            task_id="error_test",
            domain=ResearchDomain.MATHEMATICAL_ENGINE,
            payload={},
            origin="CNS",
            created_at=time.time(),
        )
        result, assessment, _ = controller.delegate(task)
        self.assertIsNone(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.VETOED)
        self.assertIn("organ_execution_failed", assessment.veto_reason)
        self.assertTrue(controller.verify_integrity())


# =============================================================================
# Health Report Tests
# =============================================================================


class TestHealthReport(unittest.TestCase):
    """Test the CNS-compatible health report."""

    def test_healthy_with_organs(self):
        """Health report shows healthy when organs are registered and integrity ok."""
        controller = DelegationController()
        controller.registry.register(
            create_organ("org_01", "Healthy", ResearchDomain.COHERENCE_EVALUATOR)
        )
        report = delegation_health_report(controller)
        self.assertEqual(report["subsystem"], "delegation")
        self.assertEqual(report["status"], "healthy")
        self.assertEqual(report["total_organs"], 1)
        self.assertEqual(report["healthy_organs"], 1)
        self.assertTrue(report["integrity_chain_verified"])

    def test_degraded_with_no_organs(self):
        """Health report shows degraded with no organs."""
        controller = DelegationController()
        report = delegation_health_report(controller)
        self.assertEqual(report["status"], "degraded")
        self.assertEqual(report["healthy_organs"], 0)

    def test_event_counts_accurate(self):
        """Accepted and vetoed event counts are accurate."""
        controller = DelegationController()
        controller.registry.register(
            create_organ("org_01", "Test", ResearchDomain.COHERENCE_EVALUATOR,
                         handler=lambda payload: {"result": dict(payload)})
        )
        # Accepted
        task = DelegationTask(
            task_id="accept_001",
            domain=ResearchDomain.COHERENCE_EVALUATOR,
            payload={"test": True},
            origin="CNS",
            created_at=time.time(),
        )
        controller.delegate(task)

        # Vetoed — no candidates for math
        task2 = DelegationTask(
            task_id="veto_001",
            domain=ResearchDomain.MATHEMATICAL_ENGINE,
            payload={},
            origin="CNS",
            created_at=time.time(),
        )
        controller.delegate(task2)

        report = delegation_health_report(controller)
        self.assertEqual(report["total_events"], 2)
        self.assertGreaterEqual(report["accepted_events"], 1)
        self.assertGreaterEqual(report["vetoed_events"], 1)


# =============================================================================
# Fail-Closed Veto Tests
# =============================================================================


class TestFailClosedVeto(unittest.TestCase):
    """Every failure mode must result in VETO, never silent integration."""

    def test_veto_on_registry_empty(self):
        """Empty registry → veto (no silent fallback)."""
        controller = DelegationController()
        task = DelegationTask(
            task_id="v1", domain=ResearchDomain.MATHEMATICAL_ENGINE,
            payload={}, origin="CNS", created_at=time.time(),
        )
        result, assessment, _ = controller.delegate(task)
        self.assertIsNone(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.VETOED)

    def test_veto_on_unavailable_organ(self):
        """Unavailable organ → veto."""
        controller = DelegationController()
        controller.registry.register(
            create_organ("down", "Down", ResearchDomain.EMERGENCE_ENGINE,
                         health_status="unavailable", uptime_ratio=0.0, error_rate=1.0)
        )
        task = DelegationTask(
            task_id="v2", domain=ResearchDomain.EMERGENCE_ENGINE,
            payload={}, origin="CNS", created_at=time.time(),
        )
        result, assessment, _ = controller.delegate(task)
        self.assertIsNone(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.VETOED)

    def test_veto_on_low_capability(self):
        """Low capability → veto."""
        controller = DelegationController()
        controller.registry.register(
            create_organ("weak", "Weak", ResearchDomain.COHERENCE_EVALUATOR,
                         capability_score=0.10)
        )
        task = DelegationTask(
            task_id="v3", domain=ResearchDomain.COHERENCE_EVALUATOR,
            payload={}, origin="CNS", created_at=time.time(),
        )
        result, assessment, _ = controller.delegate(task)
        self.assertIsNone(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.VETOED)

    def test_veto_on_wrong_domain(self):
        """Wrong domain delegation → veto."""
        controller = DelegationController()
        controller.registry.register(
            create_organ("math_only", "Math Only", ResearchDomain.MATHEMATICAL_ENGINE,
                         allowed_domains=[ResearchDomain.MATHEMATICAL_ENGINE])
        )
        task = DelegationTask(
            task_id="v4", domain=ResearchDomain.WORLD_SYSTEM_FORECASTER,
            payload={}, origin="CNS", created_at=time.time(),
        )
        result, assessment, _ = controller.delegate(task)
        self.assertIsNone(result)
        self.assertEqual(assessment.verdict, DelegationVerdict.VETOED)


# =============================================================================
# Run
# =============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
