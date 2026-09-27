"""Contract tests for aethel's measured CPU/memory overhead accounting.

Every figure the meter reports is measured: CPU via process_time_ns, wall
via perf_counter_ns, memory via sys.getsizeof over live containers (a
declared floor) or the mapped region size (exact). These tests pin the
contract: counters increment on real ops, payload bytes are attributed,
and reports are honest about what is measured.
"""

import os
import struct
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)
for p in (_REPO_ROOT, os.path.abspath(".")):
    if p not in sys.path:
        sys.path.insert(0, p)

from aethel.costs import OverheadMeter, container_bytes, measure_alloc
from aethel.constants import (
    AETHEL_D10_OFFSET,
    AETHEL_HEADER_BYTES,
    AETHEL_SLOT_STRIDE,
    STATE_BYTES,
)
from aethel.manifold import ManifoldCurvature, PrimeStorageManifold
from aethel.gpu import TensorCoreGPU_Context
from aethel.shm import AethelQueue
from aethel.storage import AddressSpace, CassiniLedger


def _sealed_state() -> bytes:
    state = bytearray(STATE_BYTES)
    struct.pack_into("<i", state, AETHEL_D10_OFFSET, 1)  # D10 seal
    return bytes(state)


def test_ledger_append_metered():
    ledger = CassiniLedger()
    ledger.append(1, "0" * 64)
    ledger.append(2, "1" * 64)
    report = ledger.overhead_report()
    op = report["operations"]["ledger.append"]
    assert op["calls"] == 2
    assert op["cpu_ns"] >= 0  # sub-tick ops may read 0 on coarse clocks
    assert op["wall_ns"] > 0
    assert report["structural_bytes"] > 0
    assert report["entries"] == 2
    assert report["truth"] == "measured"


def test_ledger_cpu_is_cumulative_above_clock_granularity():
    """CPU ns is a real cumulative measure: enough ops exceed the coarsest
    process-time tick and the counter records nonzero CPU.  The op count
    adapts to the observed clock granularity — a fixed batch cannot
    guarantee a tick boundary is crossed on coarse (~15ms) clocks."""
    ledger = CassiniLedger()
    i = 0
    while True:
        for _ in range(2000):
            i += 1
            ledger.append(i, "0" * 64)
        op = ledger.overhead_report()["operations"]["ledger.append"]
        assert op["calls"] == i
        if op["cpu_ns"] > 0:
            break
        assert i < 4_000_000, "clock never ticked across 4M ledger ops"


def test_address_space_accounts_payload_bytes():
    space = AddressSpace()
    space.write(b"x" * 100)
    space.write(b"y" * 50)
    report = space.overhead_report()
    assert report["operations"]["space.write"]["calls"] == 2
    assert report["operations"]["space.write"]["payload_bytes"] == 150
    assert report["blocks"] == 2
    # The shared ledger meter aggregates the writes' append cost.
    assert report["ledger"]["operations"]["ledger.append"]["calls"] == 2


def test_fork_writers_share_ledger_meter():
    space = AddressSpace()
    fork = space.fork(writer=1)
    space.write(b"a")
    fork.write(b"b")
    # Both writers' appends land on the one shared ledger meter.
    assert space.ledger._costs.snapshot()["ledger.append"]["calls"] == 2
    # ...while each space meters only its own writes.
    assert space._costs.snapshot()["space.write"]["calls"] == 1
    assert fork._costs.snapshot()["space.write"]["calls"] == 1


def test_queue_commit_read_metered(tmp_path):
    with AethelQueue(tmp_path / "q.region", slot_count=4) as q:
        slot = q.commit(_sealed_state())
        assert slot is not None
        assert q.read(slot) is not None
        report = q.overhead_report()
        assert report["operations"]["shm.commit"]["calls"] == 1
        assert report["operations"]["shm.read"]["calls"] == 1
        # Region size is exact, not estimated.
        assert report["region_bytes"] == AETHEL_HEADER_BYTES + 4 * AETHEL_SLOT_STRIDE
        assert report["structural_bytes"] == report["region_bytes"]


def test_manifold_ingest_and_read_metered():
    gpu = TensorCoreGPU_Context(require_gpu=False)
    manifold = PrimeStorageManifold(gpu)
    uid = manifold.ingest_sync(b"payload", ManifoldCurvature.EUCLIDEAN_FLAT)
    tensor = manifold.tensors[uid]
    assert manifold.read_payload(tensor) == b"payload"
    report = manifold.overhead_report()
    assert report["operations"]["manifold.ingest"]["calls"] == 1
    assert report["operations"]["manifold.ingest"]["payload_bytes"] == 7
    assert report["operations"]["manifold.read_payload"]["calls"] == 1
    assert report["structural_bytes"] > 0
    assert report["truth"] == "measured"
    # stats() embeds the structural figure.
    assert manifold.stats()["overhead_bytes"] == report["structural_bytes"]


def test_measure_alloc_reports_real_peak():
    result, peak = measure_alloc(lambda: bytearray(1 << 20))
    assert len(result) == 1 << 20
    assert peak >= 1 << 20  # the 1 MiB allocation was actually measured


def test_container_bytes_is_structural_floor():
    n = container_bytes({"a": b"xyz"})
    assert n > 3  # dict + key + value headers exceed raw payload size


def test_overhead_meter_merge():
    a = OverheadMeter()
    b = OverheadMeter()
    with a.measure("op"):
        pass
    with b.measure("op"):
        pass
    a.merge(b)
    assert a.snapshot()["op"]["calls"] == 2
