"""LEMMA_LUCAS_UNIVERSAL (docs/lemma_lucas_universal.md) — executed checks.

Asserts that every Chronus-owned bounded envelope wired in the universal
scaling extension is a ladder stop, that the anchor rule and power dial
hold, that caller-declared bounds pass through unchanged, and that the
declared OUT_OF_SCOPE surfaces stay raw. Expected values are recomputed
from first principles (the independent Lucas recurrence), never by
calling the code under test.
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

from Intelligence.lucas_scales import (
    CHRONUS_SCALE_RUNGS,
    ladder_capacity,
    nearest_ladder_index,
)


def L(n: int) -> int:
    """Independent Lucas recurrence: L_0=2, L_1=1, L_n=L_{n-1}+L_{n-2}."""
    a, b = 2, 1
    for _ in range(n):
        a, b = b, a + b
    return a


EXECUTION_RUNGS = (10, 12, 15, 18, 20, 31, 50, 76)


def _is_stop(v: int) -> bool:
    return isinstance(v, int) and v > 0 and any(v % r == 0 for r in EXECUTION_RUNGS)


# ---------------------------------------------------------------------------
# The ladder itself: power dial, attribution, two ladders
# ---------------------------------------------------------------------------


def test_execution_ladder_excludes_algebraic_rung_7():
    """Index 7 is algebraic-only: hardware dispatch may not admit it."""
    assert CHRONUS_SCALE_RUNGS == EXECUTION_RUNGS
    assert 7 not in CHRONUS_SCALE_RUNGS
    from turing_universal_quantum_computer.pisot import (
        LUCAS_EXECUTION_SCALE_INDICES,
        SUPPORTED_SCALE_INDICES,
        require_lucas_execution_scale,
        LucasScaleError,
    )

    assert 7 in SUPPORTED_SCALE_INDICES  # algebraic ladder includes it
    assert LUCAS_EXECUTION_SCALE_INDICES == EXECUTION_RUNGS
    with pytest.raises(LucasScaleError):
        require_lucas_execution_scale(7)


def test_lucas_scales_by_power_monotone_over_execution_rungs():
    """Raising the power index n raises the envelope ratio L_n / L_10."""
    from chronus.seam.scale import compute_effective_capacity, memory_budget_bytes

    eff = [compute_effective_capacity(80, n).effective for n in EXECUTION_RUNGS]
    assert eff == sorted(eff) and len(set(eff)) == len(eff)
    # Independent check of the formula at every execution rung.
    for n in EXECUTION_RUNGS:
        cap = compute_effective_capacity(80, n)
        assert cap.effective == 80 * L(n) // L(10)
        assert cap.lucas_L == L(n)
    budgets = [memory_budget_bytes(1024, n) for n in EXECUTION_RUNGS]
    assert budgets == sorted(budgets)


def test_anchor_rule_zero_physical_and_reference_identity():
    from chronus.seam.scale import compute_effective_capacity

    for n in EXECUTION_RUNGS:
        assert compute_effective_capacity(0, n).effective == 0
    assert compute_effective_capacity(80, 10).effective == 80  # L_10/L_10 = 1
    cap = compute_effective_capacity(80, 15)
    assert cap.physical == 80 and cap.effective == 887  # 80 * 1364 // 123


def test_scaled_envelope_declares_itself_not_measured():
    from chronus.seam.scale import compute_effective_capacity

    d = compute_effective_capacity(80, 20).as_dict()
    assert d["kind"] == "scale_contract_envelope"
    assert d["physical"] == 80
    assert "TH/s" not in d["note"] or "never" in d["note"].lower()


# ---------------------------------------------------------------------------
# ladder_capacity: floor-to-stop, minimum 10, idempotent
# ---------------------------------------------------------------------------


def test_ladder_capacity_floors_to_stop_with_minimum_ten():
    pins = {
        1: 10, 3: 10, 8: 10, 10: 10, 16: 15, 31: 31, 32: 31,
        64: 62, 256: 255, 512: 510, 2048: 2046, 4096: 4095,
        65536: 65535, 1 << 22: 4194300, 32 * 1024 * 1024: 33554431,
    }
    for bound, stop in pins.items():
        assert ladder_capacity(bound) == stop, f"ladder_capacity({bound})"
        assert _is_stop(stop)
    for v in pins.values():
        assert ladder_capacity(v) == v  # idempotent


def test_ladder_capacity_never_exceeds_declared_bound():
    for bound in (16, 64, 255, 1000, 12345, 65536, 10_000_000):
        out = ladder_capacity(bound)
        assert _is_stop(out)
        assert out <= bound


# ---------------------------------------------------------------------------
# Wired surfaces: every Chronus-owned default is a ladder stop
# ---------------------------------------------------------------------------


def test_seam_queue_threshold_is_ladder_stop():
    from chronus.seam import store

    store.reset()
    threshold = store.queue_of("dev-lucas")["threshold"]
    assert threshold == 62 and _is_stop(threshold)


def test_seam_partition_snaps_span_to_ladder_stop():
    from chronus.seam.hybrid import partition
    from chronus.seam.types import KernelName

    parts = partition([KernelName.sha256d_scan, KernelName.lucas_wind], span=1024)
    windows = [w for ws in parts.values() for w in ws]
    snapped = nearest_ladder_index(1024, 1, 65536)
    assert snapped == 1023
    assert max(w.end for w in windows) <= snapped
    # exact tiling of the snapped span — the arithmetic itself is not scaled
    assert windows[0].start == 0


def test_seam_workflow_window_snaps_before_dispatch():
    import chronus.seam.workflow as wf

    captured = {}

    class _Bridge:
        def __init__(self, *a, **k):
            pass

        async def disconnect(self):
            return None

    async def _fake_run(bridge, host, port, *, window, **kw):
        captured["window"] = window
        return object()

    import chronus.seam.scale  # noqa: F401  (keeps patch target warm)

    orig_bridge, orig_run = wf.StratumBridge, wf._run_workflow
    wf.StratumBridge, wf._run_workflow = _Bridge, _fake_run
    try:
        asyncio.run(wf.run_workflow("h", 1, "w", "p", window=4096))
    finally:
        wf.StratumBridge, wf._run_workflow = orig_bridge, orig_run
    assert captured["window"] == 4095


def test_genetic_effort_budgets_snap_to_stops():
    from chronus.seam.genetic_mining import evolve_mining_config

    class _S:
        def __init__(self, w, li):
            self.work_items, self.ladder_index = w, li

    r = evolve_mining_config(64, lambda j, n: _S(n, 5), generations=5, population_size=8)
    assert r.generations_run == 10 and r.population_size == 10
    # bounds validation still precedes the snap — out-of-range stays rejected
    with pytest.raises(ValueError):
        evolve_mining_config(64, lambda j, n: _S(n, 5), generations=0)


def test_fabric_default_request_envelope_is_ladder_stop():
    import chronus.fabric as fabric

    assert fabric._DEFAULT_WORK_ITEMS == 1048575
    assert _is_stop(fabric._DEFAULT_WORK_ITEMS)


def test_mining_bounded_capacities_are_ladder_stops():
    import chronus.mla1517.mining.agentic_controller as ac
    import chronus.mla1517.mining.causal as causal
    import chronus.mla1517.mining.closed_loop as cl
    import chronus.mla1517.mining.cycle_fsm as fsm
    import chronus.mla1517.mining.decision_journal as dj
    import chronus.mla1517.mining.hashrate_governor as hg
    import chronus.mla1517.mining.nonce_lease as nl
    import chronus.mla1517.mining.policy_audit as pa
    import chronus.mla1517.mining.quality as quality
    import chronus.mla1517.mining.recovery_effect as recv
    import chronus.mla1517.mining.self_healing_agent as heal

    constants = [
        ("agentic._DEFAULT_QUEUE_DEPTH", ac._DEFAULT_QUEUE_DEPTH),
        ("agentic._MAX_QUEUE_DEPTH", ac._MAX_QUEUE_DEPTH),
        ("agentic._ADAPT_WINDOW", ac._ADAPT_WINDOW),
        ("agentic._LEAD_HISTORY_WINDOW", ac._LEAD_HISTORY_WINDOW),
        ("agentic._OUTCOME_HISTORY_LIMIT", ac._OUTCOME_HISTORY_LIMIT),
        ("agentic.MAX_STATE_BYTES", ac.MAX_STATE_BYTES),
        ("agentic._MAX_POLICIES", ac._MAX_POLICIES),
        ("agentic._MAX_POLICY_ID", ac._MAX_POLICY_ID),
        ("closed_loop._SAMPLE_RETENTION", cl._SAMPLE_RETENTION),
        ("closed_loop._HISTORY_RETENTION", cl._HISTORY_RETENTION),
        ("closed_loop._PERSIST_EVERY", cl._PERSIST_EVERY),
        ("recovery_effect.SPAN", recv.SPAN),
        ("nonce_lease._WORK_SPACE_MEMORY", nl._WORK_SPACE_MEMORY),
        ("nonce_lease._EXTRANONCE2_SKIP_LIMIT", nl._EXTRANONCE2_SKIP_LIMIT),
        ("hashrate_governor.lru_maxsize", hg.poisson_interval.cache_info().maxsize),
        ("runtime_config.WINDOW_MAX", None),  # placeholder resolved below
    ]
    for name, value in constants:
        if value is None:
            continue
        assert _is_stop(value), f"{name}={value} is not a ladder stop"

    # Signature defaults — Chronus-declared, snapped.
    assert _is_stop(inspect.signature(causal.CausalLedger.__init__).parameters["capacity"].default)
    assert _is_stop(inspect.signature(causal.CausalLedger.__init__).parameters["max_file_bytes"].default)
    assert _is_stop(inspect.signature(dj.DecisionJournal.__init__).parameters["capacity"].default)
    assert _is_stop(inspect.signature(quality.QualityLedger.__init__).parameters["window"].default)
    assert _is_stop(inspect.signature(heal.NonBlockingRecoveryQueue.__init__).parameters["max_pending"].default)
    assert _is_stop(inspect.signature(nl.NonceLeaseLedger.__init__).parameters["max_active"].default)
    assert _is_stop(inspect.signature(nl.NonceLeaseLedger.__init__).parameters["terminal_memory"].default)
    assert _is_stop(inspect.signature(pa.PolicyAuditor.__init__).parameters["every"].default)
    assert _is_stop(inspect.signature(fsm.MiningCycleLedger.__init__).parameters["history"].default)


def test_platform_runtime_bounds_are_ladder_stops():
    import runtime_config as rc

    assert _is_stop(rc.WINDOW_MAX) and rc.WINDOW_MAX == 4194300
    assert _is_stop(rc.CAMPAIGN_PHASES_MAX) and rc.CAMPAIGN_PHASES_MAX == 31
    assert _is_stop(rc.ARMS_MAX) and rc.ARMS_MAX == 600
    assert _is_stop(rc.WORKERS_MAX) and rc.WORKERS_MAX == 600
    # the shipped default window was already a stop
    assert _is_stop(200000)


def test_probe_workload_depth_snaps_but_samples_stay_raw():
    import chronus.seam.probe as probe

    sig = inspect.signature(probe._measure_host_hps)
    assert sig.parameters["samples"].default == 3  # evidence minimum — raw
    assert sig.parameters["work"].default == 1024  # input, snapped inside
    from chronus.seam.scale import snap_work_items

    assert snap_work_items(1024) == 1023


# ---------------------------------------------------------------------------
# Caller authority: explicitly declared bounds pass through unchanged
# ---------------------------------------------------------------------------


def test_caller_declared_bounds_are_honored():
    from chronus.mla1517.mining.quality import QualityLedger
    from chronus.mla1517.mining.self_healing_agent import NonBlockingRecoveryQueue

    assert QualityLedger(window=64)._window == 64  # explicit caller value kept
    q = NonBlockingRecoveryQueue(max_pending=7)
    assert q._queue.maxsize == 7


# ---------------------------------------------------------------------------
# Out-of-scope pins stay raw
# ---------------------------------------------------------------------------


def test_out_of_scope_pins_unchanged():
    from chronus.mla1517.mining.nonce_lease import LANE_ALIGN, NONCE_SPACE
    from chronus.seam.capability import MIN_SAMPLES
    from chronus.seam.threshold import min_required, ThresholdPolicy

    assert LANE_ALIGN == 32          # M32 lane topology
    assert NONCE_SPACE == 1 << 32    # consensus domain
    assert MIN_SAMPLES == 32         # evidence methodology
    assert min_required(ThresholdPolicy.majority, 1, 3) == 2  # quorum math


def test_exact_tiling_not_scaled():
    """partition_window must cover the declared count exactly — no snap."""
    from hyba.multi_hasher import MultiDeviceHasher

    pool = MultiDeviceHasher([], include_cpu=True)
    spans, cert = pool.partition_window(0, 4096)
    cursor = 0
    for s in spans:
        assert s.span_base == cursor
        cursor += s.span_count
    assert cursor == 4096
    assert cert["total_span"] == 4096


def test_measured_counters_stay_raw():
    """Physical measurement arithmetic is never multiplied."""
    from chronus.seam.types import Distribution

    d = Distribution(mean=100.0, stddev=5.0, samples=64)
    assert d.samples == 64
