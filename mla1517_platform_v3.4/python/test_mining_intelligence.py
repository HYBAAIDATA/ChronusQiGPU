"""World model, operating policy, loss ledger and Aethel-backed memory."""

from __future__ import annotations

import random
import shutil
import tempfile
import unittest
from pathlib import Path

from mla1517.mining.intelligence_memory import IntelligenceMemory
from mla1517.mining.loss_ledger import LossLedger
from mla1517.mining.operating_policy import (
    OperatingPolicy,
    PolicyContext,
    expected_loss,
    lucas_ladder,
)
from mla1517.mining.search_plan import CompletionState, ExecutionRecord
from mla1517.mining.world_model import GammaRate, MiningWorldModel, RouteModel
from policy_bench import REGIMES, simulate
from mla1517.mining.policy_audit import PolicyAuditor, grover_minimum

LANES = tuple(range(32))
ROUTE = "opencl_range"


def _record(**overrides) -> ExecutionRecord:
    base = dict(
        plan_id="p",
        job_fingerprint="fp",
        policy_id="m32",
        planned_window=128,
        actual_window=128,
        device_used="opencl",
        hash_count=128,
        elapsed_seconds=0.01,
        kernel_ms=0.0,
        temperature_c=None,
        locally_valid_shares=0,
        pool_accepted=0,
        pool_rejected=0,
        pool_stale=0,
        recovery_event=False,
        lane_order=LANES,
        preferred_face=0,
        requested_route=ROUTE,
        executed_route=ROUTE,
    )
    base.update(overrides)
    return ExecutionRecord(**base)


def _ctx(**overrides) -> PolicyContext:
    base = dict(
        route=ROUTE,
        lanes=32,
        max_window=1_000_000,
        legacy_window=96,
        legacy_lookahead=2,
        capacity=3,
        chunk_cap=65_536,
    )
    base.update(overrides)
    return PolicyContext(**base)


def _train(world: MiningWorldModel, *, overhead=8e-4, rate=5e7, n=40, seed=1, sizes=(96, 192, 4096)):
    rng = random.Random(seed)
    for _ in range(n):
        w = rng.choice(sizes)
        world.observe_execution(
            _record(
                planned_window=w,
                actual_window=w,
                hash_count=w,
                elapsed_seconds=overhead + w / rate + abs(rng.gauss(0, 1e-5)),
            )
        )


class GammaRateTests(unittest.TestCase):
    def test_posterior_follows_measured_rate(self):
        r = GammaRate(half_life_s=1e9)
        for _ in range(100):
            r.advance(60.0)
            r.event()
        # Gamma(1 + 100, 600 + 6000): shrunk toward the 1/600 s prior, not to 1/min.
        self.assertAlmostEqual(r.mean, 101 / 6600, places=6)
        for _ in range(900):
            r.advance(60.0)
            r.event()
        self.assertAlmostEqual(r.mean * 60.0, 1.0, delta=0.01)
        self.assertGreater(r.quantile(0.9), r.mean)

    def test_forgetting_tracks_a_calmer_pool(self):
        r = GammaRate(half_life_s=600.0)
        for _ in range(60):
            r.advance(10.0)
            r.event()
        busy = r.mean
        r.advance(7200.0)
        self.assertLess(r.mean, busy / 10)


class RouteModelTests(unittest.TestCase):
    def test_fit_separates_overhead_from_hash_rate(self):
        m = RouteModel()
        for w in (96, 4096, 192, 8192, 96, 4096, 192, 8192, 320) * 2:
            m.observe(w, 8e-4 + w / 5e7, 0.0)
        overhead, sec_per_hash = m.estimate()
        self.assertAlmostEqual(overhead, 8e-4, delta=1e-6)
        self.assertAlmostEqual(1 / sec_per_hash, 5e7, delta=5e4)

    def test_single_window_size_is_not_identifiable(self):
        m = RouteModel()
        for _ in range(50):
            m.observe(96, 1e-3, 0.0)
        self.assertFalse(m.identifiable)
        self.assertIsNone(m.estimate())

    def test_direct_kernel_timing_is_preferred(self):
        m = RouteModel()
        for _ in range(5):
            m.observe(1000, 0.003, 0.002)
        self.assertEqual(m.snapshot()["method"], "direct")
        overhead, sec_per_hash = m.estimate()
        self.assertAlmostEqual(overhead, 0.001, places=9)
        self.assertAlmostEqual(sec_per_hash, 2e-6, places=12)

    def test_invalidated_windows_do_not_train_the_route(self):
        world = MiningWorldModel()
        world.observe_execution(_record(completion_state=CompletionState.INVALIDATED))
        self.assertNotIn(ROUTE, world.routes)
        self.assertEqual(world.completions["INVALIDATED"], 1)


class PolicyTests(unittest.TestCase):
    def test_ladder_is_lucas_epochs(self):
        ladder = lucas_ladder(1_000_000, 32)
        self.assertTrue(all(w % 32 == 0 and 32 <= w <= 1_000_000 for w in ladder))
        self.assertIn(96, ladder)  # L_10 = 123 -> 96
        self.assertEqual(ladder, sorted(set(ladder)))

    def test_no_evidence_keeps_legacy(self):
        d = OperatingPolicy(MiningWorldModel()).decide(_ctx())
        self.assertEqual((d.source, d.window, d.lookahead), ("legacy", 96, 2))

    def test_recovery_always_holds(self):
        world = MiningWorldModel()
        _train(world)
        d = OperatingPolicy(world).decide(_ctx(recovery_active=True))
        self.assertEqual((d.source, d.window), ("hold", 96))

    def test_overhead_bound_route_gets_a_larger_window(self):
        world = MiningWorldModel()
        _train(world)
        d = OperatingPolicy(world).decide(_ctx())
        self.assertEqual(d.source, "model")
        self.assertGreater(d.window, 96)
        self.assertLess(d.expected["loss"], d.expected["legacy_loss"])

    def test_derate_cap_is_respected(self):
        world = MiningWorldModel()
        _train(world)
        d = OperatingPolicy(world).decide(_ctx(derate_cap=5000))
        self.assertLessEqual(d.window, 5000)

    def test_high_churn_shrinks_window_below_chunk(self):
        world = MiningWorldModel()
        _train(world, overhead=1e-5, rate=1e6)
        calm = OperatingPolicy(world).decide(_ctx(chunk_cap=10**9)).window
        world.tick(0.0)
        for i in range(1, 200):
            world.observe_bind(float(i), clean_jobs=True)
        busy = OperatingPolicy(world).decide(_ctx(chunk_cap=10**9)).window
        self.assertLess(busy, calm)

    def test_window_seconds_envelope_bounds_the_choice(self):
        world = MiningWorldModel()
        _train(world)  # ~5e7 H/s: 2 ms of hashing is ~100k nonces
        d = OperatingPolicy(world).decide(_ctx(max_window_seconds=0.002))
        self.assertEqual(d.source, "model")
        self.assertLessEqual(d.window / d.expected["hash_rate_hs"], 0.002)
        free = OperatingPolicy(world).decide(_ctx())
        self.assertGreater(free.window, d.window)

    def test_choice_is_the_argmin_of_reported_candidates(self):
        world = MiningWorldModel()
        _train(world)
        d = OperatingPolicy(world).decide(_ctx())
        best = min(d.candidates, key=lambda c: (c["loss"], -c["window"]))
        self.assertEqual(best["window"], d.window)

    def test_expected_loss_matches_closed_form(self):
        total, o, s = expected_loss(1000, 1e-3, 1e-6, 0.01, 10**9)
        self.assertAlmostEqual(o, 1e-3 / (1e-3 + 1e-3))
        self.assertAlmostEqual(s, 0.01 * 1e-3 / 2)
        self.assertAlmostEqual(total, o + s)

    def test_probe_is_bounded_and_labelled(self):
        world = MiningWorldModel()
        for _ in range(10):
            world.observe_execution(_record(planned_window=96, actual_window=96, hash_count=96))
        policy = OperatingPolicy(world)
        sources = [policy.decide(_ctx()).source for _ in range(16)]
        self.assertEqual(sources.count("probe"), 2)
        self.assertEqual(sources.count("legacy"), 14)


class LossLedgerTests(unittest.TestCase):
    def test_time_is_split_by_cause(self):
        world = MiningWorldModel()
        ledger = LossLedger()
        ledger.observe_bind(0.0)
        ledger.observe_execution(
            _record(hash_count=1000, elapsed_seconds=0.003, kernel_ms=2.0), world, started_at=0.5
        )
        ledger.observe_execution(
            _record(
                hash_count=500,
                elapsed_seconds=0.002,
                kernel_ms=1.0,
                completion_state=CompletionState.INVALIDATED,
            ),
            world,
            started_at=1.0,
        )
        ledger.observe_idle(0.25)
        ledger.observe_recovery(2.0, True)
        ledger.observe_recovery(2.5, False)
        snap = ledger.snapshot(4.0)
        s = snap["seconds"]
        self.assertAlmostEqual(s["useful_hashing"], 0.002)
        self.assertAlmostEqual(s["stale_hashing"], 0.001)
        self.assertAlmostEqual(s["window_overhead"], 0.002)
        self.assertAlmostEqual(s["idle_no_plan"], 0.25)
        self.assertAlmostEqual(s["recovery"], 0.5)
        self.assertAlmostEqual(sum(s.values()), 4.0)
        self.assertAlmostEqual(snap["time_to_first_hash_ms"]["p50"], 500.0)
        self.assertEqual(snap["stale_hashes"], 500)

    def test_unknown_hash_rate_is_unattributed_not_guessed(self):
        ledger = LossLedger()
        ledger.observe_execution(_record(elapsed_seconds=0.01), MiningWorldModel(), started_at=0.0)
        self.assertAlmostEqual(ledger.snapshot(1.0)["seconds"]["unattributed_execution"], 0.01)


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_learned_state_survives_restart_through_aethel(self):
        world = MiningWorldModel()
        _train(world)
        world.observe_bind(10.0, clean_jobs=True)
        mem = IntelligenceMemory(self.dir)
        receipt = mem.checkpoint(world.export_state())
        self.assertEqual(receipt["entries"], 1)
        restored = MiningWorldModel()
        restored.import_state(IntelligenceMemory(self.dir).load())
        self.assertEqual(restored.snapshot()["routes"], world.snapshot()["routes"])
        self.assertEqual(restored.clean.observed_events, 1)

    def test_tampered_block_is_rejected(self):
        mem = IntelligenceMemory(self.dir)
        mem.checkpoint({"schema": "x", "v": 1})
        block = next((self.dir / "gen-000001").rglob("*.blk"))
        block.write_bytes(block.read_bytes().replace(b"1", b"2"))
        fresh = IntelligenceMemory(self.dir)
        self.assertIsNone(fresh.load())
        self.assertIsNotNone(fresh.last_error)

    def test_rotation_bounds_the_ledger_and_keeps_latest(self):
        mem = IntelligenceMemory(self.dir, rotate_after=4)
        for i in range(11):
            mem.checkpoint({"i": i})
        gens = sorted(p.name for p in self.dir.iterdir())
        self.assertLessEqual(len(gens), 2)
        self.assertEqual(IntelligenceMemory(self.dir, rotate_after=4).load(), {"i": 10})

    def test_empty_memory_is_a_clean_baseline(self):
        self.assertIsNone(IntelligenceMemory(self.dir).load())


class PolicyBenchTests(unittest.TestCase):
    """The learned policy must never lose materially to the legacy window."""

    def _pair(self, name, seconds):
        regime = next(r for r in REGIMES if r.name == name)
        legacy = simulate(regime, mode="legacy", seconds=seconds, seed=7)
        model = simulate(regime, mode="model", seconds=seconds, seed=7)
        return legacy["efficiency"], model

    def test_bounded_learning_cost_when_the_ceiling_binds(self):
        legacy, model = self._pair("cpu_mainnet_rung10", 20)
        self.assertGreater(model["efficiency"], legacy - 0.005)

    def test_overhead_bound_cpu_gains_with_ladder_ceiling(self):
        legacy, model = self._pair("cpu_mainnet_rung10_ladder_ceiling", 20)
        self.assertGreater(model["efficiency"], legacy + 0.10)
        self.assertEqual(model["final_window"], 15104)

    def test_high_churn_trades_overhead_against_stale_work(self):
        legacy, model = self._pair("cpu_reconnect_storm", 60)
        self.assertGreater(model["efficiency"], legacy)
        self.assertLess(model["final_window"], 15104)

    def test_extended_ceiling_removes_igpu_overhead(self):
        legacy, model = self._pair("igpu_mainnet_extended_ceiling", 120)
        self.assertGreater(model["efficiency"], 0.95)
        self.assertLess(legacy, 0.5)


class PolicyAuditTests(unittest.TestCase):
    def _decision(self, seed=1):
        world = MiningWorldModel()
        _train(world, seed=seed)
        return OperatingPolicy(world).decide(_ctx())

    def test_vqc_minimum_matches_classical_argmin(self):
        if not PolicyAuditor().snapshot()["vqc_available"]:
            self.skipTest("turing_universal_quantum_computer not importable")
        rng = random.Random(3)
        for trial in range(25):
            losses = [rng.random() for _ in range(rng.randint(2, 22))]
            found = grover_minimum(losses, seed=trial)
            self.assertEqual(losses[found["index"]], min(losses))
            self.assertLessEqual(found["qubits"], 5)

    def test_audit_agrees_and_is_attested(self):
        auditor = PolicyAuditor(every=1)
        if not auditor.snapshot()["vqc_available"]:
            self.skipTest("turing_universal_quantum_computer not importable")
        record = auditor.maybe_audit(self._decision())
        self.assertTrue(record["agree"])
        self.assertEqual(record["vqc"]["window"], record["classical_window"])
        self.assertEqual(record["decided_window"], record["classical_window"])
        att = record["attestation"]
        self.assertEqual(att["schema"], "kellogg.attestation/v1")
        self.assertEqual(len(att["digest"]), 64)
        self.assertFalse(att["boundary"]["theorem_proven"])
        again = PolicyAuditor(every=1).maybe_audit(self._decision())
        self.assertEqual(again["attestation"]["digest"], att["digest"])

    def test_audit_without_vqc_still_attests_classical_choice(self):
        auditor = PolicyAuditor(every=1)
        auditor._register_cls, auditor._vqc_error = None, "ModuleNotFoundError: test"
        record = auditor.maybe_audit(self._decision())
        self.assertIsNone(record["agree"])
        self.assertFalse(record["vqc"]["available"])
        self.assertIn("digest", record["attestation"])

    def test_audit_cadence_and_legacy_decisions_are_skipped(self):
        auditor = PolicyAuditor(every=3)
        decision = self._decision()
        results = [auditor.maybe_audit(decision) for _ in range(6)]
        self.assertEqual(sum(r is not None for r in results), 2)
        legacy = OperatingPolicy(MiningWorldModel()).decide(_ctx())
        self.assertIsNone(PolicyAuditor(every=1).maybe_audit(legacy))

    def test_disagreement_is_recorded_not_acted_on(self):
        auditor = PolicyAuditor(every=1)

        class Wrong:
            """A register that always measures the worst candidate."""

            def __init__(self, n):
                self.n = n

            def uniform_superposition(self):
                pass

            def apply_grover_oracle(self, marked):
                pass

            def diffusion(self):
                pass

            def measure(self, seed):
                return 0

        auditor._register_cls = Wrong
        decision = self._decision()
        record = auditor.maybe_audit(decision)
        if record["vqc"]["window"] != record["classical_window"]:
            self.assertFalse(record["agree"])
            self.assertEqual(auditor.disagreements, 1)
        self.assertEqual(record["decided_window"], decision.window)


class LiveCoordinatorTests(unittest.TestCase):
    """The intelligence inside the real coordinator on the soak voyage."""

    def _soak(self, seconds, memory_dir):
        import asyncio
        import logging
        import os

        import soak_voyage
        from mla1517.mining import coordinator as coordinator_module

        created = []
        original = coordinator_module.IntelligentPoolCoordinator.__init__

        def capture(self_, *args, **kwargs):
            original(self_, *args, **kwargs)
            created.append(self_)

        os.environ["PYTHIA_INTELLIGENCE_DIR"] = str(memory_dir)
        os.environ["PYTHIA_INTELLIGENCE_CHECKPOINT_S"] = "0.5"
        coordinator_module.IntelligentPoolCoordinator.__init__ = capture
        logging.disable(logging.CRITICAL)
        try:
            stats = asyncio.run(soak_voyage.run_soak(seconds, seed=1517, backend="cpu"))
        finally:
            coordinator_module.IntelligentPoolCoordinator.__init__ = original
            os.environ.pop("PYTHIA_INTELLIGENCE_DIR", None)
            os.environ.pop("PYTHIA_INTELLIGENCE_CHECKPOINT_S", None)
            logging.disable(logging.NOTSET)
        return stats, created[0]

    def test_soak_with_intelligence_stays_honest_and_remembers(self):
        from lucas.core import lucas

        memory_dir = Path(tempfile.mkdtemp())
        try:
            stats, coord = self._soak(4.0, memory_dir)
            self.assertEqual(stats["unexpected_errors"], [])
            self.assertEqual(stats["duplicate_submits"], 0)
            self.assertEqual(stats["stale_submits"], 0)
            snap = coord.evidence_snapshot()["intelligence"]
            decision = snap["decision"]
            self.assertIsNotNone(decision)
            self.assertLessEqual(decision["window"], coord._intelligence_ceiling())
            self.assertLessEqual(coord._intelligence_ceiling(), lucas(31))
            self.assertIn("cpu_reference", snap["world"]["routes"])
            self.assertGreater(snap["loss"]["executions"], 0)
            self.assertTrue(snap["memory"]["ledger_verified"])
            self.assertGreater(snap["memory"]["checkpoints_this_run"], 0)
            learned = snap["world"]["routes"]["cpu_reference"]["fit_samples"]
            restored = MiningWorldModel()
            restored.import_state(IntelligenceMemory(memory_dir).load())
            self.assertGreater(restored.routes["cpu_reference"].fit_samples, 0)
            self.assertLessEqual(restored.routes["cpu_reference"].fit_samples, learned)
        finally:
            shutil.rmtree(memory_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
