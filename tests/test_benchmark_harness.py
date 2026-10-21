"""Tests for the exact per-domain Lucas benchmark contract."""
from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "benchmark_harness.py"
SPEC = importlib.util.spec_from_file_location("benchmark_harness", MODULE_PATH)
assert SPEC and SPEC.loader
benchmark_harness = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = benchmark_harness
SPEC.loader.exec_module(benchmark_harness)

BenchmarkHarness = benchmark_harness.BenchmarkHarness
DEFAULT_SCALE_MATRIX = benchmark_harness.DEFAULT_SCALE_MATRIX
LucasScaleMatrix = benchmark_harness.LucasScaleMatrix
canonical_json_bytes = benchmark_harness.canonical_json_bytes
fibonacci = benchmark_harness.fibonacci
lucas = benchmark_harness.lucas
make_workload = benchmark_harness.make_workload
pqsc_nonce_order = benchmark_harness.pqsc_nonce_order
quadratic_query_bound = benchmark_harness.quadratic_query_bound
run_classical = benchmark_harness.run_classical
run_pqsc = benchmark_harness.run_pqsc
run_quantum_model = benchmark_harness.run_quantum_model
verify_artifact = benchmark_harness.verify_artifact
verify_metric = benchmark_harness.verify_metric
SEED = bytes(32)


def spec(matrix=None, bits=8):
    return make_workload("unit", SEED, nonce_bits=bits, target_prefix_bytes=1, scale_matrix=matrix)


def test_exact_lucas_ladder():
    assert [lucas(i) for i in (7, 10, 12, 15, 18, 20, 31, 50, 76)] == [29, 123, 322, 1364, 5778, 15127, 3010349, 28143753123, 7639424778862807]
    assert [fibonacci(i) for i in range(8)] == [0, 1, 1, 2, 3, 5, 8, 13]


def test_matrix_has_independent_powers():
    matrix = LucasScaleMatrix.from_dict(DEFAULT_SCALE_MATRIX)
    assert len({matrix.power(domain) for domain in ("search", "memory", "tensor", "virtual_quantum", "hardware")}) > 1
    assert matrix.scale_integer("hardware", 1) == 24475
    assert matrix.scale_integer("memory", 1) == 1


def test_workload_fingerprint_binds_the_whole_matrix():
    a = spec()
    altered = dict(DEFAULT_SCALE_MATRIX)
    altered["tensor"] = 20
    b = spec(altered)
    assert a.fingerprint() != b.fingerprint()
    assert a.scale_matrix.as_dict()["tensor"]["power"] == 12
    assert b.scale_matrix.as_dict()["tensor"]["power"] == 20


def test_dimensions_use_different_domains():
    s = spec()
    d = s.dimensions
    assert d.search_space == s.scale_matrix.scale_integer("search", 1 << 8)
    assert d.memory_units == s.scale_matrix.scale_integer("memory", 1)
    assert d.tensor_width == s.scale_matrix.scale_integer("tensor", 1)
    assert d.hardware_cores == s.scale_matrix.scale_integer("hardware", 1)
    assert d.virtual_state_dimension == 1 << d.virtual_qubits


def test_all_paths_share_workload_but_not_one_scale():
    s = spec()
    results = [run_classical(s), run_pqsc(s), run_quantum_model(s)]
    assert all(result.workload_fingerprint == s.fingerprint() for result in results)
    assert all(result.scale_matrix == s.scale_matrix.as_dict() for result in results)
    assert all(result.dimensions == s.dimensions.as_dict() for result in results)
    assert all(result.verified for result in results)


def test_pqsc_schedule_is_complete_and_disjoint():
    s = spec()
    order = list(pqsc_nonce_order(s))
    assert len(order) == s.search_space
    assert len(set(order)) == s.search_space
    assert set(order) == set(range(s.nonce_min, s.nonce_max))


def test_tamper_is_rejected():
    s = spec()
    result = run_classical(s)
    assert not verify_metric(s, dataclasses.replace(result, digest_hex="00" * 32))
    changed = dict(result.dimensions)
    changed["tensor_width"] += 1
    assert not verify_metric(s, dataclasses.replace(result, dimensions=changed))


def test_quantum_is_model_only():
    result = run_quantum_model(spec())
    assert result.kind == "modeled"
    assert result.hardware_provenance == "UNPROVEN_NO_QPU_BACKEND"
    assert result.wall_time_ns is None
    assert result.operations == quadratic_query_bound(spec().search_space)


def test_artifact_seal_and_reproducible_outcomes():
    kwargs = dict(master_seed=SEED, nonce_bits=8, target_prefix_bytes=1, trials=1, scale_matrix=DEFAULT_SCALE_MATRIX)
    a = BenchmarkHarness(**kwargs).run("artifact")
    b = BenchmarkHarness(**kwargs).run("artifact")
    assert verify_artifact(a)
    assert a["workload"]["fingerprint_sha256"] == b["workload"]["fingerprint_sha256"]
    assert [(r["runner"], r["nonce"], r["digest_hex"]) for r in a["results"]] == [(r["runner"], r["nonce"], r["digest_hex"]) for r in b["results"]]
    a["results"][0]["operations"] += 1
    assert not verify_artifact(a)


def test_invalid_matrix_fails_closed():
    bad = dict(DEFAULT_SCALE_MATRIX)
    bad.pop("tensor")
    with pytest.raises(ValueError):
        spec(bad)
