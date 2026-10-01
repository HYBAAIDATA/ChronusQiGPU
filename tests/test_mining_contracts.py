"""Tests for the Eight Formal Mining Contracts.

Every phase has a contract. Every contract has invariants. Every invariant is verified.
| # | Contract           | Phase       | Verification               |
|---|--------------------|-------------|----------------------------|
| 1 | Cold start         | Phase 1     | Cassini parity at root     |
| 2 | Precompute         | Phase 2     | 12 theorem checks          |
| 3 | Superposition hold | Phase 3     | Random sample 10% / cycle  |
| 4 | Submit             | Phase 4     | O(1) time measurement      |
| 5 | Steady state       | Phase 5     | Real-time telemetry        |
| 6 | Cool down          | Phase 6     | Post-shutdown verify       |
| 7 | Agent authority    | Continuous  | Audit trail                |
| 8 | Provenance         | Continuous  | Reconstruct any decision   |
"""

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PYTHIA_DIR = os.path.dirname(_THIS_DIR)
_INTEL_DIR = os.path.join(_PYTHIA_DIR, "Intelligence")

for p in (_PYTHIA_DIR, _INTEL_DIR, os.path.abspath("."), os.path.abspath("Intelligence")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

from Intelligence.agentic_mining import AgenticMiningWorkflow


class TestEightContracts:
    """Rigorous verification of all 8 formal mining contracts."""

    @pytest.fixture
    def active_workflow(self):
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        wf.phase2_precompute(count=32, n_anchor=7)
        return wf

    def test_contract_1_cold_start_cassini_root_parity(self):
        """Contract 1: Cold start verified by Cassini parity at root n=0."""
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        # Verify L_0^2 - 5*F_0^2 = 4*(-1)^0 = 4
        assert wf.geometric.verify_cassini_parity_integer(0) is True
        # Verify cold start provenance entry created
        entries = [r for r in wf.toe.provenance_ledger if r.contract_number == 1]
        assert len(entries) == 1
        assert entries[0].verified is True

    def test_contract_2_precompute_12_theorems(self, active_workflow):
        """Contract 2: Precompute verified by 12 theorem checks per candidate."""
        wf = active_workflow
        candidates = list(wf.manifold_bridge.md_memory.values())
        for cand in candidates:
            all_ok, theorem_map = wf.toe.verify_12_theorems_candidate(cand, n_anchor=7)
            assert all_ok is True
            assert len(theorem_map) == 12
            assert all(theorem_map.values()) is True

    def test_contract_3_superposition_hold_10_percent_sample(self, active_workflow):
        """Contract 3: Superposition hold verified by random 10% sampling per cycle."""
        wf = active_workflow
        passed, failed = wf.manifold_bridge.verify_random_sample_hold(sample_fraction=0.10)
        assert passed >= 1
        assert failed == 0

    def test_contract_4_submit_o1_lookup_timing(self, active_workflow):
        """Contract 4: Submit verified by O(1) time measurement (< 1.0 ms)."""
        wf = active_workflow
        first_nonce = next(iter(wf.manifold_bridge.md_memory.keys()))
        cand, elapsed_ms = wf.manifold_bridge.lookup_candidate_o1(first_nonce)
        assert cand is not None
        assert elapsed_ms < 1.0, f"Contract 4 O(1) violation: lookup took {elapsed_ms:.4f} ms"

    def test_contract_5_steady_state_real_time_telemetry(self, active_workflow):
        """Contract 5: Steady state verified by real-time telemetry adherence."""
        wf = active_workflow
        telemetry = wf.phase5_steady_state(cycles=2)
        assert len(telemetry) == 2
        for t in telemetry:
            # Real-data contract: channels are measured or explicitly None
            # with a basis label — never scripted scenario inputs.
            if t["hashrate_ehs"] is not None:
                assert t["hashrate_ehs"] > 0
                assert t["hashrate_basis"] in {"lucas_scaled_physical_rate", "measured"}
            else:
                assert t["hashrate_basis"] == "unmeasured"
            if t["thermal_c"] is not None:
                assert t["thermal_c"] < wf.thermal_throttle_c
            if t["power_w"] is not None:
                assert t["power_w"] <= wf.power_budget_w
            assert t["truth_class"] in {"measured", "observed"}

    def test_contract_6_cool_down_post_shutdown_verification(self, active_workflow):
        """Contract 6: Cool down verified by post-shutdown state verification."""
        wf = active_workflow
        wf.phase3_hold()
        wf.phase4_submit()
        wf.phase5_steady_state(cycles=1)
        report = wf.phase6_cool_down(force_safe_state=True)
        assert report["state_safe"] is True
        assert report["mining_active"] is False

    def test_contract_7_agent_authority_audit_trail(self, active_workflow):
        """Contract 7: Agent authority verified by autonomous decision audit trail."""
        wf = active_workflow
        wf.phase3_hold()
        wf.phase4_submit()
        wf.phase5_steady_state(cycles=1)

        # Inspect decisions from each of the 5 intelligences
        initiators = {r.initiating_intelligence for r in wf.toe.provenance_ledger}
        assert "TOE" in initiators
        assert "Geometric+Quantum" in initiators
        assert "Causal+Counterfactual" in initiators

    def test_contract_8_provenance_reconstruction(self, active_workflow):
        """Contract 8: Provenance verified by ability to reconstruct any decision."""
        wf = active_workflow
        wf.phase4_submit()
        ledger = wf.toe.provenance_ledger
        assert len(ledger) > 0
        for record in ledger:
            assert len(record.provenance_hash) == 64
            assert record.timestamp > 0
            assert record.action_type != ""
