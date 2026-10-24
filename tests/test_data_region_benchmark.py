"""Contract tests for current data evidence, not performance thresholds."""
import json

import numpy as np
import pytest

from aethel.phi_fold import PhiFoldError
from scripts import benchmark_data_region as benchmark


@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int64, np.complex128])
@pytest.mark.parametrize("region", [(slice(1, 4), slice(2, 6)), (slice(None), slice(None)), (2, slice(1, 4))])
def test_same_complete_output_for_every_comparator(dtype, region):
    data = np.arange(64).reshape(8, 8).astype(dtype)
    report = benchmark.benchmark_regions(data, region, depth=2, repetitions=2, warmups=1)
    assert report["bit_exact_all_calls"]
    assert set(report["elapsed_ns"]) == {
        "dense_direct_region", "full_decode_then_region", "folded_selective_region"}
    assert all(len(times) == 2 for times in report["elapsed_ns"].values())
    assert report["output_bytes"] == data[region].nbytes
    assert report["selective_read"]["requested_values"] == data[region].size
    assert report["selective_read"]["source_values_read"] == data[region].size
    assert report["resident_array_payload_bytes"] == data.nbytes
    assert report["physical_compression_ratio"] is None
    assert report["statistical_significance"] is None
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("kwargs", [{"repetitions": 0}, {"repetitions": True},
    {"warmups": -1}, {"depth": -1}, {"depth": 1.5}])
def test_invalid_run_configuration_refused(kwargs):
    with pytest.raises(ValueError):
        benchmark.benchmark_regions(np.ones((8, 8)), (slice(None), slice(None)), **kwargs)


def test_invalid_region_refused():
    with pytest.raises(PhiFoldError):
        benchmark.benchmark_regions(np.ones((8, 8)), (slice(0, 9), slice(None)))


def test_truncated_candidate_never_yields_success_report(monkeypatch):
    original = benchmark.unfold_region
    def truncated(*args):
        result, stats = original(*args)
        return result[:-1], stats
    monkeypatch.setattr(benchmark, "unfold_region", truncated)
    with pytest.raises(benchmark.BenchmarkValidationError, match="bit-identical"):
        benchmark.benchmark_regions(np.ones((8, 8)), (slice(1, 4), slice(2, 6)), repetitions=1)


def test_missing_dependency_is_not_a_successful_fallback(monkeypatch):
    def unavailable(*args, **kwargs):
        raise ImportError("required data engine unavailable")
    monkeypatch.setattr(benchmark, "phi_fold", unavailable)
    with pytest.raises(ImportError, match="unavailable"):
        benchmark.benchmark_regions(np.ones((8, 8)), (slice(None), slice(None)))


def test_cli_reproducible_input_and_does_not_mutate_global_rng(tmp_path):
    path = tmp_path / "report.json"
    np.random.seed(123)
    state = np.random.get_state()
    argv = ["--rows", "16", "--cols", "16", "--region", "1", "3", "2", "5",
            "--repetitions", "1", "--warmups", "0", "--output", str(path)]
    assert benchmark.main(argv) == 0
    first = json.loads(path.read_text())
    assert benchmark.main(argv) == 0
    second = json.loads(path.read_text())
    assert first["input_sha256"] == second["input_sha256"]
    assert first["output_sha256"] == second["output_sha256"]
    assert first["synthetic"] is True
    after = np.random.get_state()
    assert state[0] == after[0] and state[2:] == after[2:]
    np.testing.assert_array_equal(state[1], after[1])


def test_legacy_runner_is_withdrawn_without_loading_mining():
    import ast
    from pathlib import Path
    from benchmarks.production_workload_benchmarks import (
        LegacyBenchmarkUnavailable, ProductionWorkloadBenchmark,
    )
    with pytest.raises(LegacyBenchmarkUnavailable, match="unequal workloads"):
        ProductionWorkloadBenchmark()
    tree = ast.parse((Path(__file__).parents[1] / "benchmarks/production_workload_benchmarks.py").read_text())
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(name and "pythia_mining" in name for name in imports)


def test_current_ovid_authority_survives_projection_delete_and_restart(tmp_path):
    """Real disk-backed owners, no mock, Chronus dependency or mining path."""
    from aethel.ovid_authority import open_ovid_authority
    from aethel.theseus_projection import open_theseus_projection

    root = tmp_path / "ovid"
    authority = open_ovid_authority(root)
    payload = b"HYBA-data-authority-reference" * 8
    obj = authority.put(payload)
    projection = open_theseus_projection(tmp_path / "theseus", authority)
    generation = projection.rebuild()
    assert projection.lookup(obj.object_id).ovid_generation == generation
    projection.delete()
    # A fresh owner must recover the authoritative object without the index projection.
    reopened = open_ovid_authority(root)
    assert reopened.get_bytes(obj.object_id) == payload
    rebuilt = open_theseus_projection(tmp_path / "theseus", reopened)
    assert rebuilt.rebuild() == generation
    assert rebuilt.compare_to_ovid()["equal"] is True
