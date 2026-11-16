"""Contract tests only: test fixtures must never be presented as production evidence."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from benchmarks.real_workload_benchmark import (
    MANIFEST_SCHEMA, discover, main, run_benchmark,
)


def _manifest(tmp_path: Path, path: Path, kind: str, *, digest: str | None = None) -> Path:
    doc = {
        "schema": MANIFEST_SCHEMA,
        "data_sources": [{
            "path": str(path),
            "kind": kind,
            "sha256": digest or hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_class": "TEST_FIXTURE_NON_PRODUCTION",
            "provenance": "generated exclusively for contract testing",
        }],
    }
    destination = tmp_path / "manifest.yaml"
    destination.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return destination


def test_refuses_empty_manifest_without_generating_inputs(tmp_path: Path):
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump({"schema": MANIFEST_SCHEMA, "data_sources": []}))
    with pytest.raises(ValueError, match="no operator-declared"):
        discover(path)
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.simulated
def test_rejects_modified_and_mismatched_assets(tmp_path: Path):
    tensor = tmp_path / "actual.npy"
    np.save(tensor, np.arange(32, dtype=np.int64))
    manifest = _manifest(tmp_path, tensor, "tensor", digest="0" * 64)
    from benchmarks.real_workload_benchmark import _read_verified
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        _read_verified(discover(manifest)[0])
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        run_benchmark(manifest, tmp_path / "state.sqlite3")
    assert not (tmp_path / "state.sqlite3").exists()


@pytest.mark.simulated
def test_rejects_unsupported_or_pickle_bearing_tensors(tmp_path: Path):
    serialized = tmp_path / "tensor.pt"
    serialized.write_bytes(b"not-a-trusted-numpy-tensor")
    with pytest.raises(ValueError, match="no safe registered decoder"):
        discover(_manifest(tmp_path, serialized, "tensor"))
    unsafe = tmp_path / "object.npy"
    np.save(unsafe, np.array([{"unsafe": "object"}], dtype=object))
    with pytest.raises(ValueError, match="invalid or unsafe"):
        run_benchmark(_manifest(tmp_path, unsafe, "tensor"), tmp_path / "state.sqlite3")


@pytest.mark.simulated
def test_real_execution_path_with_explicit_nonproduction_tensor_fixture(tmp_path: Path):
    tensor = tmp_path / "input.npy"
    np.save(tensor, np.arange(32, dtype=np.float64) / 17.0)
    result = run_benchmark(_manifest(tmp_path, tensor, "tensor"), tmp_path / "state.sqlite3", depth=3)
    assert result["result"] == "PASS"
    assert result["production_qualification"] == "UNVERIFIED"
    assert result["signed_evidence"] is False
    assert result["data_generated_by_benchmark"] is False
    entry = result["entries"][0]
    assert entry["source_class"] == "TEST_FIXTURE_NON_PRODUCTION"
    assert entry["workload"]["addition_exact_match"]
    assert entry["workload"]["pulvini"]["numerical_reconstruction_verified"]
    assert entry["workload"]["pulvini"]["complete_retained_bytes"] == (
        entry["workload"]["pulvini"]["working_set_bytes"]
        + entry["workload"]["pulvini"]["kernel_bytes"]
    )
    assert entry["workload"]["geodesic"]["endpoint_verified"]
    assert entry["custody_restart_roundtrip_verified"]


@pytest.mark.simulated
def test_snapshot_partial_unfold_and_durable_triad_reopen(tmp_path: Path):
    state = tmp_path / "existing.snapshot"
    state.write_bytes(bytes(range(128)) * 2 + b"x")
    result = run_benchmark(_manifest(tmp_path, state, "snapshot"), tmp_path / "state.sqlite3")
    workload = result["entries"][0]["workload"]
    assert workload["byte_exact_roundtrip_verified"]
    assert workload["partial_read_latency"]["count"] == 3
    assert workload["constant_time_complexity_proven"] is False
    assert result["entries"][0]["custody_restart_roundtrip_verified"]


@pytest.mark.simulated
def test_cli_fails_closed_on_missing_production_data(tmp_path: Path, capsys):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump({"schema": MANIFEST_SCHEMA, "data_sources": []}))
    output = tmp_path / "evidence.json"
    status = main(["--manifest", str(manifest), "--custody-db",
                   str(tmp_path / "custody.sqlite3"), "--output", str(output)])
    assert status == 2
    assert not output.exists()
    assert json.loads(capsys.readouterr().err)["result"] == "FAIL"


@pytest.mark.simulated
def test_cli_never_overwrites_input_or_custody_with_evidence(tmp_path: Path):
    state = tmp_path / "existing.snapshot"
    state.write_bytes(b"real bytes in a controlled non-production contract test")
    manifest = _manifest(tmp_path, state, "snapshot")
    db = tmp_path / "custody.sqlite3"
    assert main(["--manifest", str(manifest), "--custody-db", str(db),
                 "--output", str(state)]) == 2
    assert state.read_bytes() == b"real bytes in a controlled non-production contract test"

@pytest.mark.simulated
def test_cli_refuses_existing_output_before_custody_write(tmp_path: Path):
    snapshot = tmp_path / "existing.snapshot"
    snapshot.write_bytes(b"already-provided bytes in an explicit non-production test")
    manifest = _manifest(tmp_path, snapshot, "snapshot")
    destination = tmp_path / "evidence.json"
    destination.write_text('{"protected": true}', encoding="utf-8")
    custody = tmp_path / "custody.sqlite3"
    assert main(["--manifest", str(manifest), "--custody-db", str(custody),
                 "--output", str(destination)]) == 2
    assert json.loads(destination.read_text(encoding="utf-8")) == {"protected": True}
    assert not custody.exists()
