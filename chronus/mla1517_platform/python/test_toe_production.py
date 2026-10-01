"""Reconciled TOE production frame and five-intelligence plane on a real TOE context."""

from __future__ import annotations

import copy
import dataclasses
import unittest
from types import SimpleNamespace

from manifold_pool_coordinator import StratumJob
from chronus.mla1517.mining import toe_capabilities, toe_decision
from chronus.mla1517.mining.chooser import MiningIntelligenceChooser
from chronus.mla1517.mining.search_plan import SearchPlan
from chronus.mla1517.mining.solver import M32SearchSolver
from chronus.mla1517.mining.toe_adapter import TOEMiningAdapter
from chronus.mla1517.mining.toe_capabilities import TOEMiningCapabilityPlane
from chronus.mla1517.mining.toe_decision import TOEDecisionFrameUnavailable, build_toe_decision_frame
from chronus.mla1517.mining.toe_signal import build_toe_signal
from toe.bridge import TOEBridge

_CONTEXT = None


def _context():
    global _CONTEXT
    if _CONTEXT is None:
        job = StratumJob(
            job_id="job-real-observation",
            params=("job-real-observation", "prevhash", "coinbase1", "coinbase2"),
            received_at=1.0,
        )
        _CONTEXT = TOEMiningAdapter(TOEBridge()).analyse(
            job=job, state=bytes(range(64)), node_id=7, sequence=19
        )
    return _CONTEXT


def _mutated(mutate):
    ctx = _context()
    result = copy.deepcopy(dict(ctx.result))
    mutate(result)
    return SimpleNamespace(
        result=result,
        execution_evidence=dict(ctx.execution_evidence),
        job_id=ctx.job_id,
        node_id=ctx.node_id,
        sequence=ctx.sequence,
    )


def _plan(frame, **overrides) -> SearchPlan:
    base = dict(
        job_fingerprint="fp",
        pool_session_id="session",
        generation=1,
        base_step=0,
        window=1344,
        extranonce2="00000000",
        lane_order=tuple(range(32)),
        preferred_face=0,
        dispatch_breadth=320,
        executor_route="cpu_reference",
        policy_id="m32",
        evidence_refs=dict(frame.evidence_refs()),
        created_at=1.0,
    )
    base.update(overrides)
    return SearchPlan(**base)


class FrameTests(unittest.TestCase):
    def test_real_toe_context_yields_a_valid_bound_frame(self):
        frame = build_toe_decision_frame(_context())
        self.assertTrue(frame.is_valid())
        self.assertTrue(frame.exact_state)
        self.assertTrue(frame.exact_field)
        self.assertEqual(frame.execution_backend, "cpu-exact")
        self.assertEqual(set(frame.surface_digests), set(frame.steering_surfaces + frame.audit_only_surfaces))
        self.assertEqual(frame.frame_digest, build_toe_decision_frame(_context()).frame_digest)
        refs = frame.evidence_refs()
        self.assertEqual(refs["toe_frame_digest"], frame.frame_digest)
        self.assertEqual(frame.advisory_summary()["frame_digest"], frame.frame_digest)

    def test_audit_only_surfaces_cannot_steer(self):
        frame = build_toe_decision_frame(_context())
        self.assertNotIn("causal_analysis", frame.steering_surfaces)
        self.assertNotIn("causal_ladder", frame.steering_surfaces)

    def test_tampering_breaks_validity(self):
        frame = build_toe_decision_frame(_context())
        self.assertFalse(dataclasses.replace(frame, combined_confidence=0.0123).is_valid())

    def test_stricter_validation_from_the_reconciliation(self):
        def not_normalised(r):
            r["exact_tensor"] = {**r["exact_tensor"], "normalized_exact": False}

        def digests_disagree(r):
            r["toe_expansion"] = {**r["toe_expansion"], "input_digest": "0" * 64}

        def missing_digest(r):
            r["exact_tensor"] = {**r["exact_tensor"], "input_digest": ""}
            r["toe_expansion"] = {**r["toe_expansion"], "input_digest": ""}

        def refused_scale(r):
            program = [dict(p) for p in r["toe_expansion"]["scale_program"]]
            program[0]["accepted"] = False
            r["toe_expansion"] = {**r["toe_expansion"], "scale_program": program}

        def surface_missing(r):
            r["causal_ladder"] = {"available": False}

        for mutate in (not_normalised, digests_disagree, missing_digest, refused_scale, surface_missing):
            with self.subTest(mutate.__name__):
                with self.assertRaises(TOEDecisionFrameUnavailable):
                    build_toe_decision_frame(_mutated(mutate))

    def test_consensus_vocabulary_is_rejected(self):
        def inject(r):
            r["state_tomography"] = {**r["state_tomography"], "nonce": 42}

        with self.assertRaises(Exception):
            build_toe_decision_frame(_mutated(inject))

    def test_parallel_design_names_are_one_implementation(self):
        self.assertIs(toe_decision.TOEProductionFrame, toe_decision.TOEMiningDecisionFrame)
        self.assertIs(toe_decision.build_toe_production_frame, build_toe_decision_frame)
        self.assertIs(toe_decision.TOEFrameUnavailable, TOEDecisionFrameUnavailable)
        self.assertIs(toe_capabilities.TOEFiveIntelligencePlane, TOEMiningCapabilityPlane)


class CapabilityPlaneTests(unittest.TestCase):
    def setUp(self):
        self.frame = build_toe_decision_frame(_context())
        self.signal = build_toe_signal(_context())
        self.plane = TOEMiningCapabilityPlane()

    def test_bound_signal_may_advise_ordering_and_missing_sensors_stay_unavailable(self):
        snap = self.plane.observe(frame=self.frame, signal=self.signal, candidate_window=range(0, 64))
        self.assertTrue(snap.geometric["action_available"])
        self.assertEqual(snap.geometric["preferred_face"], self.signal.face_bias)
        self.assertFalse(snap.plastic["action_available"])
        self.assertFalse(snap.causal["action_available"])
        self.assertFalse(snap.quantum["treasury_action_available"])
        self.assertEqual(len(snap.receipt_digest), 64)

    def test_signal_from_another_observation_cannot_steer(self):
        foreign = dataclasses.replace(self.signal, sequence=self.signal.sequence + 1)
        snap = self.plane.observe(frame=self.frame, signal=foreign, candidate_window=range(0, 64))
        self.assertFalse(snap.geometric["action_available"])
        self.assertIsNone(snap.geometric["preferred_face"])

    def test_observe_plan_requires_the_plan_to_name_this_frame(self):
        receipt = self.plane.observe_plan(frame=self.frame, signal=self.signal, plan=_plan(self.frame))
        self.assertEqual(receipt.geometric["leased_window"], 1344)
        with self.assertRaises(ValueError):
            self.plane.observe_plan(
                frame=self.frame, signal=self.signal, plan=_plan(self.frame, evidence_refs={})
            )

    def test_measured_telemetry_unlocks_plastic_advice(self):
        snap = self.plane.observe(
            frame=self.frame,
            signal=self.signal,
            candidate_window=range(0, 64),
            telemetry={"temperature_c": 61.0, "power_w": 14.0, "measured_hashrate": 2.6e7},
        )
        self.assertTrue(snap.plastic["action_available"])
        self.assertEqual(snap.plastic["authority"], "compute_profile_advisory")


class ChooserWiringTests(unittest.TestCase):
    def test_frame_identity_gates_the_lane_bias(self):
        frame = build_toe_decision_frame(_context())
        signal = build_toe_signal(_context())
        self.assertTrue(MiningIntelligenceChooser._toe_binding_valid(signal, frame))
        other = dataclasses.replace(signal, job_id="another-job")
        self.assertFalse(MiningIntelligenceChooser._toe_binding_valid(other, frame))

    def test_lane_bias_can_be_cleared_between_jobs(self):
        solver = M32SearchSolver()
        solver.set_lane_start_offset(5)
        self.assertEqual(solver.get_lane_start_offset(), 5)
        solver.clear_lane_start_offset()
        self.assertEqual(solver.get_lane_start_offset(), 0)


if __name__ == "__main__":
    unittest.main()
