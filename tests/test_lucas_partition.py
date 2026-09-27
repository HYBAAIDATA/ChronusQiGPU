"""T4 — Lucas-weighted partitioner invariants.

Coverage, disjointness, determinism and the weighting property: faces with
better historical yield receive larger windows, not smaller. The fake
scheduler below exists only inside this test module — it exercises the
partition contract without touching hardware and is never used in
production paths.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hyba.hybrid.lucas_partition import (
    FACE_COUNT,
    TraversalHistory,
    partition,
)
from hyba.hybrid.nonce_scheduler import DeviceCapability


class FakeScheduler:
    """Test-only scheduler: reports an injected capability, does no work."""

    def __init__(self, device_id: str, hps: float, supported: bool = True):
        self._cap = DeviceCapability(
            device_id=device_id,
            device_class="gpu",
            measured_hashes_per_sec=hps,
            supported=supported,
            reason_if_unsupported=None if supported else "test-unsupported",
        )

    def capability(self):
        return self._cap

    def dispatch(self, window):
        raise NotImplementedError

    def poll(self, handle):
        return None

    def cancel(self, handle):
        return None

    def attestation(self):
        return []


def _assert_tiles(spans, total_span):
    """Intervals tile [0, total_span) exactly — disjoint, covering, non-empty."""
    cursor = 0
    for s in sorted(spans, key=lambda x: x.base_nonce):
        assert s.span > 0, "empty window emitted"
        assert s.base_nonce == cursor, f"gap or overlap at {s.base_nonce}"
        cursor += s.span
    assert cursor == total_span, f"coverage ends at {cursor}, expected {total_span}"


def test_disjoint_and_covering_over_random_instances():
    rng = random.Random(20260926)
    for _ in range(10_000):
        span = rng.randint(1, 2_000_000)
        n_dev = rng.randint(1, 4)
        devices = [
            FakeScheduler(f"dev{i}", hps=rng.uniform(1e6, 1e12))
            for i in range(n_dev)
        ]
        spans, cert = partition(span, devices, TraversalHistory())
        _assert_tiles(spans, span)
        assert cert.verify()


def test_determinism_byte_identical():
    devices = [FakeScheduler("a", 1e7), FakeScheduler("b", 5e7)]
    hist = TraversalHistory()
    hist.append(3, "a", True, 100)
    hist.append(5, "b", False, 200)
    s1, c1 = partition(1 << 20, devices, hist)
    s2, c2 = partition(1 << 20, devices, hist)
    assert c1.digest == c2.digest
    assert [x.as_dict() for x in s1] == [x.as_dict() for x in s2]


def test_even_split_covers_and_is_disjoint():
    devices = [FakeScheduler("a", 1e7), FakeScheduler("b", 1e7)]
    spans, cert = partition(1 << 20, devices, TraversalHistory(), strategy="even")
    _assert_tiles(spans, 1 << 20)
    assert cert.verify()
    totals = {}
    for s in spans:
        totals[s.device_id] = totals.get(s.device_id, 0) + s.span
    assert max(totals.values()) - min(totals.values()) <= 1


def test_weighting_favors_productive_faces():
    """Hot faces (low miss rate) get larger spans than the same faces cold."""
    devices = [FakeScheduler("gpu0", 1e7)]
    span = 1 << 20

    cold_hist = TraversalHistory()
    for f in range(FACE_COUNT):
        for _ in range(4):
            cold_hist.append(f, "gpu0", False, 100)

    hot_hist = TraversalHistory()
    hot_faces = {1, 5, 8, 13}
    for f in range(FACE_COUNT):
        for _ in range(4):
            hot_hist.append(f, "gpu0", f in hot_faces, 100)

    cold_spans, _ = partition(span, devices, cold_hist)
    hot_spans, _ = partition(span, devices, hot_hist)

    cold_by_face = {s.face: s.span for s in cold_spans}
    hot_by_face = {s.face: s.span for s in hot_spans}

    improved = 0
    for f in hot_faces:
        hot_span = hot_by_face.get(f, 0)
        cold_span = cold_by_face.get(f, 0)
        assert hot_span >= cold_span, (
            f"hot face {f} shrank: {cold_span} -> {hot_span}"
        )
        if hot_span > cold_span:
            improved += 1
    assert improved > 0, "no hot face grew under productive history"


def test_every_nonce_exactly_once_lucas_strategy():
    devices = [FakeScheduler("a", 1e7), FakeScheduler("b", 2e7)]
    for span in (32, 33, 31, 1_000_003):
        spans, cert = partition(span, devices, TraversalHistory())
        _assert_tiles(spans, span)
        assert cert.verify()
