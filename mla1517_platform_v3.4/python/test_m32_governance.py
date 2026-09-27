"""Governance, Lucas-gate, and phyllotaxis contracts for the M32 substrate.

Covers the mandate wiring: exact spherical 5-design proof over the
32-face frame, golden-ratio lane storage, the Lucas execution ladder gate,
and the self-healing sink's real device-side effects.
"""

from __future__ import annotations

import struct
import unittest
from types import SimpleNamespace

from mla1517.mining.geometry import (
    LANES,
    M32GovernanceError,
    M32Topology,
    PhyllotaxisLaneIndex,
    spherical_design_moments,
    truncated_icosahedron_frame,
    verify_spherical_design,
)
from mla1517.mining.pow import (
    LUCAS_EXECUTION_SCALE_INDICES,
    LucasScaleError,
    compact_target,
    require_lucas_execution_scale,
)
from mla1517.mining.solver import M32SearchSolver


class SphericalDesignTests(unittest.TestCase):
    def test_canonical_frame_moments_vanish_exactly(self):
        moments = spherical_design_moments()
        for ell in range(1, 6):
            self.assertTrue(moments[ell]["vanishes"], f"degree {ell} survived")
            self.assertEqual(moments[ell]["q5_part"], (0, 0))
            self.assertEqual(moments[ell]["w_part"], (0, 0))

    def test_verify_returns_proof_record(self):
        proof = verify_spherical_design()
        self.assertEqual(proof["points"], 32)
        self.assertEqual(proof["design_degree"], 5)
        self.assertEqual(proof["proof_kind"], "legendre_frame_potential")

    def test_degraded_frame_triggers_governance(self):
        frame = list(truncated_icosahedron_frame())
        frame[5] = frame[0]  # structural degradation: duplicate direction
        with self.assertRaises(M32GovernanceError) as ctx:
            verify_spherical_design(tuple(frame))
        self.assertTrue(ctx.exception.moments)

    def test_off_orbit_frame_triggers_governance(self):
        frame = list(truncated_icosahedron_frame())
        frame[3] = (frame[3][0], frame[3][1], frame[3][0])  # wrong norm
        with self.assertRaises(M32GovernanceError):
            spherical_design_moments(tuple(frame))

    def test_topology_enforces_design_at_construction(self):
        topo = M32Topology()
        self.assertTrue(topo.connected())
        self.assertEqual(topo.lanes, 32)


class PhyllotaxisTests(unittest.TestCase):
    def test_slot_map_is_bijection(self):
        index = PhyllotaxisLaneIndex()
        self.assertEqual(sorted(index._slots), list(range(LANES)))

    def test_order_and_slot_are_inverse(self):
        index = PhyllotaxisLaneIndex()
        order = index.order()
        self.assertEqual(len(order), LANES)
        for lane in range(LANES):
            self.assertEqual(order[index.slot(lane)], lane)

    def test_golden_angle_first_insertions(self):
        # frac(0*phi)=0 ranks first; frac(13*phi)~0.034 ranks second.
        index = PhyllotaxisLaneIndex()
        self.assertEqual(index.order()[:2], (0, 13))

    def test_slot_bounds(self):
        index = PhyllotaxisLaneIndex()
        with self.assertRaises(ValueError):
            index.slot(-1)
        with self.assertRaises(ValueError):
            index.slot(32)


class LucasGateTests(unittest.TestCase):
    def test_ladder_indices_accepted(self):
        for index in LUCAS_EXECUTION_SCALE_INDICES:
            self.assertEqual(require_lucas_execution_scale(index), index)

    def test_non_ladder_indices_rejected(self):
        for bad in (7, 9, 11, 13, 32, 77, 0, -10):
            with self.assertRaises(LucasScaleError):
                require_lucas_execution_scale(bad)

    def test_non_integer_indices_rejected(self):
        for bad in ("12", 12.0, True, None):
            with self.assertRaises(LucasScaleError):
                require_lucas_execution_scale(bad)  # type: ignore[arg-type]

    def test_solver_scan_gates_scale_index(self):
        solver = M32SearchSolver()
        bits = "207fffff"  # trivial target: any digest wins
        with self.assertRaises(LucasScaleError):
            solver.scan(
                version=1,
                previous_hash="00" * 32,
                merkle_root="00" * 32,
                timestamp=1,
                bits=bits,
                budget=4,
                scale_index=7,
            )

    def test_solver_scan_admits_ladder_index_and_proves_sha256d(self):
        solver = M32SearchSolver()
        bits = "207fffff"
        result = solver.scan(
            version=1,
            previous_hash="00" * 32,
            merkle_root="00" * 32,
            timestamp=1,
            bits=bits,
            budget=64,
            scale_index=20,
        )
        self.assertTrue(result.valid)
        self.assertIsNotNone(result.found_nonce)
        target = compact_target(bits)
        from mla1517.mining.pow import build_header, check_pow

        header = build_header(1, "00" * 32, "00" * 32, 1, bits, result.found_nonce)
        self.assertTrue(check_pow(header, target))

    def test_lane_attempts_folded_through_phyllotaxis(self):
        solver = M32SearchSolver()
        solver.scan(
            version=1,
            previous_hash="00" * 32,
            merkle_root="00" * 32,
            timestamp=1,
            bits="1f7fffff",  # still easy enough to finish quickly
            budget=96,
            scale_index=10,
        )
        attempts = solver.lane_attempts()
        self.assertEqual(sum(attempts), 96)


class _FakeBridge:
    """Records the real ABI calls the sink must issue; performs no I/O."""

    def __init__(self):
        self.calls = []

    def stage_lane_mask(self, mask):
        self.calls.append(("stage_lane_mask", mask))

    def request_supervisor_commit(self):
        self.calls.append(("commit",))

    def stop(self):
        self.calls.append(("stop",))

    def start(self):
        self.calls.append(("start",))

    def reset_ring(self):
        self.calls.append(("reset_ring",))

    def last_error(self):
        return 0


class MMIOControlSinkTests(unittest.TestCase):
    def _sink(self):
        from mla1517.mining.coordinator import MMIOControlSink

        effects = {"throttle": [], "quarantine": [], "prune": []}
        sink = MMIOControlSink(
            _FakeBridge(),
            on_throttle=effects["throttle"].append,
            on_quarantine=effects["quarantine"].append,
            on_prune=effects["prune"].append,
        )
        return sink, effects

    def test_sever_and_flush_drive_real_mask_ops(self):
        sink, _ = self._sink()
        sink.sever_lane(parameters={}, evidence={})
        sink.flush_lane(job_id="j", parameters={}, evidence={})
        self.assertEqual(
            sink._bridge.calls,
            [("stage_lane_mask", 0), ("commit",), ("stage_lane_mask", 0xFFFFFFFF), ("commit",)],
        )

    def test_restart_restarts_device(self):
        sink, _ = self._sink()
        sink.restart_lane(parameters={}, evidence={})
        self.assertEqual(sink._bridge.calls, [("stop",), ("start",)])

    def test_backpressure_and_quarantine_reach_callbacks(self):
        sink, effects = self._sink()
        sink.apply_backpressure(parameters={}, evidence={})
        sink.quarantine_record(parameters={"record_id": "r1"}, evidence={})
        self.assertEqual(effects["throttle"], [True])
        self.assertEqual(effects["quarantine"], ["r1"])

    def test_ring_commands_reset_real_cursor(self):
        sink, _ = self._sink()
        sink.flush_persistence_ring(parameters={}, evidence={})
        sink.reset_cursor(parameters={}, evidence={})
        self.assertEqual(sink._bridge.calls, [("reset_ring",), ("reset_ring",)])

    def test_unsupported_resize_direction_fails_closed(self):
        sink, _ = self._sink()
        with self.assertRaises(RuntimeError):
            sink.resize_workgroup(parameters={"direction": "up"}, evidence={})


class CoordinatorEvidenceWiringTests(unittest.TestCase):
    """The live record path must feed observed evidence into TOE and the
    chooser — and never submit record state as a share."""

    def _coordinator(self):
        from mla1517.mining.coordinator import IntelligentPoolCoordinator
        from manifold_pool_coordinator import PoolEndpoint

        coord = IntelligentPoolCoordinator(
            [PoolEndpoint("127.0.0.1", 3333, "stub")],
            username="u",
            password="x",
        )
        job = SimpleNamespace(
            job_id="job-observed",
            params=("job-observed", "00" * 32, "cb1", "cb2"),
            received_at=1.0,
        )
        coord.client = SimpleNamespace(latest_job=lambda: job)
        return coord

    def test_cassini_fault_detects_torn_state(self):
        from mla1517.mining.coordinator import IntelligentPoolCoordinator

        good = struct.pack("<Q14I", 1, *([0] * 8), 1, 0, 0, 0, 0, 0)
        torn = struct.pack("<Q14I", 1, *([0] * 8), 7, 0, 0, 0, 0, 0)
        self.assertIsNone(IntelligentPoolCoordinator._cassini_fault(good))
        self.assertIn("invalid_cassini_seal", IntelligentPoolCoordinator._cassini_fault(torn))
        self.assertEqual(
            IntelligentPoolCoordinator._cassini_fault(b"short"),
            "state_not_64_bytes",
        )

    def test_observed_window_is_real_solver_coverage(self):
        coord = self._coordinator()
        window = coord._observed_candidate_window()
        self.assertEqual(len(window), 10 * LANES)
        self.assertEqual(len(set(window)), len(window))
        lanes = {coord.solver.topology.lane_for_nonce(n) for n in window}
        self.assertEqual(lanes, set(range(LANES)))

    def test_submit_record_runs_toe_heal_and_choose_without_share(self):
        import asyncio
        from mla1517.hardware import VaultRecord

        coord = self._coordinator()
        record = VaultRecord(
            node_id=3,
            sequence=1,
            state=struct.pack("<Q14I", 9, *([0] * 8), 1, 0, 0, 0, 0, 0),
        )
        accepted = asyncio.run(coord.submit_record(record))
        self.assertFalse(accepted)  # record state is never a proof
        self.assertIsNotNone(coord.last_toe_context)
        self.assertIsNotNone(coord.last_mining_decision)
        self.assertIsNotNone(coord.last_recovery_plan)
        self.assertEqual(coord.last_mining_decision.policy.candidate_ordering, "m32_lane_order")


if __name__ == "__main__":
    unittest.main()
