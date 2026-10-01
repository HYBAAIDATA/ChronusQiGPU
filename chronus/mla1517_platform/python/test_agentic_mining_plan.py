"""Agentic SearchPlan contract: Stratum-owned identity, leases, lookahead, learning.

Offline and deterministic. Live pool and hardware behaviour is covered only by
the voyage tests' fake pool; nothing here claims hardware evidence.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import time

import pytest

from agentic_fixtures import LANE_ORDER, Extranonce2, identity, make_plan, make_record
from chronus.mla1517.mining.agentic_controller import (
    MAX_STATE_BYTES,
    STATE_SCHEMA_VERSION,
    AgenticMiningController,
)
from chronus.mla1517.mining.nonce_lease import LeaseConflict
from chronus.mla1517.mining.scale_state import ScaleEvidence, ScaleState, ScaleStateClassifier
from chronus.mla1517.mining.search_plan import (
    ExecutionRecord,
    LeaseState,
    PlanSource,
    PoolOutcome,
    SearchPlan,
)

WORK_A = identity(1, fingerprint="fp-a")
WORK_B = identity(2, fingerprint="fp-b", job_id="job-b", clean_jobs=True)


def bound(work=WORK_A, **kwargs) -> AgenticMiningController:
    controller = AgenticMiningController(**kwargs)
    controller.bind_work(work)
    return controller


# ── SearchPlan contract ──────────────────────────────────────────────── #


class TestSearchPlanContract:
    def test_frozen(self):
        plan = make_plan(bound(), WORK_A)
        with pytest.raises(dataclasses.FrozenInstanceError):
            plan.window = 1  # type: ignore[misc]

    def test_evidence_refs_frozen(self):
        plan = make_plan(bound(), WORK_A, evidence_refs={"k": 1})
        with pytest.raises(TypeError):
            plan.evidence_refs["k"] = 2  # type: ignore[index]

    @pytest.mark.parametrize(
        "override",
        [
            {"lane_order": (0,) * 32},
            {"lane_order": tuple(range(31))},
            {"executor_route": "quantum_magic"},
            {"window": 0},
            {"generation": 0},
            {"pool_session_id": ""},
        ],
    )
    def test_invalid_fields_rejected(self, override):
        with pytest.raises(ValueError):
            make_plan(bound(), WORK_A, **override)

    def test_valid_only_for_exact_stratum_identity(self):
        plan = make_plan(bound(), WORK_A)
        assert plan.is_valid_for(WORK_A)
        assert not plan.is_valid_for(None)
        assert not plan.is_valid_for(identity(2, fingerprint="fp-a"))
        assert not plan.is_valid_for(identity(1, fingerprint="fp-target-changed"))
        assert not plan.is_valid_for(identity(1, fingerprint="fp-a", session="session-2"))

    def test_expired_plan_is_invalid(self):
        now = time.monotonic()
        plan = make_plan(bound(), WORK_A, created_at=now - 1, expires_at=now - 0.5)
        assert not plan.is_valid_for(WORK_A)


# ── Stratum identity is the only job truth ───────────────────────────── #


class TestStratumIdentity:
    def test_no_plan_admitted_before_stratum_identity(self):
        c = AgenticMiningController()
        assert c.admission_block_reason() == "NO_WORK_IDENTITY"
        assert c.plans_needed() == 0
        with pytest.raises(LeaseConflict):
            c.reserve_lease("p", 320, Extranonce2())

    def test_same_identity_rebind_is_idempotent(self):
        c = bound()
        plan = make_plan(c, WORK_A)
        assert c.submit_plan(plan)
        assert c.bind_work(WORK_A) is False
        assert c.queue_depth() == 1

    @pytest.mark.parametrize(
        "changed",
        [
            identity(2, fingerprint="fp-a"),
            identity(1, fingerprint="fp-a2", target_generation=2),
            identity(1, fingerprint="fp-a", session="session-2"),
        ],
        ids=["generation", "fingerprint", "session"],
    )
    def test_any_identity_change_invalidates_queue_and_leases(self, changed):
        c = bound()
        plans = [make_plan(c, WORK_A) for _ in range(2)]
        assert all(c.submit_plan(p) for p in plans)
        assert c.bind_work(changed) is True
        assert c.queue_depth() == 0
        assert c.telemetry.plans_invalidated == 2
        assert c.consume_plan() is None
        for plan in plans:
            with pytest.raises(LeaseConflict):
                c.begin_execution(plan)

    def test_clean_jobs_forces_invalidation_and_is_counted(self):
        c = bound()
        assert c.submit_plan(make_plan(c, WORK_A))
        c.bind_work(WORK_B)
        assert c.queue_depth() == 0
        assert c.telemetry.clean_job_invalidations == 1

    def test_plan_for_old_identity_rejected_at_submit(self):
        c = bound()
        old = make_plan(c, WORK_A)
        c.bind_work(WORK_B)
        assert c.submit_plan(old) is False
        assert c.telemetry.plans_stale == 1

    def test_clear_work_blocks_and_drains(self):
        c = bound()
        assert c.submit_plan(make_plan(c, WORK_A))
        c.clear_work("NO_CURRENT_JOB")
        assert c.queue_depth() == 0
        assert c.admission_block_reason() == "NO_CURRENT_JOB"
        assert c.snapshot()["work_identity"] is None


# ── Admission, queue bounds and leases ───────────────────────────────── #


class TestAdmission:
    def test_plan_without_lease_is_refused(self):
        c = bound()
        plan = make_plan(c, WORK_A)
        c.release_lease(plan.plan_id)
        assert c.submit_plan(plan) is False

    def test_plan_whose_range_differs_from_lease_is_refused(self):
        c = bound()
        plan = make_plan(c, WORK_A)
        forged = dataclasses.replace(plan, base_step=plan.base_step + 32)
        assert c.submit_plan(forged) is False

    def test_queue_full_releases_the_lease(self):
        c = bound(queue_depth=1)
        assert c.submit_plan(make_plan(c, WORK_A))
        overflow = make_plan(c, WORK_A)
        assert c.submit_plan(overflow) is False
        assert c._leases.get(overflow.plan_id).state is LeaseState.INVALIDATED
        assert c.queue_depth() == 1

    def test_plans_needed_respects_lookahead(self):
        c = bound(queue_depth=4, initial_lookahead=2)
        assert c.plans_needed() == 2
        c.submit_plan(make_plan(c, WORK_A))
        assert c.plans_needed() == 1

    def test_consumed_plan_executes_its_exact_lease(self):
        c = bound()
        plan = make_plan(c, WORK_A, window=100)
        c.submit_plan(plan)
        consumed = c.consume_plan()
        lease = c.begin_execution(consumed)
        assert (lease.start, lease.count, lease.extranonce2) == (
            plan.base_step,
            128,
            plan.extranonce2,
        )
        assert c.finish_execution(lease.lease_id, scanned=True)
        with pytest.raises(LeaseConflict):
            c.begin_execution(consumed)

    def test_consume_miss_reasons_are_explicit(self):
        c = AgenticMiningController()
        assert c.consume_plan() is None
        assert c.telemetry.last_consume_miss_reason == "precompute_unavailable"
        c.bind_work(WORK_A)
        assert c.consume_plan() is None
        assert c.telemetry.last_consume_miss_reason == "queue_empty"
        c.set_recovery_active(True)
        assert c.consume_plan() is None
        assert c.telemetry.last_consume_miss_reason == "recovery"


# ── Salamander gate ──────────────────────────────────────────────────── #


class TestRecoveryGate:
    def test_recovery_drains_speculation_and_closes_admission(self):
        c = bound()
        plans = [make_plan(c, WORK_A) for _ in range(2)]
        for p in plans:
            c.submit_plan(p)
        c.set_recovery_active(True)
        assert c.queue_depth() == 0
        assert c.plans_needed() == 0
        assert all(c._leases.get(p.plan_id).state is LeaseState.INVALIDATED for p in plans)
        with pytest.raises(LeaseConflict):
            c.reserve_lease("x", 320, Extranonce2())

    def test_clearing_recovery_requires_identity_revalidation(self):
        c = bound()
        c.set_recovery_active(True)
        c.set_recovery_active(False)
        assert c.admission_block_reason() == "REVALIDATION_REQUIRED"
        assert c.plans_needed() == 0
        c.bind_work(WORK_A)
        assert c.admission_block_reason() is None
        assert c.plans_needed() > 0

    def test_repeated_false_does_not_flap_state(self):
        c = bound()
        c.set_recovery_active(False)
        c.set_recovery_active(False)
        assert c.telemetry.agentic_state == "NEW_JOB"
        assert c.admission_block_reason() is None


# ── Adaptive lookahead ───────────────────────────────────────────────── #


class TestAdaptiveLookahead:
    def test_job_churn_shortens_lookahead(self):
        c = bound(queue_depth=4, initial_lookahead=3)
        for generation in range(2, 6):
            for _ in range(c.plans_needed()):
                c.submit_plan(make_plan(c, c.current_identity()))
            c.bind_work(identity(generation, fingerprint=f"fp-{generation}"))
        assert c.lookahead < 3
        assert "shrink" in c.telemetry.lookahead_change_reason

    def test_starvation_with_stable_jobs_grows_within_bound(self):
        c = bound(queue_depth=3, initial_lookahead=1)
        for _ in range(12):
            c.note_fallback("queue_empty")
        assert c.lookahead == 3
        assert c.lookahead <= c.snapshot()["lookahead_max"]

    def test_waste_ratio_is_invalidated_over_created(self):
        c = bound()
        assert c.precompute_waste_ratio is None
        for _ in range(2):
            c.submit_plan(make_plan(c, WORK_A))
        c.bind_work(WORK_B)
        assert c.precompute_waste_ratio == 1.0

    def test_recovery_means_zero_speculative_expansion(self):
        c = bound(queue_depth=3, initial_lookahead=1)
        c.set_recovery_active(True)
        for _ in range(12):
            c.note_fallback("queue_empty")
        assert c.plans_needed() == 0


# ── Learning only from literal pool outcomes ─────────────────────────── #


class TestOutcomeLearning:
    def _executed(self, c):
        plan = make_plan(c, WORK_A)
        c.submit_plan(plan)
        return c.consume_plan()

    @pytest.mark.parametrize("outcome", [PoolOutcome.ACCEPTED, PoolOutcome.REJECTED])
    def test_literal_pool_outcomes_train(self, outcome):
        c = bound()
        c.record_outcome(make_record(self._executed(c), outcome))
        assert c.telemetry.learning_update_applied
        assert list(c._lead_history["flat_exhaustive"]) == [outcome is PoolOutcome.ACCEPTED]

    @pytest.mark.parametrize(
        "outcome",
        [PoolOutcome.OUTCOME_UNKNOWN, PoolOutcome.NOT_SUBMITTED, PoolOutcome.NO_CANDIDATE],
    )
    def test_non_pool_outcomes_never_train(self, outcome):
        c = bound()
        c.record_outcome(make_record(self._executed(c), outcome))
        assert not c.telemetry.learning_update_applied
        assert c._lead_history == {}

    def test_record_cannot_claim_acceptance_without_pool_response(self):
        plan = make_plan(bound(), WORK_A)
        with pytest.raises(ValueError):
            dataclasses.replace(make_record(plan), pool_accepted=1)
        with pytest.raises(ValueError):
            dataclasses.replace(make_record(plan, PoolOutcome.OUTCOME_UNKNOWN), pool_rejected=1)

    def test_fallback_record_carries_reason_and_no_plan_id(self):
        plan = make_plan(bound(), WORK_A)
        record = dataclasses.replace(
            make_record(plan),
            plan_id=None,
            plan_source=PlanSource.BASELINE_FALLBACK,
            plan_fallback_reason="queue_empty",
        )
        assert record.plan_source is PlanSource.BASELINE_FALLBACK
        with pytest.raises(ValueError):
            dataclasses.replace(record, plan_fallback_reason=None)
        with pytest.raises(ValueError):
            dataclasses.replace(make_record(plan), plan_id=None)

    def test_executor_idle_is_measured(self):
        c = bound()
        c.consume_plan(timeout_ms=5)
        assert c.telemetry.executor_idle_waiting_for_plan_ms > 0


# ── Scale state (unchanged classifier) ───────────────────────────────── #


def _evidence(**overrides) -> ScaleEvidence:
    base = dict(
        kernel_latency_ms=10.0,
        latency_bound_ms=100.0,
        temperature_c=40.0,
        thermal_limit_c=85.0,
        queue_depth=0,
        executor_idle_ms=50.0,
        recovery_active=False,
        device_errors=0,
    )
    base.update(overrides)
    return ScaleEvidence(**base)


class TestScaleStateClassifier:
    @pytest.mark.parametrize(
        "overrides,state,word",
        [
            ({}, ScaleState.UNDER_UTILISED, "increase"),
            (
                {"kernel_latency_ms": 110.0, "temperature_c": 60.0, "executor_idle_ms": 0.0},
                ScaleState.SATURATED,
                "hold",
            ),
            (
                {"kernel_latency_ms": 250.0, "temperature_c": 90.0, "executor_idle_ms": 0.0},
                ScaleState.OVERLOADED,
                None,
            ),
            (
                {"latency_bound_ms": 0.0, "thermal_limit_c": 0.0},
                ScaleState.UNCERTAIN,
                "hold",
            ),
            ({"recovery_active": True}, ScaleState.OVERLOADED, None),
            ({"device_errors": 3, "executor_idle_ms": 0.0}, ScaleState.OVERLOADED, None),
            (
                {
                    "kernel_latency_ms": 50.0,
                    "temperature_c": 50.0,
                    "executor_idle_ms": 0.0,
                    "prior_throughput": 1000.0,
                    "current_throughput": 1001.0,
                },
                ScaleState.SATURATED,
                None,
            ),
        ],
    )
    def test_classification(self, overrides, state, word):
        result = ScaleStateClassifier().classify(_evidence(**overrides))
        assert result.state == state
        if word:
            assert word in result.recommendation

    def test_controller_recovery_overrides_classification(self):
        c = bound()
        c.set_recovery_active(True)
        state = c.classify_scale(
            kernel_latency_ms=10.0,
            latency_bound_ms=100.0,
            temperature_c=40.0,
            thermal_limit_c=85.0,
        )
        assert state == ScaleState.OVERLOADED


# ── Persistence: history only, never work ────────────────────────────── #


def _learned_controller() -> AgenticMiningController:
    c = bound()
    for outcome in (PoolOutcome.ACCEPTED, PoolOutcome.REJECTED, PoolOutcome.ACCEPTED):
        plan = make_plan(c, WORK_A, policy="m32_structured")
        c.submit_plan(plan)
        c.record_outcome(make_record(c.consume_plan(), outcome))
    return c


def _write_envelope(path: pathlib.Path, body: dict, *, checksum: str | None = None) -> None:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    path.write_text(
        json.dumps(
            {
                "schema_version": STATE_SCHEMA_VERSION,
                "body": body,
                "sha256": checksum or hashlib.sha256(canonical.encode()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )


class TestPolicyPersistence:
    def test_round_trip_restores_history_only(self, tmp_path):
        state = tmp_path / "agentic.json"
        original = _learned_controller()
        assert original.save_state(state)
        restored = AgenticMiningController()
        assert restored.load_state(state)
        assert list(restored._lead_history["m32_structured"]) == [True, False, True]
        assert restored.snapshot()["historical_binding_epoch"] >= 1
        assert restored.current_identity() is None
        assert restored.admission_block_reason() == "NO_WORK_IDENTITY"

    def test_persisted_file_contains_no_work(self, tmp_path):
        state = tmp_path / "agentic.json"
        _learned_controller().save_state(state)
        text = state.read_text(encoding="utf-8")
        for forbidden in ("fp-a", "session-1", "job-a", "extranonce", "plan_id", "target"):
            assert forbidden not in text

    def test_no_leftover_tmp_file(self, tmp_path):
        state = tmp_path / "agentic.json"
        _learned_controller().save_state(state)
        assert [p.name for p in tmp_path.iterdir()] == ["agentic.json"]

    @pytest.mark.parametrize(
        "writer",
        [
            lambda p: p.write_text("{not json", encoding="utf-8"),
            lambda p: p.write_text(
                json.dumps({"version": 1, "generation": 3, "lead_history": {}}), encoding="utf-8"
            ),
            lambda p: _write_envelope(
                p, {"historical_epoch": 1, "lead_history": {"x": [True]}}, checksum="0" * 64
            ),
            lambda p: _write_envelope(
                p,
                {
                    "historical_epoch": 1,
                    "lead_history": {},
                    "job_fingerprint": "fp-a",
                },
            ),
            lambda p: _write_envelope(p, {"historical_epoch": 1, "lead_history": {"x": [1]}}),
            lambda p: _write_envelope(p, {"historical_epoch": -1, "lead_history": {}}),
            lambda p: p.write_bytes(b" " * (MAX_STATE_BYTES + 1)),
        ],
        ids=[
            "corrupt_json",
            "legacy_schema",
            "checksum_mismatch",
            "work_field_injected",
            "non_bool_history",
            "negative_epoch",
            "oversize",
        ],
    )
    def test_defective_state_yields_clean_baseline(self, tmp_path, writer):
        state = tmp_path / "agentic.json"
        writer(state)
        c = AgenticMiningController()
        c._lead_history = {"stale": []}
        assert c.load_state(state) is False
        assert c._lead_history == {}
        assert c.snapshot()["historical_binding_epoch"] == 0
        c.bind_work(WORK_A)
        assert c.submit_plan(make_plan(c, WORK_A))

    def test_missing_file_is_not_an_error(self, tmp_path):
        assert AgenticMiningController().load_state(tmp_path / "absent.json") is False

    def test_history_bounded_on_load(self, tmp_path):
        state = tmp_path / "agentic.json"
        _write_envelope(state, {"historical_epoch": 0, "lead_history": {"p": [True] * 50}})
        c = AgenticMiningController()
        assert c.load_state(state)
        assert len(c._lead_history["p"]) == 20


class TestExecutionRecordContract:
    def test_planned_and_actual_window_stay_separate(self):
        plan = make_plan(bound(), WORK_A, window=640)
        record = dataclasses.replace(make_record(plan), actual_window=320)
        assert (record.planned_window, record.actual_window) == (640, 320)

    def test_rejects_negative_hash_count(self):
        plan = make_plan(bound(), WORK_A)
        with pytest.raises(ValueError):
            dataclasses.replace(make_record(plan), hash_count=-1)

    def test_lane_order_is_full_permutation(self):
        plan = make_plan(bound(), WORK_A)
        with pytest.raises(ValueError):
            dataclasses.replace(make_record(plan), lane_order=LANE_ORDER[:-1])


def test_record_type_is_shared_contract():
    assert ExecutionRecord.__module__ == SearchPlan.__module__
