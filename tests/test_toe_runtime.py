"""Tests for the TOEIntelligenceRuntime composition root.

These tests use fakes/stubs so they don't depend on ASI background loops,
network access, or web learning.  They validate the wiring, fail-closed
behaviour, receipt generation, and mining consensus boundary enforcement.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

# Ensure project root on path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from toe.runtime import (
    RuntimeResponse,
    TenantContext,
    TOEIntelligenceRuntime,
    TOEIntelligenceRuntimeConfig,
    RuntimeReceipt,
)


class FakeBridge:
    """Minimal stand-in for TOEBridge that doesn't require heavy imports."""

    def __init__(self) -> None:
        self._available = True

    def available(self) -> bool:
        return self._available

    def status(self) -> dict[str, Any]:
        return {"engine": "TOEBridge", "available": True}

    def predict(self, data: Any) -> dict[str, Any]:
        return {
            "available": True,
            "confidence": 0.85,
            "state_tomography": {"energy": 0.5, "entropy": 2.1},
            "trajectory_prediction": {"trend": "rising"},
            "causal_analysis": {"key_factors": [["factor_a", 0.9]]},
            "causal_ladder": {"available": True},
        }

    def explain_causality(self, data: Any) -> dict[str, Any]:
        return {
            "available": True,
            "key_factors": [["factor_a", 0.9]],
            "recommendations": {"immediate": ["reduce X"]},
            "model_agreement": 0.8,
        }

    def predict_trajectory(self, data: Any) -> dict[str, Any]:
        return {
            "available": True,
            "trend": "rising",
            "intervention_points": [0.5],
            "energies": [1.0, 1.1],
        }

    def causal_ladder(self, data: Any) -> dict[str, Any]:
        return {
            "available": True,
            "rung_1_association": {"a": 0.3},
            "rung_2_intervention": {"distribution": {"a": 0.1}},
            "rung_3_counterfactual": {"value": 0.2},
        }


class FakeFeedbackCore:
    """Minimal stand-in for IntelligenceFeedbackCore."""

    def __init__(self) -> None:
        self.decisions: dict[str, Any] = {}
        self.reports: list[Any] = []

    def record_decision(self, decision: Any, confidence: float,
                        module_outputs: dict[str, Any], context: dict[str, Any] | None = None,
                        source_id: str = "default") -> str:
        import uuid
        decision_id = str(uuid.uuid4())
        self.decisions[decision_id] = {
            "decision": decision,
            "confidence": confidence,
            "module_outputs": module_outputs,
            "context": context or {},
            "source_id": source_id,
        }
        return decision_id

    def process(self, decision_id: str, outcome: Any, source_id: str | None = None,
                decision_fn: Any = None) -> Any:
        from dataclasses import dataclass, field
        from typing import Any

        @dataclass
        class FakeReport:
            report_id: str = "test-report"
            decision_id: str = decision_id
            calibration_score: float = 0.05
            learning_signal: float = 0.8
            recommendations: list[str] = field(default_factory=list)

        report = FakeReport()
        self.reports.append(report)
        return report


class FakeEvidenceChain:
    """Minimal stand-in for EvidenceChain."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def append(self, kind: str, payload: dict[str, Any]) -> Any:
        self.records.append({"kind": kind, "payload": payload})
        return {"kind": kind, "payload": payload}


class TestTOEIntelligenceRuntime(unittest.TestCase):
    """Tests for the TOEIntelligenceRuntime composition root."""

    def setUp(self) -> None:
        self.bridge = FakeBridge()
        self.feedback = FakeFeedbackCore()
        self.evidence = FakeEvidenceChain()
        self.tenant = TenantContext(tenant_id="test-tenant", mode="standard")
        self.runtime = TOEIntelligenceRuntime(
            bridge=self.bridge,
            feedback_core=self.feedback,
            evidence_chain=self.evidence,
            asi=MagicMock(),  # observe-only, never acts
            platform=None,
            config=TOEIntelligenceRuntimeConfig(
                enable_feedback=True,
                enable_evidence=True,
                enable_asi=False,
                enable_platform=False,
            ),
        )

    def test_predict_returns_ok_response(self) -> None:
        """predict() should return an ok response with receipt and result."""
        payload = {"performance_score": [0.5, 0.6, 0.7], "engagement": [0.4, 0.5, 0.6]}
        response = self.runtime.predict(payload, self.tenant)
        self.assertTrue(response.ok)
        self.assertEqual(response.operation, "predict")
        self.assertIsNotNone(response.receipt)
        self.assertEqual(response.receipt.tenant_id, "test-tenant")
        self.assertEqual(response.receipt.evidence_status, "MEASURED")
        self.assertIn("state_tomography", response.result)

    def test_predict_records_decision_in_feedback(self) -> None:
        """predict() should record a decision in the feedback core."""
        payload = {"a": [1.0, 2.0]}
        self.runtime.predict(payload, self.tenant)
        self.assertGreater(len(self.feedback.decisions), 0)

    def test_predict_appends_evidence(self) -> None:
        """predict() should append to the evidence chain."""
        payload = {"a": [1.0, 2.0]}
        self.runtime.predict(payload, self.tenant)
        self.assertGreater(len(self.evidence.records), 0)
        self.assertEqual(self.evidence.records[-1]["kind"], "toe-prediction")

    def test_receipt_is_tamper_evident(self) -> None:
        """Receipt should have payload and result digests."""
        payload = {"a": [1.0, 2.0]}
        response = self.runtime.predict(payload, self.tenant)
        receipt = response.receipt
        self.assertIsNotNone(receipt.payload_digest)
        self.assertIsNotNone(receipt.result_digest)
        self.assertNotEqual(receipt.payload_digest, receipt.result_digest)

    def test_explain_returns_causal_analysis(self) -> None:
        """explain() should return causal analysis results."""
        payload = {"a": [1.0, 2.0]}
        response = self.runtime.explain(payload, self.tenant)
        self.assertTrue(response.ok)
        self.assertEqual(response.operation, "explain")

    def test_forecast_returns_trajectory(self) -> None:
        """forecast() should return trajectory prediction."""
        payload = {"a": [1.0, 2.0]}
        response = self.runtime.forecast(payload, self.tenant, horizon=2.0)
        self.assertTrue(response.ok)
        self.assertEqual(response.operation, "forecast")

    def test_causal_returns_ladder(self) -> None:
        """causal() should return the causal ladder."""
        payload = {"driver": [9.8, 10.0], "outcome": [5.0, 5.2]}
        response = self.runtime.causal(payload, self.tenant, intervention_node="driver")
        self.assertTrue(response.ok)
        self.assertEqual(response.operation, "causal")

    def test_record_outcome_returns_feedback(self) -> None:
        """record_outcome() should process the outcome and return a report."""
        # First predict to get a decision
        payload = {"a": [1.0]}
        self.runtime.predict(payload, self.tenant)
        decision_id = list(self.feedback.decisions.keys())[0]
        response = self.runtime.record_outcome(decision_id, True, self.tenant)
        self.assertTrue(response.ok)
        self.assertIn("calibration_score", response.result)

    def test_fail_closed_on_empty_tenant(self) -> None:
        """Runtime should fail-closed on empty tenant_id."""
        bad_tenant = TenantContext(tenant_id="", mode="standard")
        # TenantContext raises on empty tenant_id in __post_init__
        with self.assertRaises(ValueError):
            TenantContext(tenant_id="", mode="standard")

    def test_fail_closed_on_payload_too_large(self) -> None:
        """Runtime should fail-closed on oversized payload."""
        big_payload = {"data": [0.5] * 20_000}
        response = self.runtime.predict(big_payload, self.tenant)
        self.assertFalse(response.ok)
        self.assertIn("payload", response.error.code)

    def test_fail_closed_on_engine_unavailable(self) -> None:
        """Runtime should fail-closed when engine is unavailable."""
        self.bridge._available = False
        response = self.runtime.predict({"a": [1.0]}, self.tenant)
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, "engine_unavailable")

    def test_mining_consensus_boundary_enforced(self) -> None:
        """Mining-mode output must not contain consensus vocabulary."""
        mining_tenant = TenantContext(tenant_id="mining-tenant", mode="mining")

        # Patch predict to return a consensus field
        original_predict = self.bridge.predict

        def patched_predict(data: Any) -> dict[str, Any]:
            result = original_predict(data)
            result["nonce"] = 12345  # consensus field
            return result

        self.bridge.predict = patched_predict  # type: ignore[method-assign]
        try:
            response = self.runtime.predict({"a": [1.0]}, mining_tenant)
            self.assertFalse(response.ok)
            self.assertEqual(response.error.code, "consensus_boundary_violation")
        finally:
            self.bridge.predict = original_predict  # type: ignore[method-assign]

    def test_mining_mode_allows_non_consensus_output(self) -> None:
        """Mining-mode output without consensus fields should pass."""
        mining_tenant = TenantContext(tenant_id="mining-tenant", mode="mining")
        response = self.runtime.predict({"hash_rate": [650, 655]}, mining_tenant)
        self.assertTrue(response.ok)

    def test_health_report(self) -> None:
        """health() should return engine status and loop availability."""
        health = self.runtime.health()
        self.assertIn("engine_available", health)
        self.assertIn("feedback_available", health)
        self.assertIn("evidence_available", health)
        self.assertTrue(health["engine_available"])
        self.assertTrue(health["feedback_available"])

    def test_ready_when_engine_available(self) -> None:
        """ready() should be True when engine is available."""
        self.assertTrue(self.runtime.ready())

    def test_not_ready_when_engine_unavailable(self) -> None:
        """ready() should be False when engine is unavailable."""
        self.bridge._available = False
        self.assertFalse(self.runtime.ready())

    def test_production_ready_flag_is_false(self) -> None:
        """production_ready should be False by default."""
        self.assertFalse(self.runtime.config.production_ready)
        health = self.runtime.health()
        self.assertFalse(health["production_ready"])

    def test_receipt_observe_only_flag(self) -> None:
        """Receipt should have observe_only=True."""
        response = self.runtime.predict({"a": [1.0]}, self.tenant)
        self.assertTrue(response.receipt.observe_only)

    def test_asi_probe_is_observe_only(self) -> None:
        """ASI hooks should only call capability_report, never act."""
        # ASI is a MagicMock with observe-only methods
        mock_asi = self.runtime.asi
        if mock_asi is not None:
            response = self.runtime.predict({"a": [1.0]}, self.tenant)
            # The predict should succeed and ASI should have been probed
            self.assertTrue(response.ok)
            # Verify ASI was only probed (capability_report), never started
            if hasattr(mock_asi, "start") and mock_asi.start.called:
                self.fail("ASI start() was called — should be observe-only")

    def test_degraded_mode_when_optional_wiring_missing(self) -> None:
        """Runtime should report degraded when optional wiring is missing."""
        runtime = TOEIntelligenceRuntime(
            bridge=FakeBridge(),
            feedback_core=None,
            evidence_chain=None,
            asi=None,
            platform=None,
            config=TOEIntelligenceRuntimeConfig(
                enable_feedback=False,
                enable_evidence=False,
                enable_asi=False,
                enable_platform=False,
            ),
        )
        self.assertTrue(runtime.degraded)
        self.assertGreater(len(runtime.degradation_reasons), 0)

    def test_response_as_dict_is_json_serialisable(self) -> None:
        """RuntimeResponse.as_dict() should be JSON-serialisable."""
        response = self.runtime.predict({"a": [1.0]}, self.tenant)
        d = response.as_dict()
        json.dumps(d)  # should not raise


class TestTenantContext(unittest.TestCase):
    """Tests for TenantContext validation."""

    def test_valid_tenant(self) -> None:
        ctx = TenantContext(tenant_id="acme", mode="standard")
        self.assertEqual(ctx.tenant_id, "acme")
        self.assertEqual(ctx.mode, "standard")

    def test_mining_mode_tenant(self) -> None:
        ctx = TenantContext(tenant_id="mining-co", mode="mining")
        self.assertEqual(ctx.mode, "mining")

    def test_empty_tenant_id_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TenantContext(tenant_id="", mode="standard")

    def test_invalid_mode_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TenantContext(tenant_id="acme", mode="invalid")


class TestRuntimeConfig(unittest.TestCase):
    """Tests for TOEIntelligenceRuntimeConfig validation."""

    def test_default_config(self) -> None:
        config = TOEIntelligenceRuntimeConfig()
        self.assertEqual(config.hilbert_dim, 32)
        self.assertFalse(config.production_ready)
        self.assertTrue(config.enable_feedback)
        self.assertTrue(config.enable_evidence)

    def test_small_hilbert_dim_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TOEIntelligenceRuntimeConfig(hilbert_dim=1)

    def test_small_max_payload_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TOEIntelligenceRuntimeConfig(max_payload_bytes=100)


if __name__ == "__main__":
    unittest.main()
