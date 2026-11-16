import json

import numpy as np

from ga.mathcore import (
    GALOIS,
    OQS_AVAILABLE,
    SHAMIR,
    Persistence,
    PhyllotaxisLattice,
    PostQuantum,
    RicciFlowOptimizer,
    SegmentedWAL,
    YangMillsConnection,
)


def test_weighted_forman_curvature_and_flow_are_dynamic():
    optimizer = RicciFlowOptimizer(dim=2, k=3)
    optimizer.set_points(np.array([[0, 0], [1, 0], [0, 1], [1, 1]]), steps=0)
    assert all(
        optimizer.curvature(i, j) == 0
        for i in optimizer.graph
        for j in optimizer.graph[i]
        if i < j
    )
    optimizer.graph = {0: {1: 1.0}, 1: {0: 1.0, 2: 1.0}, 2: {1: 1.0}}
    optimizer.flow(1)
    assert optimizer.graph[0][1] > 1.0
    assert optimizer.geodesic_distance(0, 2) == (
        optimizer.graph[0][1] + optimizer.graph[1][2]
    )


def test_yang_mills_uses_operator_commutators():
    connection = YangMillsConnection(dim=2)
    a = np.array([[0, 1], [1, 0]], dtype=complex)
    b = np.array([[1, 0], [0, -1]], dtype=complex)
    connection.register("a", a)
    assert np.array_equal(connection.field_strength(a, b), a @ b - b @ a)
    assert np.array_equal(
        connection.parallel_transport(np.array([1, 0]), ["a"]),
        np.array([1, 1j]),
    )


def test_post_quantum_capability_detection_is_explicit():
    post_quantum = PostQuantum()
    assert post_quantum.enabled is OQS_AVAILABLE
    post_quantum.init_keys()
    if not OQS_AVAILABLE:
        assert post_quantum.kem is None
        assert post_quantum.signer is None


def test_shamir_round_trip_and_threshold_boundary():
    shares = SHAMIR.split(b"abcdefghi", 3, 5)
    assert SHAMIR.combine(shares[:3], 9) == b"abcdefghi"
    assert SHAMIR.combine(shares[1:4], 9) == b"abcdefghi"
    assert SHAMIR.combine(shares[:2], 9) != b"abcdefghi"
    assert GALOIS.mul(3, GALOIS.inv(3)) == 1


def test_segmented_wal_rotates_and_drops_only_a_partial_tail(tmp_path):
    wal = SegmentedWAL(tmp_path, max_bytes=10)
    wal.append(json.dumps({"n": 1}))
    wal.append(json.dumps({"n": 2}))
    wal.close()
    assert len(wal.segments()) == 2
    with wal.segments()[-1].open("a", encoding="utf-8") as file_handle:
        file_handle.write('{"partial":')
    records, stats = wal.replay()
    assert records == [{"n": 1}, {"n": 2}]
    assert stats["partial_dropped"] == 1


def test_persistence_snapshot_and_restore(tmp_path):
    lattice = PhyllotaxisLattice(capacity=101)
    index = lattice.store("alpha", {"value": 1})
    persistence = Persistence(str(tmp_path), lattice)
    persistence.append("alpha", lattice.data[index])
    snapshot = persistence.snapshot()
    assert snapshot == {"signed": False, "records": 1}

    restored = PhyllotaxisLattice(capacity=101)
    stats = Persistence(str(tmp_path), restored).load()
    assert stats["restored"] == 1
    assert restored.retrieve("alpha")["value"] == {"value": 1}
