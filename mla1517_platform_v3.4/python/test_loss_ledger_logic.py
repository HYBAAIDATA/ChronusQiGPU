"""Loss ledger pinned by one hand-worked timeline.

A mutation check of loss_ledger.py against the original intelligence tests
killed 59% of planted mistakes, including ``v / wall`` becoming ``v * wall``:
the time-share fractions behind "useful hashing" were never checked. The
timeline below is worked out by hand; every category must match it.
"""

from __future__ import annotations

import pytest

from mla1517.mining.loss_ledger import LossLedger
from mla1517.mining.search_plan import CompletionState
from mla1517.mining.world_model import MiningWorldModel, RouteModel
from test_mining_intelligence import ROUTE, _record


def _world() -> MiningWorldModel:
    world = MiningWorldModel()
    route = RouteModel(forgetting=1.0)
    for _ in range(3):  # measured directly: 1 microsecond per hash
        route.observe(1_000, 0.002, 0.001)
    world.routes[ROUTE] = route
    return world


def test_a_worked_timeline_lands_in_the_right_categories():
    # Start away from zero: at t=0, now - start and now + start agree.
    T0 = 100.0
    world, ledger = _world(), LossLedger()
    ledger.observe_bind(T0)
    # t=1.0: 0.5 s window, kernel 0.4 s -> 0.4 useful + 0.1 overhead.
    ledger.observe_execution(
        _record(hash_count=400_000, elapsed_seconds=0.5, kernel_ms=400.0),
        world,
        started_at=T0 + 1.0,
    )
    ledger.observe_idle(0.2)
    ledger.observe_idle(-1.0)  # nonsense is ignored
    ledger.observe_recovery(T0 + 2.0, True)
    ledger.observe_recovery(T0 + 2.2, True)  # already recovering: the start stays 2.0
    ledger.observe_recovery(T0 + 2.5, False)  # 0.5 s of recovery
    ledger.observe_recovery(T0 + 2.6, False)  # not recovering: nothing added
    # t=3.0: invalidated 0.3 s window, no kernel time -> 200k hashes * 1 us = 0.2 stale.
    ledger.observe_execution(
        _record(
            hash_count=200_000,
            elapsed_seconds=0.3,
            kernel_ms=0.0,
            completion_state=CompletionState.INVALIDATED,
        ),
        world,
        started_at=T0 + 3.0,
    )
    # t=3.5: a route the world has not learned -> 0.25 s unattributed, never guessed.
    ledger.observe_execution(
        _record(
            hash_count=1_000,
            elapsed_seconds=0.25,
            kernel_ms=0.0,
            requested_route="opencl_m32",
            executed_route="opencl_m32",
        ),
        world,
        started_at=T0 + 3.5,
    )
    ledger.observe_recovery(T0 + 4.0, True)  # still recovering at the snapshot

    snap = ledger.snapshot(T0 + 5.0)
    expected = {
        "useful_hashing": 0.4,
        "stale_hashing": 0.2,
        "window_overhead": 0.1 + 0.1,
        "idle_no_plan": 0.2,
        "recovery": 0.5 + 1.0,  # 1.0 s of the open recovery counts
        "unattributed_execution": 0.25,
    }
    expected["other"] = 5.0 - sum(expected.values())  # 2.25
    assert snap["wall_seconds"] == 5.0
    assert snap["seconds"] == pytest.approx(expected)
    assert snap["fractions"] == pytest.approx({k: v / 5.0 for k, v in expected.items()})
    assert (snap["executions"], snap["hashes"], snap["stale_hashes"]) == (3, 601_000, 200_000)
    assert snap["time_to_first_hash_ms"] == {"p50": 1000.0, "p90": 1000.0, "samples": 1}


def test_an_empty_ledger_reports_nothing_rather_than_zero():
    snap = LossLedger().snapshot(10.0)
    assert snap["wall_seconds"] == 0.0
    assert set(snap["fractions"].values()) == {None}
    assert snap["time_to_first_hash_ms"] is None


def test_first_hash_latency_needs_real_hashes_and_keeps_recent_percentiles():
    world, ledger = _world(), LossLedger()
    ledger.observe_bind(0.0)
    ledger.observe_execution(_record(hash_count=0, elapsed_seconds=0.1), world, started_at=0.5)
    assert ledger.first_hash_latency_s == []  # an empty window is not a first hash
    assert (ledger.executions, ledger.hashes) == (1, 0)
    ledger.observe_bind(1.0)
    ledger.observe_execution(_record(hash_count=1), world, started_at=1.5)
    assert ledger.first_hash_latency_s == [0.5]  # one hash is a first hash
    ledger.first_hash_latency_s.clear()
    for i in range(10):
        bind_at = 10.0 * (i + 1)
        ledger.observe_bind(bind_at)
        ledger.observe_execution(_record(), world, started_at=bind_at + 0.01 * (i + 1))
    first = ledger.snapshot(200.0)["time_to_first_hash_ms"]
    # Latencies 10..100 ms: p50 is index 5 (60 ms), p90 index 9 (100 ms).
    assert first == pytest.approx({"p50": 60.0, "p90": 100.0, "samples": 10})
    for i in range(300):
        ledger.observe_bind(1_000.0 + i)
        ledger.observe_execution(_record(), world, started_at=1_000.0 + i + 0.5)
    assert len(ledger.first_hash_latency_s) == 256
    assert ledger.first_hash_latency_s[-1] == pytest.approx(0.5)


def test_hashing_time_never_exceeds_the_window():
    world, ledger = _world(), LossLedger()
    ledger.observe_execution(
        _record(hash_count=1_000, elapsed_seconds=0.001, kernel_ms=5.0), world, started_at=0.0
    )
    snap = ledger.snapshot(0.001)
    assert snap["seconds"]["useful_hashing"] == pytest.approx(0.001)
    assert snap["seconds"]["window_overhead"] == 0.0
    assert snap["fractions"]["useful_hashing"] == pytest.approx(
        1.0
    )  # a sub-second wall still divides
