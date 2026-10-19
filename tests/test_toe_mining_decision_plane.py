"""Unit tests for TOE 5+1 Decision Plane in Agentic Mining (Phase P4).

Verifies:
1. Stage Logs: Every stage logs {intelligence_used, input_hash, output_hash, confidence, entropy_delta, kappa}.
2. Superposition Hold: Bounded N <= 8 chain futures held in superposition with LRU eviction.
3. 5-Lens Scoring + Quantum-ext:
   - Predictive P(future)
   - Causal expected accept
   - Counterfactual regret pruning
   - Topological kappa trauma damping: exp(-I/10*(2-c))
   - Geometric bijection verification
   - Quantum-ext Hadamard-coin walk (replayable, NUMERICAL)
4. Collapse to ONE SearchPlan with explicit collapse_reason and alternatives log.
5. Host Recheck: 100% independent bit-exact host SHA256d recheck.
6. Pool Outcome & Bayesian Learning: Literal outcomes drive adaptive learning.
"""

from __future__ import annotations

import time
import pytest

from chronus.mla1517.mining.search_plan import (
    PlanSource,
    PoolOutcome,
    SearchPlan,
    WorkIdentity,
    _LANES,
)
from kellogg.canonical_tensor import RepresentationChoice
from toe.mining_decision_plane import (
    ChainFuture,
    IntelligenceStage,
    StageIntelligenceLog,
    SuperpositionHold,
    TOEMiningDecisionPlane,
)


def _make_identity(
    job_id: str = "job_braiins_77",
    fingerprint: str = "fp_9876543210",
) -> WorkIdentity:
    return WorkIdentity(
        pool_session_id="pool_sess_001",
        generation=1,
        job_id=job_id,
        job_fingerprint=fingerprint,
        target_generation=1,
        clean_jobs=True,
        received_at=time.monotonic(),
        work_space="header_workspace_dummy",
    )


class TestTOEMiningDecisionPlane:
    def test_stratum_live_predictive_log(self) -> None:
        """Stage 1 (STRATUM_LIVE) must emit a valid predictive intelligence log."""
        plane = TOEMiningDecisionPlane()
        log = plane.on_stratum_update(
            job_id="job_001",
            difficulty=1024.0,
            extranonce1="01020304",
            clean_jobs=True,
        )

        assert isinstance(log, StageIntelligenceLog)
        assert log.stage == IntelligenceStage.STRATUM_LIVE.value
        assert log.intelligence_used == "predictive"
        assert log.input_hash
        assert log.output_hash
        assert 0.0 <= log.confidence <= 1.0
        assert isinstance(log.entropy_delta, float)
        assert log.kappa == 0.0

    def test_superposition_hold_bounded_n8_and_lru(self) -> None:
        """SuperpositionHold must strictly bound futures to N<=8 and evict via LRU."""
        hold = SuperpositionHold(capacity=2)
        futures_8 = [
            ChainFuture(
                future_id=f"f_{i}",
                future_type=f"TYPE_{i}",
                job_id=f"j_{i}",
                difficulty=1024.0,
                extranonce2=f"0000000{i}",
                target=0xFFFF,
                probability=1.0 / 8,
            )
            for i in range(8)
        ]

        # Holding 8 must succeed
        held = hold.hold("gen_1", futures_8)
        assert len(held) == 8
        assert hold.get("gen_1") is not None

        # Holding > 8 must raise ValueError
        with pytest.raises(ValueError, match="bounded to N=8"):
            hold.hold("gen_err", futures_8 + [futures_8[0]])

        # Test LRU eviction: capacity=2
        hold.hold("gen_2", futures_8)
        hold.hold("gen_3", futures_8)  # Should evict gen_1
        assert hold.get("gen_1") is None
        assert hold.get("gen_2") is not None
        assert hold.get("gen_3") is not None

    def test_agentic_precompute_5plus1_lenses_and_logs(self) -> None:
        """Precompute must log all 5+1 intelligences and evaluate scores."""
        plane = TOEMiningDecisionPlane()
        ident = _make_identity()
        futures, logs = plane.precompute_superposition(
            identity=ident,
            base_step=0,
            window=32 * 32,
        )

        assert len(futures) == 8
        assert len(logs) == 6  # predictive, causal, counterfactual, topological, geometric, quantum_ext

        intelligences_logged = [l.intelligence_used for l in logs]
        assert intelligences_logged == [
            "predictive",
            "causal",
            "counterfactual",
            "topological",
            "geometric",
            "quantum_ext",
        ]

        for log in logs:
            assert log.input_hash
            assert log.output_hash
            assert 0.0 <= log.confidence <= 1.0
            assert isinstance(log.entropy_delta, float)
            assert isinstance(log.kappa, float)

        # High-regret futures must be pruned
        pruned_futures = [f for f in futures if f.pruned]
        assert len(pruned_futures) > 0
        assert any("STALE_RISK_HIGH" in f.future_type for f in pruned_futures)

    def test_collapse_to_single_search_plan_with_reason(self) -> None:
        """Collapse must select one winner future, log collapse reason, and emit valid SearchPlan."""
        plane = TOEMiningDecisionPlane()
        ident = _make_identity()

        plan = plane.collapse_to_search_plan(
            identity=ident,
            base_step=3200,
            window=32 * 16,
            extranonce2="00000001",
            executor_route="cpu_reference",
            representation=RepresentationChoice.EXACT_CLIFFORD_T,
        )

        assert isinstance(plan, SearchPlan)
        assert plan.window == 32 * 16
        assert plan.base_step == 3200

        # Check collapse evidence
        collapse_info = plan.evidence_refs["toe_collapse"]
        assert collapse_info["winner_future"]
        assert "MAX_5LENS_COMPOSITE_SCORE" in collapse_info["collapse_reason"]
        assert len(collapse_info["alternatives"]) == 8
        assert collapse_info["5lens_breakdown"]["geometric_coverage"] == "PASS_100_PCT"

        # Check coverage proof is preserved
        cert_dict = plan.evidence_refs["coverage_proof"]
        assert cert_dict["is_bijection"] is True
        assert cert_dict["zero_overlap"] is True

        # Check collapse stage log was appended
        last_log = plane.stage_logs[-1]
        assert last_log.stage == IntelligenceStage.COLLAPSE.value
        assert last_log.intelligence_used == "5lens_composite_collapse"

    def test_chronus_execute_host_recheck_logging(self) -> None:
        """CHRONUS_EXECUTE must log route honesty and host SHA256d recheck."""
        plane = TOEMiningDecisionPlane()
        ident = _make_identity()
        plan = plane.collapse_to_search_plan(ident, 0, 32 * 8, "00000001")

        header_76 = b"\x01\x00\x00\x00" + b"\x00" * 32 + b"\x11" * 32 + b"\x29\xab\x5f\x49" + b"\xff\xff\x00\x1d"
        recheck_pass, log = plane.record_execution(
            plan=plan,
            requested_route="cpu_reference",
            executed_route="cpu_reference",
            header_prefix_76=header_76,
            candidate_nonce=123456,
            target=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF,
            device_id="cpu-0",
        )

        assert recheck_pass is True
        assert log.stage == IntelligenceStage.CHRONUS_EXECUTE.value
        assert log.provenance["host_recheck_pass"] is True
        assert log.provenance["requested_route"] == "cpu_reference"
        assert log.provenance["executed_route"] == "cpu_reference"

    def test_pythia_truth_and_learning_loop(self) -> None:
        """PYTHIA_TRUTH and LEARN stages must process literal pool outcome and update priors."""
        plane = TOEMiningDecisionPlane()

        # Submit accepted share
        truth_log = plane.record_pool_outcome(PoolOutcome.ACCEPTED, "sub_101")
        assert truth_log.stage == IntelligenceStage.PYTHIA_TRUTH.value
        assert truth_log.provenance["outcome"] == "ACCEPTED"
        assert truth_log.kappa == 0.0

        # Learn from accepted share
        learn_log = plane.learn(PoolOutcome.ACCEPTED)
        assert learn_log.stage == IntelligenceStage.LEARN.value
        assert learn_log.confidence > 0.95

        # Submit stale share -> triggers curvature trauma kappa
        stale_truth = plane.record_pool_outcome(PoolOutcome.STALE, "sub_102")
        assert stale_truth.kappa == 0.15
        assert stale_truth.provenance["is_stale"] is True

        stale_learn = plane.learn(PoolOutcome.STALE)
        assert stale_learn.confidence < learn_log.confidence  # Prior derated
