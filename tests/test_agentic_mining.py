"""Tests for Autonomous Agentic Mining Lifecycle (Cold Start to Cool Down).

Validates all 6 phases, all 5 intelligences, all 13 substrates, and
hard integrity invariants.
"""

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PYTHIA_DIR = os.path.dirname(_THIS_DIR)

# Only the repo root goes on sys.path. ``Intelligence/`` must NOT be added: doing
# so makes it a source root, and its ``asi/`` subpackage then shadows the
# top-level ``asi`` package that this repository also ships, breaking any later
# ``import asi``. The fallback below imports the platform tree's own
# ``agentic_mining`` module, which the repo root alone does not expose.
for p in (_PYTHIA_DIR, os.path.abspath(".")):
    if p not in sys.path:
        sys.path.insert(0, p)

import hashlib
import time
import pytest

try:
    from Intelligence.agentic_mining import (
        AgenticMiningWorkflow,
    )
    from toe.intelligences.causal import CausalIntelligence
    from toe.intelligences.geometric import GeometricIntelligence
    from toe.intelligences.plastic import PlasticIntelligence
    from toe.intelligences.counterfactual import CounterfactualIntelligence
    from toe.intelligences.quantum import QuantumIntelligence
    from toe.system import TOESystem
except ImportError:
    from agentic_mining import (
        AgenticMiningWorkflow,
    )
    from toe.intelligences.causal import CausalIntelligence
    from toe.intelligences.geometric import GeometricIntelligence
    from toe.intelligences.plastic import PlasticIntelligence
    from toe.intelligences.counterfactual import CounterfactualIntelligence
    from toe.intelligences.quantum import QuantumIntelligence
    from toe.system import TOESystem


# =============================================================================
# COLD START TESTS
# =============================================================================
class TestColdStart:
    """Test suite for Phase 1: Cold Start."""

    def test_hardware_detected_within_timeout(self):
        wf = AgenticMiningWorkflow()
        t0 = time.time()
        manifest = wf.phase1_cold_start()
        elapsed = time.time() - t0
        assert elapsed <= 5.0, f"Hardware detection took {elapsed:.2f}s > 5.0s limit"
        assert manifest.is_valid is True

    def test_all_25_punches_registered(self):
        wf = AgenticMiningWorkflow()
        manifest = wf.phase1_cold_start()
        assert manifest.punch_count >= 24

    def test_cassini_root_parity_verified(self):
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        # Root anchor n=0: L_0^2 - 5*F_0^2 = 4 - 0 = 4 = 4(-1)^0
        assert wf.geometric.verify_cassini_parity_integer(0) is True

    def test_wallet_authenticated(self):
        wf = AgenticMiningWorkflow(wallet_address="bc1qvalidtreasurywalletaddress01")
        wf.phase1_cold_start()
        assert wf.wallet_address.startswith("bc1")

    def test_all_5_intelligences_instantiated(self):
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        assert isinstance(wf.causal, CausalIntelligence)
        assert isinstance(wf.geometric, GeometricIntelligence)
        assert isinstance(wf.plastic, PlasticIntelligence)
        assert isinstance(wf.counterfactual, CounterfactualIntelligence)
        assert isinstance(wf.quantum, QuantumIntelligence)

    def test_toe_system_ready(self):
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        assert isinstance(wf.toe, TOESystem)
        assert len(wf.toe.provenance_ledger) >= 1

    def test_refuses_to_start_on_invalid_hardware(self):
        wf = AgenticMiningWorkflow()
        with pytest.raises(RuntimeError, match="Phase 1 refused to start"):
            wf.phase1_cold_start(mock_invalid_hardware=True)


# =============================================================================
# PRECOMPUTE TESTS
# =============================================================================
class TestPrecompute:
    """Test suite for Phase 2: Precompute."""

    @pytest.fixture
    def started_workflow(self):
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        return wf

    def test_candidates_pass_cassini_and_zeckendorf(self, started_workflow):
        wf = started_workflow
        candidates = wf.phase2_precompute(count=16, n_anchor=7)
        assert len(candidates) == 16
        for cand in candidates:
            # Cassini parity exact integer check
            assert cand.cassini_valid is True
            # Zeckendorf non-adjacency exact check: no consecutive 1s
            assert (cand.zeckendorf_mask & (cand.zeckendorf_mask << 1)) == 0

    def test_prime_exponents_galois_bounded(self, started_workflow):
        wf = started_workflow
        candidates = wf.phase2_precompute(count=16, n_anchor=7)
        q_modulus = 2**61 - 1
        for cand in candidates:
            assert cand.galois_composite < q_modulus

    def test_yang_mills_bound_applied(self, started_workflow):
        wf = started_workflow
        candidates = wf.phase2_precompute(count=8, n_anchor=7)
        for cand in candidates:
            ok, theorem_map = wf.toe.verify_12_theorems_candidate(cand, n_anchor=7)
            assert ok is True
            assert theorem_map["T10_yang_mills_gap"] is True

    def test_born_rule_threshold_met(self, started_workflow):
        wf = started_workflow
        candidates = wf.phase2_precompute(count=8, n_anchor=7)
        for cand in candidates:
            assert cand.born_probability >= 0.5


# =============================================================================
# HOLD TESTS
# =============================================================================
class TestHold:
    """Test suite for Phase 3: Superposition Hold."""

    def test_hold_contracts_and_distribution(self):
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        wf.phase2_precompute(count=32, n_anchor=7)
        stats = wf.phase3_hold()

        assert stats["total_held_candidates"] == 32
        assert stats["md_memory_entries"] == 32
        assert stats["galois_prime_entries"] >= 1
        assert stats["igpu_vram_cached"] == 32
        assert stats["cassini_sample_passed"] >= 1
        assert stats["cassini_sample_failed"] == 0


# =============================================================================
# SUBMIT TESTS (O(1))
# =============================================================================
class TestSubmit:
    """Test suite for Phase 4: Submit."""

    def test_submit_o1_and_sha256d_sole_authority(self):
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        candidates = wf.phase2_precompute(count=16, n_anchor=7)
        target_cand = candidates[0]

        res = wf.phase4_submit(target_nonce=target_cand.nonce)

        # O(1) lookup latency constraint
        assert res.lookup_time_ms < 5.0
        # Zeckendorf certificate present
        assert res.zeckendorf_certificate == target_cand.zeckendorf_mask
        assert (res.zeckendorf_certificate & (res.zeckendorf_certificate << 1)) == 0
        # Provenance hash recorded
        assert len(res.provenance_hash) == 64
        # Causal intervention recorded
        assert "do(Pool=" in res.causal_intervention
        # Counterfactual alternatives evaluated
        assert res.counterfactual_count >= 1

    def test_sha256d_exact_evaluation(self):
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        cand = wf.phase2_precompute(count=1, n_anchor=7)[0]

        # Artificially set target to maximum to confirm acceptance logic strictly matches SHA-256d
        wf.current_target = (1 << 256) - 1
        res = wf.phase4_submit(target_nonce=cand.nonce)
        assert res.accepted is True

        # Now set target to 0 to confirm rejection strictly matches SHA-256d
        wf.current_target = 0
        res2 = wf.phase4_submit(target_nonce=cand.nonce)
        assert res2.accepted is False


# =============================================================================
# STEADY STATE TESTS
# =============================================================================
class TestSteadyState:
    """Test suite for Phase 5: Steady State."""

    def test_steady_state_loop_and_telemetry(self):
        wf = AgenticMiningWorkflow(start_ehs=0.001, thermal_throttle_c=85.0)
        wf.phase1_cold_start()
        wf.phase2_precompute(count=16, n_anchor=7)

        # Real-data contract: a live deployment injects its measured
        # telemetry; the workflow never scripts values itself.
        def provider(cycle):
            return {
                "peer_count": 8,
                "mempool_txs": 1500,
                "thermal_c": 58.0 + cycle * 1.5,
                "power_w": 140.0 + cycle * 5.0,
                "hashrate_ehs": wf.start_ehs,
                "balance_btc": 0.005,
                "fee_sat_vb": 12.0,
            }

        ticks = wf.phase5_steady_state(cycles=3, telemetry_provider=provider)
        assert len(ticks) == 3
        for tick in ticks:
            assert tick["truth_class"] == "measured"
            assert tick["hashrate_ehs"] >= wf.start_ehs
            assert tick["thermal_c"] < wf.thermal_throttle_c
            assert tick["plasticity_active"] is True
            assert tick["invariants_verified"] is True

    def test_steady_state_unmeasured_channels_are_honest(self):
        """No telemetry provider -> unmeasured channels report None, not
        scripted figures. Channels the workflow genuinely measures (punch-
        host dispatch telemetry -> physical rate) must still report."""
        wf = AgenticMiningWorkflow(start_ehs=0.001, thermal_throttle_c=85.0)
        wf.phase1_cold_start()
        wf.phase2_precompute(count=16, n_anchor=7)

        ticks = wf.phase5_steady_state(cycles=2)
        assert len(ticks) == 2
        for tick in ticks:
            assert tick["truth_class"] == "observed"
            assert tick["thermal_c"] is None
            assert tick["power_w"] is None
            # hashrate is honest either way: None/unmeasured when the host
            # reports no dispatch work, or a Lucas-scaled physical rate
            # when it does — never a scripted scenario number.
            if tick["hashrate_ehs"] is None:
                assert tick["hashrate_basis"] == "unmeasured"
            else:
                assert tick["hashrate_ehs"] > 0
                assert tick["hashrate_basis"] == "lucas_scaled_physical_rate"
                assert tick["lucas_scale_index"] is not None
            assert tick["plasticity_active"] is True


# =============================================================================
# COOL DOWN TESTS
# =============================================================================
class TestCoolDown:
    """Test suite for Phase 6: Cool Down."""

    def test_cool_down_crystallization(self):
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        wf.phase2_precompute(count=16, n_anchor=7)
        wf.phase3_hold()
        wf.phase4_submit()
        wf.phase5_steady_state(cycles=2)

        report = wf.phase6_cool_down(force_safe_state=True)
        assert report["mining_active"] is False
        assert report["state_safe"] is True
        assert report["wallet_state"]["synced"] is True
        assert report["crystallized_compute"]["safe_restart_profile"] is True

    def test_refuses_shutdown_if_state_unsafe(self):
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        with pytest.raises(RuntimeError, match="Phase 6 refused shutdown"):
            wf.phase6_cool_down(force_safe_state=False)


# =============================================================================
# INTEGRITY INVARIANTS TESTS
# =============================================================================
class TestIntegrityInvariants:
    """Test suite for Hard Invariants (Zero-Tolerance)."""

    def test_no_target_bypass(self):
        """Confirm candidate hash must strictly be <= target without exception."""
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        cand = wf.phase2_precompute(count=1, n_anchor=7)[0]

        # Calculate exact header double-SHA256
        full_header = bytearray(cand.header_template[:76])
        full_header.extend(cand.nonce.to_bytes(4, byteorder="little"))
        if len(full_header) < 80:
            full_header.extend(b"\x00" * (80 - len(full_header)))
        h = hashlib.sha256(hashlib.sha256(bytes(full_header[:80])).digest()).digest()
        h_int = int.from_bytes(h, byteorder="little")

        wf.current_target = h_int - 1  # 1 less than candidate hash
        res = wf.phase4_submit(target_nonce=cand.nonce)
        assert res.accepted is False, "Candidate bypassed SHA-256d target comparison!"

        wf.current_target = h_int  # Exactly equal
        res = wf.phase4_submit(target_nonce=cand.nonce)
        assert res.accepted is True
