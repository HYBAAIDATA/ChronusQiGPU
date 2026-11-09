"""Tests for Chronus ONE iGPU C++ Native SIMD and In-Place Dual Space Execution."""

import pytest  # noqa: F401
from chronus.execution.structural import fold_pair
from chronus.execution.native_simd import (
    NativeSIMDBackendAdapter,
    ResidentConfig,
    ResidentLogicalScheduler,
    dual_space_in_place_query,
    fold_pairs_vectorized,
    unfold_pairs_vectorized,
)


def test_fold_unfold_vectorized_matches_scalar_reference():
    # 32 pairs = 64 bytes
    data = bytes((i * 7 + 13) % 256 for i in range(64))
    folded = fold_pairs_vectorized(data)
    unfolded = unfold_pairs_vectorized(folded)

    assert len(folded) == len(data)
    assert len(unfolded) == len(data)
    assert unfolded == data

    # Verify each pair against the scalar M15 reference
    for i in range(32):
        a = data[2 * i]
        b = data[2 * i + 1]
        fa, fb = fold_pair(a, b)
        assert folded[2 * i] == fa
        assert folded[2 * i + 1] == fb


def test_in_place_dual_space_query_algebraic_equivalence():
    """Verify the core doctrine: q^T * x (mod 256) == (M^-1 q)^T * y (mod 256).

    Query evaluates directly on folded y without unfolding x.
    """
    raw_data = bytes((i * 17 + 23) % 256 for i in range(32))
    query = bytes((i * 31 + 5) % 256 for i in range(32))

    folded_data = fold_pairs_vectorized(raw_data)

    # 1. Uncompressed standard dot product: sum(q_i * x_i) mod 256
    uncompressed_dot = sum(q * x for q, x in zip(query, raw_data)) % 256

    # 2. In-place dual space dot product evaluated on folded data
    dual_space_dot = dual_space_in_place_query(query, folded_data)

    assert dual_space_dot == uncompressed_dot


def test_resident_logical_scaling_partitions():
    scheduler_80 = ResidentLogicalScheduler(ResidentConfig(virtual_units=80))
    scheduler_800 = ResidentLogicalScheduler(ResidentConfig(virtual_units=800))
    scheduler_8000 = ResidentLogicalScheduler(ResidentConfig(virtual_units=8000))

    payload_len = 65536
    tiles_80 = scheduler_80.partition_workload(payload_len)
    tiles_800 = scheduler_800.partition_workload(payload_len)
    tiles_8000 = scheduler_8000.partition_workload(payload_len)

    assert len(tiles_80) == 80
    assert len(tiles_800) == 800
    assert len(tiles_8000) <= 8000

    # Ensure all partitions are disjoint and cover the exact payload length
    assert tiles_80[0][0] == 0
    assert tiles_80[-1][1] == payload_len
    for (s1, e1), (s2, e2) in zip(tiles_80, tiles_80[1:]):
        assert s2 == e1


def test_native_simd_backend_adapter_execution():
    adapter = NativeSIMDBackendAdapter()
    assert adapter.is_available()
    probe = adapter.probe_silicon()
    assert probe["unified_memory_resident"] is True
    assert probe["virtual_units_resident"] == 8000

    raw = b"CHRONUS_IGPU_V36"  # 16 bytes = 8 pairs
    fold_res = adapter.execute(raw, "M15_SIMD_FOLD")
    assert fold_res["pairs_folded"] == 8
    folded = fold_res["output_bytes"]

    unfold_res = adapter.execute(folded, "M15_SIMD_UNFOLD")
    assert unfold_res["output_bytes"] == raw

    # Dual space query execution
    q = b"TEST_QUERY_BYTES"
    query_payload = q + folded
    q_res = adapter.execute(query_payload, "DUAL_SPACE_QUERY")
    assert "dual_space_inner_product" in q_res
    assert q_res["zero_unfold_evaluated"] is True
