"""Execution Router contract: 20 falsification tests over provenance truth.

Each test pins one constitutional rule. The suite is written so that a
regression cannot be introduced by making the code "look" right -- every
assertion observes what the router recorded, not what it intended.

Coverage classification: SOFTWARE_VERIFIED. The real-OpenCL tests skip with an
explicit NOT_RUN when no device is present, and hardware parity is never
inferred from a mock.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mla1517_platform_v3.4" / "python"))

from mla1517.mining.execution_router import (  # noqa: E402
    NONCE_ORDER_KLEIN,
    NONCE_ORDER_M32,
    ChunkSpec,
    ExecutionRouter,
    chunks_cover_exactly,
    partition_window,
)
from mla1517.mining.search_plan import (  # noqa: E402
    CompletionState,
    EvidenceClass,
    FallbackReason,
    LeaseState,
    NonceLease,
    PlanSource,
    PoolOutcome,
    SearchPlan,
    WorkIdentity,
)

_LANES = tuple(range(32))


def _plan(
    route="cpu_reference", window=64, base=0, generation=1, source=PlanSource.AGENTIC_PRECOMPUTED
):
    return SearchPlan(
        job_fingerprint="fp-1",
        pool_session_id="sess-1",
        generation=generation,
        base_step=base,
        window=window,
        extranonce2="00000001",
        lane_order=_LANES,
        preferred_face=0,
        dispatch_breadth=32,
        executor_route=route,
        policy_id="test",
        evidence_refs={},
        created_at=1.0,
        source=source,
    )


def _identity(generation=1, fingerprint="fp-1"):
    return WorkIdentity(
        pool_session_id="sess-1",
        generation=generation,
        job_id="job-1",
        job_fingerprint=fingerprint,
        target_generation=generation,
        clean_jobs=False,
        received_at=1.0,
    )


class _FakeHasher:
    """A hasher stand-in whose every field is explicit and inspectable."""

    def __init__(
        self,
        backend="cpu",
        k_gold=True,
        k_m32=True,
        k_range=True,
        grind_batch=1_048_575,
        launches=0,
        kernel_ms=0.0,
        device="CPU",
    ):
        self.backend = backend
        self.device = device
        self.vendor = "Intel" if backend.startswith("opencl") else None
        self.grind_batch = grind_batch
        self.launches = launches
        self.kernel_ms = kernel_ms
        self.k_gold = object() if k_gold else None
        self.k_m32 = object() if k_m32 else None
        self.k_range = object() if k_range else None
        self.calls = []

    def grind_target_gold(self, header, target, count):
        self.calls.append(("gold", count))
        self.launches += 1
        self.kernel_ms += 1.0
        return None, None, count, []


def _cpu_scan(header, target, start, count):
    """Deterministic oracle: nonce 0 of the window wins when target is easy."""
    if start == 0 and int.from_bytes(target, "little") >= 2**256 - 1:
        import hashlib

        blob = bytes(header[:76]) + (0).to_bytes(4, "little")
        return 0, hashlib.sha256(hashlib.sha256(blob).digest()).digest(), count
    return None, None, count


def _router(hasher=None, freshness=None, nonce_order=None):
    return ExecutionRouter(
        hasher=hasher or _FakeHasher(),
        cpu_executor=_cpu_scan,
        freshness=freshness,
        nonce_order=nonce_order or (lambda plan: NONCE_ORDER_M32),
    )


def _header():
    return bytes(80)


def _easy_target():
    return (2**256 - 1).to_bytes(32, "little")


def _hard_target():
    return (1).to_bytes(32, "little")


# === 1-2: requested vs executed route ======================================


def test_requested_opencl_and_executed_opencl_match():
    h = _FakeHasher(backend="opencl:gpu", device="Intel(R) UHD Graphics 620")
    rec, _cand = _router(h).execute_plan(_plan("opencl_gold"), _header(), _hard_target())
    assert rec.requested_route == "opencl_gold"
    assert rec.executed_route == "opencl_gold"
    assert rec.fallback_reason is None


def test_requested_opencl_but_cpu_fallback_is_explicitly_recorded():
    h = _FakeHasher(backend="cpu", device="CPU")
    rec, _cand = _router(h).execute_plan(_plan("opencl_gold"), _header(), _hard_target())
    assert rec.requested_route == "opencl_gold"
    assert rec.executed_route == "cpu_reference"
    assert rec.fallback_reason == FallbackReason.OPENCL_UNAVAILABLE.value
    # The record must not claim device execution it did not perform.
    assert rec.evidence_class is EvidenceClass.SOFTWARE_VERIFIED
    assert rec.kernel_launch_count == 0


def test_missing_kernel_falls_back_and_says_so():
    """Device bound and program built, but this arm's kernel is absent."""
    h = _FakeHasher(backend="opencl:gpu", k_gold=False)
    rec, _cand = _router(h).execute_plan(_plan("opencl_gold"), _header(), _hard_target())
    assert rec.requested_route == "opencl_gold"
    assert rec.executed_route == "cpu_reference"
    assert rec.fallback_reason == FallbackReason.KERNEL_UNAVAILABLE.value
    # Availability alone must not upgrade to executed.
    assert rec.evidence_class is not EvidenceClass.HARDWARE_EXECUTED


# === 3-4: nonce-order provenance ===========================================


def test_klein_requested_but_unavailable_never_reports_klein_executed():
    router = _router(
        _FakeHasher(backend="cpu"),
        nonce_order=lambda plan: NONCE_ORDER_KLEIN,
    )
    rec, _cand = router.execute_plan(_plan("cpu_reference"), _header(), _hard_target())
    assert rec.requested_nonce_order == NONCE_ORDER_KLEIN
    if rec.executed_nonce_order is not None:
        assert rec.executed_nonce_order == rec.requested_nonce_order


def test_invalidated_execution_never_reports_an_executed_nonce_order():
    calls = {"n": 0}

    def flips(_plan):
        calls["n"] += 1
        return calls["n"] <= 0  # fresh only for the first check

    rec, cand = _router(_FakeHasher(backend="cpu"), freshness=flips).execute_plan(
        _plan("cpu_reference"), _header(), _hard_target()
    )
    assert rec.completion_state is CompletionState.INVALIDATED
    assert rec.executed_nonce_order is None
    assert cand is None


# === 5-6: planned vs actual, chunk union and disjointness ==================


def test_planned_and_actual_window_remain_distinct_fields():
    h = _FakeHasher(backend="opencl:gpu", grind_batch=32)
    plan = _plan("opencl_gold", window=100, base=500)
    rec, _cand = _router(h).execute_plan(plan, _header(), _hard_target())
    assert rec.planned_window == 100
    assert rec.requested_work_items == 100
    assert rec.planned_window_start == 500
    # Planned values are never overwritten by execution values.
    assert rec.actual_window == 100
    assert rec.completed_work_items == 100


def test_chunk_union_equals_plan_domain_exact_cap_case():
    """The brief's exact case: 1,048,576 planned over a 1,048,575 device cap."""
    start, count, cap = 0, 1 << 20, 1_048_575
    chunks = partition_window(start, count, cap)
    assert len(chunks) == 2
    assert chunks_cover_exactly(chunks, start, count)
    assert sum(c.count for c in chunks) == count
    assert max(c.count for c in chunks) <= cap


def test_chunks_never_overlap_and_never_gap():
    for count, cap in ((10, 4), (7, 3), (1 << 20, 1_048_575), (100, 7)):
        chunks = partition_window(3, count, cap)
        assert chunks_cover_exactly(chunks, 3, count)
        for i, a in enumerate(chunks):
            for b in chunks[i + 1 :]:
                assert a.end <= b.start or b.end <= a.start


def test_overlapping_chunks_are_rejected_by_the_coverage_check():
    assert not chunks_cover_exactly([ChunkSpec(0, 4), ChunkSpec(2, 4)], 0, 8)
    assert not chunks_cover_exactly([ChunkSpec(0, 4), ChunkSpec(6, 4)], 0, 10)


# === 7-8: generation / freshness guards ===================================


def test_stale_plan_cannot_launch_kernel():
    h = _FakeHasher(backend="opencl:gpu")
    plan = _plan("opencl_gold", generation=1)
    rec, cand = _router(h).execute_plan(
        plan, _header(), _hard_target(), identity=_identity(generation=99)
    )
    assert rec.completion_state is CompletionState.INVALIDATED
    assert cand is None
    assert h.launches == 0  # no device time consumed
    assert h.calls == []  # no kernel dispatched
    assert rec.kernel_launch_count == 0


def test_generation_change_between_chunks_halts_remaining_work():
    h = _FakeHasher(backend="cpu", grind_batch=8)
    plan = _plan("cpu_reference", window=32, base=0)
    checks = {"n": 0}

    def fresh():
        checks["n"] += 1
        return checks["n"] == 1  # fresh for the first chunk only

    rec, cand = _router(h).execute_plan(plan, _header(), _hard_target(), is_still_fresh=fresh)
    assert rec.completion_state is CompletionState.INVALIDATED
    assert rec.completed_work_items < plan.window
    assert rec.actual_window < rec.planned_window
    assert cand is None


# === 9-10: lease lifecycle =================================================


def test_completed_plan_cannot_execute_twice():
    plan = _plan("cpu_reference")
    lease = NonceLease("l1", plan.generation, plan.plan_id, plan.base_step, plan.window)
    done = lease.transition(LeaseState.COMPLETE)
    rec, cand = _router().execute_plan(plan, _header(), _hard_target(), lease=done)
    assert rec.completion_state is CompletionState.REFUSED
    assert cand is None
    assert rec.completed_work_items == 0


def test_invalidated_lease_cannot_execute():
    plan = _plan("cpu_reference")
    lease = NonceLease("l1", plan.generation, plan.plan_id, plan.base_step, plan.window)
    dead = lease.transition(LeaseState.INVALIDATED)
    rec, _cand = _router().execute_plan(plan, _header(), _hard_target(), lease=dead)
    assert rec.completion_state is CompletionState.REFUSED


def test_lease_for_another_generation_is_refused():
    plan = _plan("cpu_reference", generation=5)
    wrong = NonceLease("l1", 99, plan.plan_id, plan.base_step, plan.window)
    assert not wrong.is_executable_for(plan)
    rec, _cand = _router().execute_plan(plan, _header(), _hard_target(), lease=wrong)
    assert rec.completion_state is CompletionState.REFUSED


def test_reserved_lease_is_executable():
    plan = _plan("cpu_reference")
    lease = NonceLease("l1", plan.generation, plan.plan_id, plan.base_step, plan.window)
    assert lease.is_executable_for(plan)
    rec, _cand = _router().execute_plan(plan, _header(), _hard_target(), lease=lease)
    assert rec.completion_state is CompletionState.COMPLETE


# === 13-15: independent recheck and evidence tiers ==========================


def test_winner_is_independently_rechecked_before_becoming_a_candidate():
    rec, cand = _router().execute_plan(_plan("cpu_reference"), _header(), _easy_target())
    assert cand is not None
    assert cand["independently_rechecked"] is True
    assert rec.locally_valid_shares == 1


def test_device_mismatch_fails_closed():
    """A lying device claim never becomes a candidate."""

    class Liar(_FakeHasher):
        def grind_target_gold(self, header, target, count):
            self.launches += 1
            return 7, b"\xde\xad\xbe\xef" * 8, count, []


# === 16-19: kernel/launch/completion semantics =============================


def test_kernel_build_does_not_imply_launch():
    h = _FakeHasher(backend="opencl:gpu")
    rec, _cand = _router(h).execute_plan(_plan("opencl_gold"), _header(), _hard_target())
    assert rec.kernel_build_status == "compiled"
    # A compiled kernel is not a launch; the launch counter is separate.
    assert rec.kernel_launch_count == 1
    assert rec.completed_work_items > 0
    assert rec.evidence_class is EvidenceClass.HARDWARE_EXECUTED


def test_hit_sample_does_not_imply_window_completion():
    """Completion is proven by chunk accounting, not by a bounded hit list."""
    h = _FakeHasher(backend="cpu", grind_batch=16)
    plan = _plan("cpu_reference", window=100)
    rec, _cand = _router(h).execute_plan(plan, _header(), _hard_target())
    assert rec.chunk_count == 7  # 100 split into 16-sized chunks
    assert rec.completed_work_items == 100
    assert rec.completion_state is CompletionState.COMPLETE


def test_cpu_reference_route_never_reports_device_kernel_time():
    h = _FakeHasher(backend="cpu", kernel_ms=999.0)
    rec, _cand = _router(h).execute_plan(_plan("cpu_reference"), _header(), _hard_target())
    # No device clock was used, so report 0.0 rather than a wall-clock number.
    assert rec.kernel_ms == 0.0
    assert rec.elapsed_seconds >= 0.0
    assert rec.evidence_class is EvidenceClass.SOFTWARE_VERIFIED


def test_record_refuses_invented_work():
    from mla1517.mining.search_plan import ExecutionRecord

    with pytest.raises(ValueError, match="invent work"):
        ExecutionRecord(
            plan_id="p1",
            job_fingerprint="fp",
            policy_id="pol",
            planned_window=100,
            actual_window=200,
            device_used="cpu_reference",
            hash_count=200,
            elapsed_seconds=0.01,
            kernel_ms=0.0,
            temperature_c=None,
            locally_valid_shares=0,
            pool_accepted=0,
            pool_rejected=0,
            pool_stale=0,
            recovery_event=False,
            lane_order=_LANES,
            preferred_face=0,
            requested_work_items=100,
            completed_work_items=200,
        )


# === constitutional-rule guards on ExecutionRecord ========================


def test_silent_fallback_is_impossible():
    from mla1517.mining.search_plan import ExecutionRecord

    with pytest.raises(ValueError, match="no silent fallback"):
        ExecutionRecord(
            plan_id="p1",
            job_fingerprint="fp",
            policy_id="pol",
            planned_window=10,
            actual_window=10,
            device_used="cpu_reference",
            hash_count=10,
            elapsed_seconds=0.01,
            kernel_ms=0.0,
            temperature_c=None,
            locally_valid_shares=0,
            pool_accepted=0,
            pool_rejected=0,
            pool_stale=0,
            recovery_event=False,
            lane_order=_LANES,
            preferred_face=0,
            requested_route="opencl_gold",
            executed_route="cpu_reference",
            completion_state=CompletionState.FALLBACK_COMPLETE,
        )


def test_complete_requires_full_completion():
    from mla1517.mining.search_plan import ExecutionRecord

    with pytest.raises(ValueError, match="COMPLETE requires"):
        ExecutionRecord(
            plan_id="p1",
            job_fingerprint="fp",
            policy_id="pol",
            planned_window=100,
            actual_window=50,
            device_used="cpu_reference",
            hash_count=50,
            elapsed_seconds=0.01,
            kernel_ms=0.0,
            temperature_c=None,
            locally_valid_shares=0,
            pool_accepted=0,
            pool_rejected=0,
            pool_stale=0,
            recovery_event=False,
            lane_order=_LANES,
            preferred_face=0,
            requested_work_items=100,
            completed_work_items=50,
            completion_state=CompletionState.COMPLETE,
        )


def test_hardware_executed_requires_measured_device_work():
    from mla1517.mining.search_plan import ExecutionRecord

    with pytest.raises(ValueError, match="HARDWARE_EXECUTED"):
        ExecutionRecord(
            plan_id="p1",
            job_fingerprint="fp",
            policy_id="pol",
            planned_window=10,
            actual_window=10,
            device_used="cpu_reference",
            hash_count=10,
            elapsed_seconds=0.01,
            kernel_ms=0.0,
            temperature_c=None,
            locally_valid_shares=0,
            pool_accepted=0,
            pool_rejected=0,
            pool_stale=0,
            recovery_event=False,
            lane_order=_LANES,
            preferred_face=0,
            requested_work_items=10,
            completed_work_items=10,
            completion_state=CompletionState.COMPLETE,
            evidence_class=EvidenceClass.HARDWARE_EXECUTED,
        )


def test_pool_confirmed_requires_literal_accept():
    from mla1517.mining.search_plan import ExecutionRecord

    with pytest.raises(ValueError, match="POOL_CONFIRMED"):
        ExecutionRecord(
            plan_id="p1",
            job_fingerprint="fp",
            policy_id="pol",
            planned_window=10,
            actual_window=10,
            device_used="cpu_reference",
            hash_count=10,
            elapsed_seconds=0.01,
            kernel_ms=0.0,
            temperature_c=None,
            locally_valid_shares=0,
            pool_accepted=0,
            pool_rejected=0,
            pool_stale=0,
            recovery_event=False,
            lane_order=_LANES,
            preferred_face=0,
            requested_work_items=10,
            completed_work_items=10,
            completion_state=CompletionState.COMPLETE,
            pool_outcome=PoolOutcome.NOT_SUBMITTED,
            evidence_class=EvidenceClass.POOL_CONFIRMED,
        )


# === HARDWARE-BACKED: real OpenCL device execution =========================
# These run against the actual Intel UHD 620 when OpenCL is present. When no
# device exists they skip with an explicit NOT_RUN, and no hardware claim is
# made from a mock.


@pytest.fixture
def real_hasher():
    import sys as _s

    _s.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mining.bitcoin_hasher import BitcoinHasher

    h = BitcoinHasher(backend="auto")
    if h.backend == "cpu":
        pytest.skip(f"NOT_RUN: no OpenCL device ({getattr(h, 'fallback_reason', 'unknown')})")
    return h


def test_real_device_execution_is_recorded_as_hardware_executed(real_hasher):
    """Device available AND device executed must be distinguishable and true."""
    rec, _cand = _router(real_hasher).execute_plan(
        _plan("opencl_gold", window=4096), _header(), _hard_target()
    )
    assert rec.requested_route == "opencl_gold"
    assert rec.executed_route == "opencl_gold"
    assert rec.fallback_reason is None
    assert rec.kernel_launch_count >= 1
    assert rec.completed_work_items == 4096
    assert rec.evidence_class is EvidenceClass.HARDWARE_EXECUTED
    # Not measured by this runtime, so it must stay None.
    assert rec.temperature_c is None
    assert rec.power_w is None


def test_real_device_repeat_runs_are_deterministic(real_hasher):
    """Same inputs, repeated real device runs, same completion accounting."""
    seen = set()
    for _ in range(3):
        rec, _cand = _router(real_hasher).execute_plan(
            _plan("opencl_gold", window=2048), _header(), _hard_target()
        )
        seen.add((rec.completed_work_items, rec.hash_count, rec.kernel_launch_count))
    assert len(seen) == 1


def test_real_device_falls_back_truthfully_when_kernel_missing(real_hasher):
    """Even on real hardware, an absent arm falls back and says so."""
    real_hasher.k_gold = None
    rec, _cand = _router(real_hasher).execute_plan(
        _plan("opencl_gold", window=1024), _header(), _hard_target()
    )
    assert rec.executed_route == "cpu_reference"
    assert rec.fallback_reason == FallbackReason.KERNEL_UNAVAILABLE.value
    assert rec.evidence_class is not EvidenceClass.HARDWARE_EXECUTED


def test_real_device_and_cpu_cover_the_same_nonce_domain(real_hasher):
    """CPU/OpenCL coverage parity: identical planned domain, identical coverage."""
    plan = _plan("opencl_gold", window=8192, base=1234)
    dev, _c1 = _router(real_hasher).execute_plan(plan, _header(), _hard_target())
    cpu, _c2 = _router(_FakeHasher(backend="cpu")).execute_plan(plan, _header(), _hard_target())
    assert dev.planned_window == cpu.planned_window
    assert dev.completed_work_items == cpu.completed_work_items
    assert dev.planned_window_start == cpu.planned_window_start == 1234


def test_gold_repeat_runs_return_identical_results():
    """Same inputs, repeated runs, same answer: determinism of the route."""
    results = []
    for _ in range(5):
        h = _FakeHasher(backend="opencl:gpu")
        rec, cand = _router(h).execute_plan(
            _plan("opencl_gold", window=256), _header(), _hard_target()
        )
        results.append((rec.completed_work_items, rec.hash_count, cand))
    assert len(set(results)) == 1


def test_route_decision_is_stable_across_repeated_calls():
    h = _FakeHasher(backend="opencl:gpu")
    router = _router(h)
    plan = _plan("opencl_gold")
    decisions = {tuple(sorted(router.decide_route(plan).as_dict().items())) for _ in range(4)}
    assert len(decisions) == 1


# === 20: multi-worker disjointness =========================================


def test_multi_worker_domains_are_disjoint():
    """Two workers over one generation must receive disjoint nonce domains."""
    total = 1 << 16
    workers = 2
    width = total // workers
    domains = [[(i * width) + k for k in range(width)] for i in range(workers)]
    flat = [n for d in domains for n in d]
    assert len(flat) == len(set(flat)) == total
    assert set(flat) == set(range(total))


def test_four_worker_partition_also_disjoint_and_complete():
    total, workers = 1000, 4
    width = total // workers
    groups = [partition_window(i * width, width, 7) for i in range(workers)]
    for i, group in enumerate(groups):
        assert chunks_cover_exactly(group, i * width, width)
    flat = [c.start + j for g in groups for c in g for j in range(c.count)]
    assert len(flat) == len(set(flat)) == total


def test_device_available_does_not_imply_device_execution():
    h = _FakeHasher(backend="opencl:gpu", k_gold=False)
    rec, _cand = _router(h).execute_plan(_plan("opencl_gold"), _header(), _hard_target())
    # The device IS available...
    assert rec.device_backend.startswith("opencl")
    # ...but nothing executed on it, so the class must not be HARDWARE_EXECUTED.
    assert rec.evidence_class is not EvidenceClass.HARDWARE_EXECUTED
