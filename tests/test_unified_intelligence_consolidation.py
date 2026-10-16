"""Tests for EUCLID Unified Intelligence Engine consolidation.

Verifies:
1. Canonical import surfaces (`euclid.intelligence` and `Intelligence`).
2. Domain organization (`physics`, `cognition`, `gatekeeper`).
3. Single unified gatekeeper dispatch and verified rollback.
4. Backward-compatible deprecation shims (`hyba_toe_intelligence`, `hyba_euclid_intelligence`).
"""

import time
import warnings
import unittest

from euclid.capabilities.empirical_state_bridge import (
    EmpiricalStateBridge,
    EmpiricalStateController,
    StateTransitionRequest,
)


class TestUnifiedIntelligenceConsolidation(unittest.TestCase):
    def test_canonical_euclid_intelligence_exports(self):
        """Verify euclid.intelligence exports physics, cognition, and gatekeeper subdomains."""
        import euclid.intelligence as intel
        self.assertTrue(hasattr(intel, "physics"))
        self.assertTrue(hasattr(intel, "cognition"))
        self.assertTrue(hasattr(intel, "gatekeeper"))
        self.assertTrue(hasattr(intel, "UnifiedIntelligenceGatekeeper"))

    def test_canonical_intelligence_exports(self):
        """Verify top-level Intelligence exports physics, cognition, and gatekeeper subdomains."""
        import Intelligence
        self.assertTrue(hasattr(Intelligence, "physics"))
        self.assertTrue(hasattr(Intelligence, "cognition"))
        self.assertTrue(hasattr(Intelligence, "gatekeeper"))
        self.assertTrue(hasattr(Intelligence, "UnifiedIntelligenceGatekeeper"))

    def test_physics_subdomain_reachability(self):
        """Verify physics subdomain organizes quantum, Lucas, and physical simulation."""
        from euclid.intelligence import physics
        self.assertTrue(hasattr(physics, "first_principles_quantum"))
        self.assertTrue(hasattr(physics, "quantum_algorithms"))
        self.assertTrue(hasattr(physics, "lucas_scales"))
        self.assertTrue(hasattr(physics, "poincare_cassini_search"))
        self.assertTrue(hasattr(physics, "mining_native"))

    def test_cognition_subdomain_reachability(self):
        """Verify cognition subdomain organizes empirical state, proof tracking, and review."""
        from euclid.intelligence import cognition
        self.assertTrue(hasattr(cognition, "EmpiricalStateController"))
        self.assertTrue(hasattr(cognition, "EmpiricalStateBridge"))
        self.assertTrue(hasattr(cognition, "StateTransitionRequest"))
        self.assertTrue(hasattr(cognition, "MathematicalProofTracker"))
        self.assertTrue(hasattr(cognition, "register_proof_capability"))
        self.assertTrue(hasattr(cognition, "repository_review"))

    def test_unified_gatekeeper_dispatch_and_audit(self):
        """Verify single gatekeeper handles state transition with pre-audit and receipt."""
        from euclid.intelligence.gatekeeper import (
            UnifiedIntelligenceGatekeeper,
            StateTransitionRequest,
        )
        gatekeeper = UnifiedIntelligenceGatekeeper()

        req = StateTransitionRequest(
            capability_id="host:capability:empirical_state_controller",
            caller_id="operator:verifier:001",
            transition_type="UPDATE_RELIABILITY",
            state_payload={"domain": "atomic", "weight": 0.95},
            deadline_epoch=time.time() + 60.0,
            max_budget=100,
            operator_token="valid_operator_token_12345",
        )
        ok, receipt, msg = gatekeeper.dispatch_state_transition(req)
        self.assertTrue(ok)
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.status, "COMMITTED")
        self.assertEqual(gatekeeper.state_bridge.controller.state["reliability_weights"]["atomic"], 0.95)

        trail = gatekeeper.get_audit_trail()
        self.assertEqual(len(trail), 1)
        self.assertEqual(trail[0]["type"], "STATE_TRANSITION")
        self.assertEqual(trail[0]["receipt_id"], receipt.receipt_id)

    def test_unified_gatekeeper_refusal_and_budget(self):
        """Verify unified gatekeeper enforces fail-closed refusal and budget limits."""
        from euclid.intelligence.gatekeeper import (
            UnifiedIntelligenceGatekeeper,
            StateTransitionRequest,
        )
        gatekeeper = UnifiedIntelligenceGatekeeper()

        # Unapproved capability refusal
        bad_req = StateTransitionRequest(
            capability_id="unapproved:arbitrary:target",
            caller_id="attacker",
            transition_type="BYPASS",
            state_payload={},
            deadline_epoch=time.time() + 10.0,
            max_budget=10,
            operator_token="token_with_length_16_bytes",
        )
        ok, _, msg = gatekeeper.dispatch_state_transition(bad_req)
        self.assertFalse(ok)
        self.assertIn("FORBIDDEN_CAPABILITY", msg)

        # Budget exhaustion guard
        zero_budget = StateTransitionRequest(
            capability_id="host:capability:empirical_state_controller",
            caller_id="operator:001",
            transition_type="UPDATE_RELIABILITY",
            state_payload={"domain": "atomic", "weight": 0.10},
            deadline_epoch=time.time() + 10.0,
            max_budget=0,
            operator_token="token_with_length_16_bytes",
        )
        ok, _, msg = gatekeeper.dispatch_state_transition(zero_budget)
        self.assertFalse(ok)
        self.assertIn("BUDGET_EXHAUSTED", msg)
        # Verify no state mutation on refusal
        self.assertNotEqual(
            gatekeeper.state_bridge.controller.state["reliability_weights"]["atomic"],
            0.10,
        )

    def test_unified_gatekeeper_rollback_on_failure(self):
        """Verify verified rollback port restores pre-execution state on exception."""
        from euclid.intelligence.gatekeeper import (
            UnifiedIntelligenceGatekeeper,
            StateTransitionRequest,
        )
        gatekeeper = UnifiedIntelligenceGatekeeper()
        initial_weights = dict(gatekeeper.state_bridge.controller.state["reliability_weights"])

        failing_req = StateTransitionRequest(
            capability_id="host:capability:empirical_state_controller",
            caller_id="operator:001",
            transition_type="INVALID_TYPE_TRIGGERING_EXCEPTION",
            state_payload={},
            deadline_epoch=time.time() + 10.0,
            max_budget=10,
            operator_token="token_with_length_16_bytes",
        )
        ok, _, msg = gatekeeper.dispatch_state_transition(failing_req)
        self.assertFalse(ok)
        self.assertIn("EXECUTION_FAILED_ROLLED_BACK", msg)
        self.assertEqual(
            gatekeeper.state_bridge.controller.state["reliability_weights"],
            initial_weights,
        )

    def test_hyba_toe_intelligence_deprecation_shim(self):
        """Verify hyba_toe_intelligence emits deprecation warning and routes to physics."""
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            import hyba_toe_intelligence as toe_shim

            # Verify deprecation warning was emitted
            dep_warnings = [w for w in recorded if issubclass(w.category, DeprecationWarning)]
            self.assertTrue(len(dep_warnings) >= 1)
            self.assertIn("hyba_toe_intelligence is deprecated", str(dep_warnings[0].message))

            # Verify symbols are reachable through the shim
            self.assertTrue(hasattr(toe_shim, "physics"))
            self.assertTrue(hasattr(toe_shim.physics, "quantum_algorithms"))

    def test_hyba_euclid_intelligence_deprecation_shim(self):
        """Verify hyba_euclid_intelligence emits deprecation warning and routes to euclid.intelligence."""
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            import hyba_euclid_intelligence as euclid_shim

            dep_warnings = [w for w in recorded if issubclass(w.category, DeprecationWarning)]
            self.assertTrue(len(dep_warnings) >= 1)
            self.assertIn("hyba_euclid_intelligence is deprecated", str(dep_warnings[0].message))

            self.assertTrue(hasattr(euclid_shim, "intelligence"))
            self.assertTrue(hasattr(euclid_shim.intelligence, "cognition"))
            self.assertTrue(hasattr(euclid_shim.intelligence, "gatekeeper"))


if __name__ == "__main__":
    unittest.main()
