"""Training verification for the three autonomous capabilities.

Covers the directive's training contracts end to end, offline only:

- Self-healing: every known fault type has a registered handler; the heal
  loop detects simulated faults, repairs them, verifies HEALTHY with a
  fresh probe, escalates what it cannot repair, and logs detection+repair
  with a Cassini fingerprint.
- Self-optimising: CUOP is measured at baseline, a learner tunes a real
  parameter, the post-change CUOP is measured, and the claimed delta is
  the measured delta (never a projection).
- Agentic mining: the ValidityLearner is trained on (features, validity)
  pairs and biases phase-4 probe order without ever suppressing a
  candidate; the CoolDownController is trained on (rejection rate,
  adjustment) pairs and adapts the next cycle's cadence in phase 6; the
  local SHA256d check remains the sole accept authority.
- Integration: Salamander supervises all three — learner drift triggers
  retraining, a CUOP drop triggers re-optimisation, and a mining stall
  triggers a restart.
"""

import hashlib
import os
import sys
from types import SimpleNamespace

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PYTHIA_DIR = os.path.dirname(_THIS_DIR)
_INTEL_DIR = os.path.join(_PYTHIA_DIR, "Intelligence")

for p in (_PYTHIA_DIR, _INTEL_DIR, os.path.abspath("."), os.path.abspath("Intelligence")):
    if p not in sys.path:
        sys.path.insert(0, p)

from Intelligence.autonomous_capabilities import (
    CassiniCycleLedger,
    CoolDownController,
    CuopLearner,
    CuopMeter,
    KNOWN_FAULT_TYPES,
    MIN_RATE_SCALE,
    SelfHealingLoop,
    SelfOptimisingLoop,
    STATUS_HEALTHY,
    ValidityLearner,
    cassini_fingerprint,
    telemetry_snapshot,
)
from Intelligence.salamander import SalamanderEngine
from Intelligence.agentic_mining import AgenticMiningWorkflow


class DispatchTelemetry:
    """Minimal measured-dispatch recorder for CUOP windows.

    Replaces the quarantined iGPU telemetry module; records only observed
    dispatches — work_items and busy seconds — never projections.
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.dispatch_total = 0
        self.work_items_total = 0
        self.busy_seconds = 0.0

    def record_dispatch(
        self,
        *,
        backend: str,
        gpu: bool,
        work_items: int,
        kernel_ms: float = 0.0,
        punch_name: str = "",
    ) -> None:
        if not self.enabled:
            return
        self.dispatch_total += 1
        self.work_items_total += max(0, int(work_items))
        self.busy_seconds += max(0.0, float(kernel_ms)) / 1000.0


IgpuTelemetry = DispatchTelemetry

# ---------------------------------------------------------------------------
# Shared offline doubles — simulated fault injection, measured CUOP windows
# ---------------------------------------------------------------------------


class FakeSubsystem:
    """A monitored subsystem whose health/fault state tests control."""

    def __init__(self) -> None:
        self.fault = STATUS_HEALTHY
        self.repair_calls: list = []

    def probe(self) -> str:
        return self.fault

    def inject(self, fault_type: str) -> None:
        self.fault = fault_type

    def repair(self, fault_type: str) -> bool:
        self.repair_calls.append(fault_type)
        self.fault = STATUS_HEALTHY
        return True


def _candidate(nonce: int, sector: int = 0, born: float = 0.95):
    """A PrecomputedCandidate-shaped record for learner unit tests."""
    return SimpleNamespace(
        nonce=nonce,
        sector_id=sector,
        born_probability=born,
        cassini_valid=True,
        zeckendorf_valid=True,
        zeckendorf_mask=nonce,
        galois_composite=nonce * 7,
    )


def _sha256d_int(header_template: bytes, nonce: int) -> int:
    """The real consensus check: sha256d(template + LE nonce) as LE int."""
    blob = bytes(header_template) + nonce.to_bytes(4, byteorder="little")
    digest = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
    return int.from_bytes(digest, byteorder="little")


# =============================================================================
# Cassini ledger
# =============================================================================


class TestCassiniLedger:
    def test_fingerprint_is_exact_cassini_sign(self):
        # L_n^2 - 5 F_n^2 = 4(-1)^n — sign alternates +1/-1 by index.
        assert [cassini_fingerprint(n) for n in range(6)] == [1, -1, 1, -1, 1, -1]

    def test_entries_carry_fingerprint_and_chain(self):
        ledger = CassiniCycleLedger()
        ledger.log("self_healing", {"fault_type": "subsystem_stall"})
        ledger.log("mining_cycle", {"shares": 1})
        assert [e.cassini_fingerprint for e in ledger.entries] == [1, -1]
        assert ledger.verify()

    def test_tampering_breaks_verification(self):
        ledger = CassiniCycleLedger()
        ledger.log("a", {"v": 1})
        ledger.log("b", {"v": 2})
        ledger.entries[0].payload["v"] = 999
        assert not ledger.verify()

    def test_reordering_breaks_verification(self):
        ledger = CassiniCycleLedger()
        for i in range(3):
            ledger.log("a", {"i": i})
        ledger.entries.reverse()
        assert not ledger.verify()


# =============================================================================
# Self-healing
# =============================================================================


class TestSelfHealing:
    def test_every_known_fault_type_has_a_handler(self):
        loop = SelfHealingLoop()
        for fault_type in KNOWN_FAULT_TYPES:
            assert fault_type in loop.repair_actions, fault_type

    def test_heal_cycle_detects_repairs_and_verifies_healthy(self):
        engine = SalamanderEngine()
        loop = engine.heal_loop
        subsystem = FakeSubsystem()
        loop.register_subsystem(
            "hyba_data.mining_subsystem",
            probe=subsystem.probe,
            repairs={ft: (lambda ft=ft: subsystem.repair(ft)) for ft in KNOWN_FAULT_TYPES},
        )

        for fault_type in sorted(KNOWN_FAULT_TYPES):
            subsystem.inject(fault_type)
            records = loop.heal_cycle()
            assert len(records) == 1
            rec = records[0]
            # Detection AND repair are both logged.
            assert rec.fault_type == fault_type
            assert rec.detected_at and rec.repaired_at
            # HEALTHY is claimed only because the post-repair probe says so.
            assert rec.final_status == STATUS_HEALTHY
            assert rec.escalated is False
            # Cassini fingerprint on the record.
            assert rec.cassini_fingerprint in (1, -1)
            # The engine's diagnosis channel saw the fault (proposal id).
            assert rec.proposal_id
        assert loop.ledger.verify()

    def test_unrepairable_fault_escalates_not_ignored(self):
        loop = SelfHealingLoop()
        subsystem = FakeSubsystem()
        # No repair registered for this subsystem.
        loop.register_subsystem("dead.weight", probe=subsystem.probe, repairs={})
        subsystem.inject("subsystem_stall")

        (rec,) = loop.heal_cycle()
        assert rec.final_status == "ESCALATED"
        assert rec.escalated is True
        assert loop.escalations == [rec]
        assert rec.repaired_at is None

    def test_failed_repair_escalates(self):
        loop = SelfHealingLoop()
        subsystem = FakeSubsystem()
        # Repair runs but the fault persists -> must escalate.
        loop.register_subsystem(
            "stubborn", probe=subsystem.probe, repairs={"timeout": lambda: True}
        )
        subsystem.inject("timeout")
        (rec,) = loop.heal_cycle()
        assert rec.escalated is True
        assert rec.final_status == "ESCALATED"

    def test_repair_that_returns_false_escalates(self):
        loop = SelfHealingLoop()
        subsystem = FakeSubsystem()
        loop.register_subsystem("weak", probe=subsystem.probe, repairs={"timeout": lambda: False})
        subsystem.inject("timeout")
        (rec,) = loop.heal_cycle()
        assert rec.escalated is True


# =============================================================================
# Self-optimising (CUOP)
# =============================================================================


def _run_dispatch_window(
    telemetry: IgpuTelemetry, batch_size: int, kernel_ms_fn, items_fn=None
) -> None:
    """Simulate a measured work window: 8 dispatches at the given batch size."""
    for _ in range(8):
        telemetry.record_dispatch(
            backend="cpu",
            gpu=False,
            work_items=int(items_fn(batch_size) if items_fn else batch_size),
            kernel_ms=kernel_ms_fn(batch_size),
        )


class TestSelfOptimising:
    def _make_loop(self, kernel_ms_fn, power_fn, start_batch=2048, items_fn=None):
        """Build a measured-CUOP rig: telemetry + meter + batch-size learner."""
        telemetry = IgpuTelemetry(enabled=True)
        meter = CuopMeter(usd_per_kwh=0.10)
        state = {"batch": float(start_batch)}

        def measure():
            snap = telemetry_snapshot(telemetry)
            _run_dispatch_window(telemetry, state["batch"], kernel_ms_fn, items_fn)
            return meter.measure_telemetry_window(
                before=snap,
                telemetry=telemetry,
                mean_power_w=power_fn(state["batch"]),
            )

        learner = CuopLearner(
            "batch_size",
            getter=lambda: state["batch"],
            setter=lambda v: state.__setitem__("batch", v),
            lo=256,
            hi=16384,
        )
        loop = SelfOptimisingLoop(meter, learners=[learner])
        return loop, learner, measure

    def test_baseline_then_measured_improvement(self):
        # Kernel time is nearly flat in batch size -> ops/J rises with it.
        loop, learner, measure = self._make_loop(
            kernel_ms_fn=lambda bs: 5.0 + bs * 0.0001,
            power_fn=lambda bs: 100.0,
        )
        baseline = loop.measure_baseline(measure)
        assert baseline.cuop > 0.0
        report = loop.optimise_cycle(measure)
        assert report["new_cuop"] >= report["baseline_cuop"]
        assert report["delta_cuop"] == pytest.approx(report["new_cuop"] - report["baseline_cuop"])
        assert report["improvement_measured"] is True
        assert learner.value > 2048  # the learner found the improving direction
        assert report["cassini_fingerprint"] in (1, -1)
        assert loop.ledger.verify()

    def test_regression_is_reverted_and_delta_honest(self):
        # Power grows quadratically in batch -> CUOP falls as batch grows.
        loop, learner, measure = self._make_loop(
            kernel_ms_fn=lambda bs: 2.0 + bs * 0.002,
            power_fn=lambda bs: 60.0 + (bs / 128.0) ** 2,
        )
        loop.measure_baseline(measure)
        report = loop.optimise_cycle(measure)
        # The first (upward) suggestion measured worse -> reverted.
        assert report["reverted"] is True
        assert learner.value <= 2048
        # Post-revert measurement equals baseline up to float noise.
        assert report["new_cuop"] >= report["baseline_cuop"] * (1 - 1e-9)
        assert report["delta_cuop"] >= -report["baseline_cuop"] * 1e-9

    def test_no_claim_without_measurement(self):
        # Genuinely flat response: identical work and time whatever the
        # parameter value — CUOP cannot improve, so no improvement is claimed.
        loop, learner, measure = self._make_loop(
            kernel_ms_fn=lambda bs: 5.0,
            power_fn=lambda bs: 100.0,
            items_fn=lambda bs: 64,
        )
        report = loop.optimise_cycle(measure)
        # No material improvement: the delta is within float accumulation
        # noise of the telemetry window, and it is the measured delta.
        assert abs(report["delta_cuop"]) <= report["baseline_cuop"] * 1e-9
        assert report["delta_cuop"] == pytest.approx(report["new_cuop"] - report["baseline_cuop"])
        # Every prediction is labelled a projection, not a measurement.
        proj = learner.predict(learner.value)
        assert proj["is_projection"] is True and proj["projection_is_measured"] is False

    def test_unavailable_reading_is_never_scored(self):
        loop, learner, measure = self._make_loop(
            kernel_ms_fn=lambda bs: 5.0 + bs * 0.0001,
            power_fn=lambda bs: 100.0,
        )
        baseline = loop.measure_baseline(measure)
        start, samples = learner.value, len(learner.history)

        report = loop.optimise_cycle(lambda: None)

        assert report["evidence_class"] == "Unavailable"
        assert report["new_cuop"] is None and report["delta_cuop"] is None
        assert report["improvement_measured"] is False
        assert learner.value == start  # the parameter under test is restored
        assert len(learner.history) == samples  # nothing was scored
        assert loop.latest is baseline
        assert loop.ledger.verify()

    def test_no_baseline_without_a_reading(self):
        loop, _learner, _measure = self._make_loop(
            kernel_ms_fn=lambda bs: 5.0,
            power_fn=lambda bs: 100.0,
        )
        assert loop.measure_baseline(lambda: None) is None
        report = loop.optimise_cycle(lambda: None)
        assert loop.baseline is None
        assert report["evidence_class"] == "Unavailable"
        assert report["baseline_cuop"] is None


# =============================================================================
# Agentic mining — ValidityLearner + CoolDownController
# =============================================================================


class TestValidityLearner:
    def test_trained_on_feature_validity_pairs(self):
        learner = ValidityLearner()
        # Sector 3 candidates were the accepted ones in this run's history.
        candidates = [_candidate(n, sector=n % 7) for n in range(1, 29)]
        for _ in range(6):
            for c in candidates:
                learner.learn_candidate(c, accepted=(c.sector_id == 3))
        ordered = learner.order_candidates(candidates)
        # The learned class leads the probe order.
        first_sector = ordered[0].sector_id
        assert first_sector == 3
        # No candidate is ever suppressed — a permutation, not a filter.
        assert sorted(c.nonce for c in ordered) == sorted(c.nonce for c in candidates)

    def test_drift_error_and_retrain(self):
        learner = ValidityLearner()
        for n in range(1, 17):
            learner.learn_candidate(_candidate(n, sector=1), accepted=True)
        # Force errors so the drift detector sees a stale model.
        learner.recent_errors.extend([1.0] * 16)
        assert learner.drift_error() == pytest.approx(1.0)
        result = learner.retrain()
        assert result["retrained"] is True
        assert learner.drift_error() == 0.0


class TestPhase4LearnerWiring:
    def _workflow_with_candidates(self, count=32):
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        cands = wf.phase2_precompute(count=count, n_anchor=7)
        return wf, cands

    def test_learner_biases_probe_order_never_suppresses(self):
        wf, cands = self._workflow_with_candidates(32)
        # Measured digests for this run; exactly one winner under the target.
        digests = {c.nonce: _sha256d_int(c.header_template, c.nonce) for c in cands}
        winner = min(digests, key=digests.get)
        wf.current_target = digests[winner]

        # Deterministic worst case: reinsert the winner so it sits LAST in
        # insertion order — the untrained probe must walk the whole set.
        memory = wf.manifold_bridge.md_memory
        memory[winner] = memory.pop(winner)

        # Untrained order: insertion order — winner is the final probe.
        wf.validity_learner = ValidityLearner()
        untrained = wf.phase4_submit()
        assert untrained.accepted and untrained.nonce == winner
        assert untrained.probes_taken == len(cands)

        # Trained on this run's measured (features, validity) pairs.
        trained = ValidityLearner()
        for _ in range(6):
            for c in cands:
                trained.learn_candidate(c, accepted=(c.nonce == winner))
        wf.validity_learner = trained
        r = wf.phase4_submit()
        assert r.accepted and r.nonce == winner
        # The trained order can never be worse than the worst-case untrained
        # order (a stable-sort tie keeps the winner last at most).
        assert r.probes_taken <= untrained.probes_taken
        # The learner can only permute — every probe came from the full set.
        probed = {p["nonce"] for p in wf.probe_log}
        assert probed <= {c.nonce for c in cands}

    def test_sha256d_still_sole_authority_under_learner(self):
        wf, cands = self._workflow_with_candidates(16)
        trained = ValidityLearner()
        for _ in range(6):
            for c in cands:
                trained.learn_candidate(c, accepted=True)  # all "valid"
        wf.validity_learner = trained
        wf.current_target = 0  # nothing can pass
        r = wf.phase4_submit()
        # Learner confidence does not override consensus.
        assert r.accepted is False
        assert r.probes_taken == len(cands)  # all were probed, none suppressed

    def test_explicit_nonce_path_unchanged(self):
        wf, cands = self._workflow_with_candidates(8)
        res = wf.phase4_submit(target_nonce=cands[3].nonce)
        assert res.nonce == cands[3].nonce
        assert res.probes_taken == 1


class TestCoolDownController:
    def test_trained_on_rate_adjustment_pairs(self):
        c = CoolDownController()
        c.learn(0.5, 0.2)  # at 50% rejection, scale 0.2 proved beneficial
        c.learn(0.25, 0.6)  # at 25% rejection, scale 0.6 proved beneficial
        assert c.gain == pytest.approx(((1 - 0.2) / 0.5 + (1 - 0.6) / 0.25) / 2)

    def test_rate_contracts_on_rejection_recovers_on_clean(self):
        c = CoolDownController()
        rec = c.observe(accepted=0, rejected=10)
        assert rec["rejection_rate"] == pytest.approx(1.0)
        assert c.rate_scale < 1.0 and c.rate_scale >= MIN_RATE_SCALE
        rec2 = c.observe(accepted=10, rejected=0)
        assert rec2["rejection_rate"] == 0.0
        assert c.rate_scale > rec["rate_scale"]  # recovering toward 1.0

    def test_phase6_wires_cooldown_and_next_cycle_cadence(self):
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        wf.phase2_precompute(count=8, n_anchor=7)
        wf.phase3_hold()
        wf.phase4_submit()  # default diff-1 target -> honest rejection
        wf.phase5_steady_state(cycles=2)
        report = wf.phase6_cool_down(force_safe_state=True)

        assert report["measured_rejection_rate"] == pytest.approx(1.0)
        assert report["submission_rate_scale"] < 1.0
        assert wf.submission_rate_scale == report["submission_rate_scale"]

        # The adapted rate throttles the next session's cadence.
        wf2 = AgenticMiningWorkflow()
        wf2.phase1_cold_start()
        wf2.phase2_precompute(count=8, n_anchor=7)
        wf2.submission_rate_scale = report["submission_rate_scale"]
        ticks = wf2.phase5_steady_state(cycles=4)
        assert len(ticks) == max(1, round(4 * report["submission_rate_scale"]))
        assert len(ticks) < 4

    def test_six_phase_cycle_logged_with_fingerprint(self):
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        wf.phase2_precompute(count=8, n_anchor=7)
        wf.phase3_hold()
        wf.phase4_submit()
        wf.phase5_steady_state(cycles=2)
        wf.phase6_cool_down(force_safe_state=True)

        kinds = [e.kind for e in wf.autonomy_ledger.entries]
        assert "share_submission" in kinds
        assert "mining_cycle" in kinds
        cycle = wf.autonomy_ledger.entries[-1]
        assert cycle.payload["phases_completed"] == 6
        assert all(e.cassini_fingerprint in (1, -1) for e in wf.autonomy_ledger.entries)
        assert wf.autonomy_ledger.verify()


# =============================================================================
# Integration — Salamander supervises all three
# =============================================================================


class TestSupervisedIntegration:
    def _rig(self):
        engine = SalamanderEngine()
        supervisor = engine.supervisor
        return engine, supervisor

    def test_learner_drift_triggers_retrain(self):
        _, supervisor = self._rig()
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        supervisor.attach_workflow(wf)

        learner = wf.validity_learner
        for n in range(1, 9):
            learner.learn_candidate(_candidate(n, sector=n % 7), accepted=True)
        learner.recent_errors.extend([0.9] * 16)  # measured drift

        report = supervisor.supervise_cycle()
        drift_actions = [a for a in report["actions"] if a["payload"]["trigger"] == "learner_drift"]
        assert drift_actions, "learner drift did not trigger retraining"
        assert drift_actions[0]["payload"]["result"]["retrained"] is True

    def test_cuop_drop_triggers_reoptimisation(self):
        _, supervisor = self._rig()
        telemetry = IgpuTelemetry(enabled=True)
        meter = CuopMeter(usd_per_kwh=0.10)
        state = {"batch": 2048.0, "degraded": False}

        def measure():
            snap = telemetry_snapshot(telemetry)
            # A degraded run completes the same dispatches far slower.
            ms = 5.0 if not state["degraded"] else 500.0
            for _ in range(4):
                telemetry.record_dispatch(
                    backend="cpu", gpu=False, work_items=int(state["batch"]), kernel_ms=ms
                )
            return meter.measure_telemetry_window(
                before=snap, telemetry=telemetry, mean_power_w=100.0
            )

        learner = CuopLearner(
            "batch_size",
            getter=lambda: state["batch"],
            setter=lambda v: state.__setitem__("batch", v),
            lo=256,
            hi=16384,
        )
        loop = SelfOptimisingLoop(meter, learners=[learner])
        supervisor.attach_optimiser(loop, measure)
        loop.measure_baseline(measure)

        state["degraded"] = True  # measured CUOP collapses
        report = supervisor.supervise_cycle()
        cuop_actions = [a for a in report["actions"] if a["payload"]["trigger"] == "cuop_drop"]
        assert cuop_actions, "CUOP drop did not trigger re-optimisation"

    def test_mining_stall_triggers_restart(self):
        engine, supervisor = self._rig()
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        supervisor.attach_workflow(wf)

        # Simulate a stall: mining flag set, telemetry flat.
        wf.is_mining = True
        supervisor._last_telemetry_count = len(wf.telemetry_history)

        report = supervisor.supervise_cycle()
        stall = [a for a in report["actions"] if a.get("trigger") == "subsystem_stall"]
        assert stall, "mining stall did not reach the heal loop"
        assert stall[0]["final_status"] == STATUS_HEALTHY  # restart verified
        assert wf.is_initialized and wf.is_mining is False
        # Detection + repair logged with a Cassini fingerprint.
        assert stall[0]["cassini_fingerprint"] in (1, -1)
        assert engine.heal_loop.ledger.verify()

    def test_supervisor_status_reports_all_three(self):
        engine, supervisor = self._rig()
        wf = AgenticMiningWorkflow()
        wf.phase1_cold_start()
        supervisor.attach_workflow(wf)
        status = supervisor.status()
        assert status["workflow_attached"] is True
        assert "subsystem_stall" in status["heal_loop"]["registered_fault_types"]
        assert status["theorem_proven"] is False


# =============================================================================
# Honesty boundary
# =============================================================================


def test_theorem_proven_stays_false_everywhere():
    import Intelligence.autonomous_capabilities as ac

    assert ac.THEOREM_PROVEN is False
    loop = SelfOptimisingLoop(CuopMeter())
    assert loop.ledger.to_list() == []
    engine = SalamanderEngine()
    assert engine.supervisor.status()["theorem_proven"] is False
    assert engine.heal_loop.status()["theorem_proven"] is False
