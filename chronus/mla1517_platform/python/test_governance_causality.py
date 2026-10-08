"""Salamander recovery authority, causal coordinates, quality channels, router fixes."""

from __future__ import annotations

import asyncio
import dataclasses
import json

import pytest

import control_api
from chronus.mla1517.mining.causal import CausalCoordinate, CausalLedger, load_jsonl
from chronus.mla1517.mining.coordinator import MMIOControlSink
from chronus.mla1517.mining.execution_router import (
    NONCE_ORDER_M32,
    NONCE_ORDER_SEQUENTIAL,
    ExecutionRouter,
)
from chronus.mla1517.mining.quality import QualityLedger
from chronus.mla1517.mining.recovery_authority import RecoveryGovernor, RecoveryState
from chronus.mla1517.mining.search_plan import (
    CompletionState,
    ExecutionRecord,
    FallbackReason,
    LeaseState,
    NonceLease,
    PlanSource,
    PoolOutcome,
    SearchPlan,
)
from chronus.mla1517.mining.self_healing_agent import RecoveryAction, RecoveryCommand, RecoveryPlan
from salamander_engine import SalamanderEngine
from test_agentic_voyages import FakeChain, coordinator

LANES = tuple(range(32))
SESSION = CausalCoordinate(pool_session_id="s1", generation=4, job_fingerprint="fp")


# ── Causal coordinate system ─────────────────────────────────────────── #


def _voyage(ledger: CausalLedger, plan: str, submission: str | None) -> None:
    ledger.record("identity_bound", SESSION)
    planned = SESSION.extend(plan_id=plan, lease_id=plan)
    ledger.record("plan_created", planned)
    executed = planned.extend(execution_id=f"x-{plan}")
    ledger.record("execution_started", executed)
    if submission:
        found = executed.extend(candidate_id=f"c-{plan}")
        ledger.record("candidate_found", found)
        ledger.record("submission_sent", found.extend(submission_id=submission))


class TestCausalLedger:
    def test_trace_returns_the_full_ancestry_of_a_submission(self):
        ledger = CausalLedger()
        _voyage(ledger, "p1", "sub-1")
        _voyage(ledger, "p2", None)
        kinds = [e.kind for e in ledger.trace(submission_id="sub-1")]
        assert kinds == [
            "identity_bound",
            "plan_created",
            "execution_started",
            "candidate_found",
            "submission_sent",
            "identity_bound",
        ]
        assert all(
            e.coordinate.plan_id in (None, "p1") for e in ledger.trace(submission_id="sub-1")
        )

    def test_unknown_id_traces_to_nothing(self):
        ledger = CausalLedger()
        _voyage(ledger, "p1", "sub-1")
        assert ledger.trace(submission_id="nope") == []

    def test_unknown_axis_is_refused(self):
        with pytest.raises(ValueError):
            SESSION.extend(nonce_luck=1)

    def test_ledger_is_bounded(self):
        ledger = CausalLedger(capacity=5)
        for index in range(20):
            ledger.record("tick", SESSION, index=index)
        assert [e.detail["index"] for e in ledger.events()] == [15, 16, 17, 18, 19]

    def test_jsonl_mirror_replays_and_rotates(self, tmp_path):
        path = tmp_path / "causal.jsonl"
        ledger = CausalLedger(path=path, max_file_bytes=10_000)
        _voyage(ledger, "p1", "sub-1")
        replayed = load_jsonl(path.read_text(encoding="utf-8").splitlines())
        assert [e.kind for e in replayed] == [e.kind for e in ledger.events()]
        assert replayed[-1].coordinate.submission_id == "sub-1"
        for _ in range(200):
            ledger.record("filler", SESSION, blob="x" * 100)
        assert (tmp_path / "causal.jsonl.1").exists()
        assert path.stat().st_size < 10_000 + 1_000


# ── Recovery governor ────────────────────────────────────────────────── #


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class TestRecoveryGovernor:
    def test_hold_only_is_not_a_recovery(self):
        assert RecoveryGovernor().propose(["HOLD"], "healthy") is None

    def test_dispatch_ack_then_verified_by_healthy_observation(self):
        gov = RecoveryGovernor()
        record = gov.propose(["SEVER_LANE"], "cassini fault")
        gov.dispatch(record, [("SEVER_LANE", lambda: "SEVER_LANE")], ack=lambda: True)
        assert record.state is RecoveryState.ACKED
        assert gov.mode == "RECOVERING" and gov.freezes_speculation
        assert gov.active_recovery_id() == record.recovery_id
        gov.observe(healthy=True)
        assert record.state is RecoveryState.VERIFIED
        assert gov.mode == "NORMAL" and not gov.freezes_speculation

    def test_nack_fails_and_faults_until_healthy(self):
        gov = RecoveryGovernor()
        record = gov.propose(["FLUSH_LANE"], "stale")
        gov.dispatch(record, [("FLUSH_LANE", lambda: "FLUSH_LANE")], ack=lambda: False)
        assert record.state is RecoveryState.FAILED
        assert gov.mode == "FAULTED" and gov.freezes_speculation
        gov.observe(healthy=True)
        assert gov.mode == "NORMAL"

    def test_persistent_unhealth_fails_the_recovery(self):
        gov = RecoveryGovernor(fail_after=2)
        record = gov.propose(["RESTART_LANE"], "device error")
        gov.dispatch(record, [("RESTART_LANE", lambda: "RESTART_LANE")])
        gov.observe(healthy=False)
        assert record.state is RecoveryState.DISPATCHED
        gov.observe(healthy=False)
        assert record.state is RecoveryState.FAILED

    def test_dispatch_error_is_recorded_and_propagates(self):
        gov = RecoveryGovernor()
        record = gov.propose(["RESTART_LANE"], "x")

        def boom():
            raise RuntimeError("bridge gone")

        with pytest.raises(RuntimeError):
            gov.dispatch(record, [("RESTART_LANE", boom)])
        assert record.state is RecoveryState.FAILED and "bridge gone" in record.failure

    def test_lane_mask_writes_defer_to_a_live_salamander(self):
        clock = Clock()
        gov = RecoveryGovernor(clock=clock, salamander_ttl_s=10)
        gov.external_mode("NORMAL")
        writes = []
        record = gov.propose(["SEVER_LANE", "RESTART_LANE"], "fault")
        gov.dispatch(
            record,
            [
                ("SEVER_LANE", lambda: writes.append("mask") or "SEVER_LANE"),
                ("RESTART_LANE", lambda: writes.append("restart") or "RESTART_LANE"),
            ],
        )
        assert writes == ["restart"]
        assert record.deferred == ["SEVER_LANE"]
        clock.now += 30  # supervisor went quiet: the miner owns the mask again
        assert not gov.defers("SEVER_LANE")

    def test_external_recovery_is_tracked_and_verified(self):
        events = []
        gov = RecoveryGovernor(on_event=lambda kind, rec: events.append((kind, rec.state)))
        gov.external_mode("RECOVERING", "salamander:1")
        assert gov.mode == "RECOVERING"
        gov.external_mode("NORMAL", "salamander:1")
        assert gov.mode == "NORMAL"
        assert ("recovery_verified", RecoveryState.VERIFIED) in events

    def test_required_authorization_denial_prevents_actuator_call(self):
        writes = []

        def authorizer(record, command, target):
            return {
                "allowed": False,
                "reason": "POLICY_DENIED",
                "authorization_evidence_id": "auth-denied",
                "authorization_version_id": "fv-denied",
                "policy_version": "policy-v1",
            }

        gov = RecoveryGovernor(
            recovery_authorizer=authorizer,
            require_authorization=True,
        )
        record = gov.propose(["RESTART_LANE"], "device error")
        with pytest.raises(PermissionError, match="POLICY_DENIED"):
            gov.dispatch(
                record,
                [("RESTART_LANE", lambda: writes.append("ran") or "RESTART_LANE")],
            )
        assert writes == []
        assert record.state is RecoveryState.FAILED
        assert record.authorizations[-1]["allowed"] is False
        assert record.authorizations[-1]["evidence_id"] == "auth-denied"

    def test_required_authorization_is_bound_before_actuation(self):
        order = []

        def authorizer(record, command, target):
            order.append(("authorize", record.recovery_id, command, target))
            return {
                "allowed": True,
                "reason": "ALLOWED",
                "authorization_evidence_id": "auth-1",
                "authorization_version_id": "fv-1",
                "policy_version": "policy-v1",
            }

        gov = RecoveryGovernor(
            recovery_authorizer=authorizer,
            require_authorization=True,
            recovery_target="chronus.execution",
        )
        record = gov.propose(["RESTART_LANE"], "device error")
        gov.dispatch(
            record,
            [("RESTART_LANE", lambda: order.append(("actuate",)) or "RESTART_LANE")],
        )
        assert order[0][0] == "authorize"
        assert order[1][0] == "actuate"
        assert record.target == "chronus.execution"
        assert record.authorizations[-1]["evidence_id"] == "auth-1"

    def test_unknown_mode_refused(self):
        with pytest.raises(ValueError):
            RecoveryGovernor().external_mode("PANIC")


# ── Quality channels ─────────────────────────────────────────────────── #


def _record(**overrides) -> ExecutionRecord:
    base = dict(
        plan_id="p",
        job_fingerprint="fp",
        policy_id="m32",
        planned_window=128,
        actual_window=128,
        device_used="cpu_reference",
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
    )
    base.update(overrides)
    return ExecutionRecord(**base)


def test_quality_channels_stay_separate_and_unknown_stays_unknown():
    ledger = QualityLedger()
    ledger.observe(_record())
    ledger.observe(
        _record(pool_outcome=PoolOutcome.ACCEPTED, pool_accepted=1, locally_valid_shares=1)
    )
    ledger.observe(_record(recovery_event=True, actual_window=64))
    snap = ledger.snapshot()["m32"]
    assert set(snap) == {"execution", "search", "network", "recovery", "thermal"}
    assert snap["execution"]["hashes_per_second_mean"] == pytest.approx(12800)
    assert snap["search"]["completion_ratio_mean"] == pytest.approx((1 + 1 + 0.5) / 3)
    assert snap["network"]["accept_rate"] == 1.0
    assert snap["recovery"]["events"] == 1
    assert snap["thermal"]["temperature_c_mean"] is None


def test_accept_rate_is_unknown_without_pool_answers():
    ledger = QualityLedger()
    ledger.observe(_record(pool_outcome=PoolOutcome.OUTCOME_UNKNOWN))
    assert ledger.snapshot()["m32"]["network"]["accept_rate"] is None


# ── Router fixes ─────────────────────────────────────────────────────── #


class RecordingHasher:
    backend = "opencl:gpu"
    device = "Fake GPU"
    vendor = "Fake"
    grind_batch = 1_048_575
    m32_window_max = 4096
    launches = 0
    kernel_ms = 0.0
    k_gold = k_range = k_m32 = object()

    def __init__(self) -> None:
        self.calls = []

    def grind_target_m32(self, header, target_be, base, lanes, count):
        self.calls.append(("m32", target_be, base, tuple(lanes), count))
        self.launches += 1
        return None, None, count

    def grind_target_range(self, header, target_be, base, count):
        self.calls.append(("range", target_be, base, count))
        self.launches += 1
        return None, None, count

    def grind_target_gold(self, header, target_be, count):
        self.calls.append(("gold", target_be, count))
        return None, None, count, []


def _plan(route: str, **overrides) -> SearchPlan:
    fields = dict(
        job_fingerprint="fp",
        pool_session_id="s",
        generation=1,
        base_step=4096,
        window=96,
        extranonce2="00",
        lane_order=tuple(reversed(LANES)),
        preferred_face=0,
        dispatch_breadth=96,
        executor_route=route,
        policy_id="m32",
        evidence_refs={},
        created_at=1.0,
    )
    fields.update(overrides)
    return SearchPlan(**fields)


def _router(hasher, cpu_calls=None):
    def cpu(header, target, start, count):
        if cpu_calls is not None:
            cpu_calls.append((start, count))
        return None, None, count

    return ExecutionRouter(hasher, cpu, nonce_order=lambda _p: NONCE_ORDER_M32)


def test_device_receives_big_endian_target_and_exact_leased_range():
    hasher = RecordingHasher()
    target_le = (0x1234).to_bytes(32, "little")
    rec, _ = _router(hasher).execute_plan(_plan("opencl_m32"), bytes(80), target_le)
    kind, target_be, base, lanes, count = hasher.calls[0]
    assert (kind, base, count) == ("m32", 4096, 96)
    assert int.from_bytes(target_be, "big") == 0x1234
    assert lanes == tuple(reversed(LANES))
    assert rec.executed_nonce_order == NONCE_ORDER_M32


def test_range_route_records_sequential_order():
    hasher = RecordingHasher()
    rec, _ = _router(hasher).execute_plan(_plan("opencl_range"), bytes(80), bytes(32))
    assert hasher.calls[0][0] == "range" and hasher.calls[0][2] == 4096
    assert rec.executed_nonce_order == NONCE_ORDER_SEQUENTIAL


def test_recorded_cpu_fallback_really_runs_on_cpu():
    hasher = RecordingHasher()
    hasher.k_m32 = None
    cpu_calls = []
    rec, _ = _router(hasher, cpu_calls).execute_plan(_plan("opencl_m32"), bytes(80), bytes(32))
    assert rec.executed_route == "cpu_reference"
    assert rec.fallback_reason == FallbackReason.KERNEL_UNAVAILABLE.value
    assert hasher.calls == [] and cpu_calls == [(4096, 96)]


def test_golden_stride_cannot_execute_a_leased_interval():
    hasher = RecordingHasher()
    plan = _plan("opencl_gold")
    lease = NonceLease("l", plan.generation, plan.plan_id, plan.base_step, plan.window)
    rec, cand = _router(hasher).execute_plan(plan, bytes(80), bytes(32), lease=lease)
    assert rec.completion_state is CompletionState.REFUSED
    assert cand is None and hasher.calls == []


def test_baseline_plan_is_routed_with_its_reason():
    plan = _plan(
        "cpu_reference",
        source=PlanSource.BASELINE_FALLBACK,
        plan_fallback_reason="queue_empty",
    )
    rec, _ = _router(RecordingHasher()).execute_plan(plan, bytes(80), bytes(32))
    assert rec.plan_source is PlanSource.BASELINE_FALLBACK
    assert rec.plan_id is None and rec.plan_fallback_reason == "queue_empty"
    with pytest.raises(ValueError):
        _plan("cpu_reference", source=PlanSource.BASELINE_FALLBACK)
    with pytest.raises(ValueError):
        _plan("cpu_reference", plan_fallback_reason="nope")


def test_reserved_lease_contract_is_honoured():
    plan = _plan("cpu_reference")
    lease = NonceLease("l", plan.generation, plan.plan_id, plan.base_step, plan.window)
    rec, _ = _router(RecordingHasher()).execute_plan(plan, bytes(80), bytes(32), lease=lease)
    assert rec.completion_state is CompletionState.COMPLETE
    done = lease.transition(LeaseState.COMPLETE)
    rec, _ = _router(RecordingHasher()).execute_plan(plan, bytes(80), bytes(32), lease=done)
    assert rec.completion_state is CompletionState.REFUSED


# ── Salamander supervisor reporting ──────────────────────────────────── #


class _Bridge:
    def __init__(self) -> None:
        self.masks = []

    def stage_lane_mask(self, mask):
        self.masks.append(mask)

    def stage_polyhedral_mask(self, mask):
        self.masks.append(("poly", mask))

    def request_supervisor_commit(self):
        pass

    def supervisor_commit_ack(self):
        return True

    def stop(self):
        pass

    def start(self):
        pass

    def reset_ring(self):
        pass

    def last_error(self):
        return 0


def _engine(tmp_path, actions_by_step):
    engine = SalamanderEngine(
        _Bridge(),
        telemetry_path=tmp_path / "missing-telemetry",
        data_dir=tmp_path,
        enabled=True,
        governance_enabled=False,
    )
    engine.policy = "none"
    steps = iter(actions_by_step)
    engine.mclaren.step = lambda *a, **k: next(steps)
    engine._imbalanced = lambda cursors: False
    reports = []
    engine.mode_reporter = lambda payload: reports.append(dict(payload)) or True
    return engine, reports


def test_salamander_opens_and_verifies_a_recovery(tmp_path):
    engine, reports = _engine(tmp_path, [["sever:3"], ["sever:4"], [], []])
    first = engine.step(now_ms=0)
    assert first["mode"] == "RECOVERING" and first["recovery_id"].startswith("salamander:")
    engine.step(now_ms=100)
    closing = engine.step(now_ms=200)
    assert closing["mode"] == "NORMAL" and closing["recovery_id"] == first["recovery_id"]
    assert [r["mode"] for r in reports] == ["RECOVERING", "NORMAL"]
    assert reports[-1]["recovery_id"] == first["recovery_id"]
    assert engine.recovery_id is None
    engine.step(now_ms=300)
    assert len(reports) == 2  # no chatter inside the keepalive interval


def test_salamander_keepalive_proves_it_is_alive(tmp_path):
    engine, reports = _engine(tmp_path, [[], [], []])
    engine.step(now_ms=0)
    engine.step(now_ms=1000)
    engine.step(now_ms=2500)
    assert [r["mode"] for r in reports] == ["NORMAL", "NORMAL"]


# ── Coordinator: control socket, single writer, evidence ─────────────── #


def _action(command: RecoveryCommand) -> RecoveryAction:
    return RecoveryAction(
        command=command,
        reason="test fault",
        observed_at_ns=1,
        source_sequence=1,
        job_id="job",
        parameters={},
        evidence={},
    )


def _wired(bridge):
    coord = coordinator(1, FakeChain())
    coord._bridge = bridge
    coord._control_sink = MMIOControlSink(bridge, on_throttle=coord._set_throttled)
    return coord


def test_control_socket_mode_report_governs_the_miner():
    coord = _wired(_Bridge())
    reply = asyncio.run(
        coord._handle_control_request(
            {"op": "salamander_mode", "mode": "RECOVERING", "recovery_id": "salamander:9"}
        )
    )
    assert reply == {"status": "ok", "mode": "RECOVERING"}
    assert coord.agentic.is_recovery_active()
    asyncio.run(coord._handle_control_request({"op": "salamander_mode", "mode": "NORMAL"}))
    assert coord.recovery.mode == "NORMAL"
    kinds = [e.kind for e in coord.causal.trace(recovery_id="salamander:9")]
    assert "recovery_external" in kinds and "recovery_verified" in kinds
    bad = asyncio.run(coord._handle_control_request({"op": "salamander_mode", "mode": "PANIC"}))
    assert bad["status"] == "error"


def test_miner_writes_lane_mask_only_when_salamander_is_absent():
    bridge = _Bridge()
    coord = _wired(bridge)
    plan = RecoveryPlan(actions=(_action(RecoveryCommand.SEVER_LANE),), observation={})
    assert coord._dispatch_observation(plan) == ["SEVER_LANE"]
    assert bridge.masks == [0]
    record = coord.recovery.snapshot()["open"][0]
    assert record["state"] == "ACKED" and record["ack"] is True
    coord.recovery.observe(healthy=True)
    assert coord.recovery.snapshot()["recent"][-1]["state"] == "VERIFIED"

    coord.apply_salamander_mode("NORMAL")  # supervisor alive: it owns the mask
    assert coord._dispatch_observation(plan) == []
    assert bridge.masks == [0]
    assert coord.recovery.snapshot()["open"][0]["deferred"] == ["SEVER_LANE"]


def test_evidence_snapshot_is_published_and_served(monkeypatch):
    coord = _wired(_Bridge())
    published = []
    coord.set_evidence_sink(published.append)
    coord.apply_salamander_mode("NORMAL")
    snapshot = published[-1]
    encoded = json.dumps(snapshot, default=str)
    assert snapshot["schema"] == control_api.MINING_EVIDENCE_SCHEMA
    assert snapshot["recovery"]["authority"] == "salamander"
    assert snapshot["execution_backend"]["route"] == "cpu_reference"

    class _Plane:
        def records(self):
            return []

    monkeypatch.setattr(control_api, "_control_plane", lambda: _Plane())
    monkeypatch.setattr(control_api, "_read_metrics", lambda _w: {"mining_evidence": encoded})
    served = control_api.mining_evidence_payload()
    assert served["evidence_available"] is True and served["worker_live"] is False
    assert served["recovery"]["mode"] == "NORMAL"
    monkeypatch.setattr(control_api, "_read_metrics", lambda _w: {})
    absent = control_api.mining_evidence_payload()
    assert absent["evidence_available"] is False and "execution_backend" not in absent


def test_record_replace_keeps_contract_validation():
    record = _record()
    with pytest.raises(ValueError):
        dataclasses.replace(record, pool_accepted=1)


def test_work_space_ignores_target_and_job_id_but_not_header_fields():
    from chronus.mla1517.mining.coordinator import _header_work_space
    from chronus.mla1517.mining.stratum_state import StratumJobGeneration

    base = StratumJobGeneration(
        generation_id=1,
        pool_id="p",
        job_id="job-1",
        fingerprint="fp1",
        received_at=1.0,
        clean_jobs=True,
        prevhash="ab" * 32,
        coinb1="01",
        coinb2="02",
        merkle_branch=("aa" * 32,),
        version="20000000",
        nbits="1d00ffff",
        ntime="65abcdef",
        extranonce1="01020304",
        extranonce2_size=4,
        target=1,
        target_generation=1,
    )
    same = dataclasses.replace(base, job_id="job-2", target=2**240, target_generation=7)
    assert _header_work_space(base) == _header_work_space(same)
    for field, value in (("ntime", "65abcdf0"), ("extranonce1", "05060708"), ("coinb1", "03")):
        assert _header_work_space(base) != _header_work_space(
            dataclasses.replace(base, **{field: value})
        )
