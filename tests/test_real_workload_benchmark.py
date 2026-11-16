"""Contract tests only: test fixtures must never be presented as production evidence."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path

import numpy as np
import pytest
import yaml

from benchmarks.real_workload_benchmark import (
    MANIFEST_SCHEMA, discover, main, run_benchmark,
)

pytestmark = pytest.mark.simulated


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


def test_cli_refuses_manifest_and_hardlink_alias_as_output(tmp_path: Path):
    state = tmp_path / "existing.snapshot"
    original = b"real bytes in a controlled non-production contract test"
    state.write_bytes(original)
    manifest = _manifest(tmp_path, state, "snapshot")
    manifest_bytes = manifest.read_bytes()
    db = tmp_path / "custody.sqlite3"
    assert main(["--manifest", str(manifest), "--custody-db", str(db),
                 "--output", str(manifest)]) == 2
    assert manifest.read_bytes() == manifest_bytes
    alias = tmp_path / "alias.snapshot"
    os.link(state, alias)
    assert main(["--manifest", str(manifest), "--custody-db", str(db),
                 "--output", str(alias)]) == 2
    assert state.read_bytes() == original


def test_tiny_npy_with_oversized_declared_shape_is_rejected_before_allocation(tmp_path: Path):
    header = b"{'descr': '<f8', 'fortran_order': False, 'shape': (1000000000,), }"
    header += b" " * (64 - ((10 + len(header) + 1) % 64)) + b"\n"
    crafted = b"\x93NUMPY\x01\x00" + len(header).to_bytes(2, "little") + header + b"\x00" * 8
    tensor = tmp_path / "bomb.npy"
    tensor.write_bytes(crafted)
    with pytest.raises(ValueError, match="outside finite-value/element limits"):
        run_benchmark(_manifest(tmp_path, tensor, "tensor"), tmp_path / "state.sqlite3")


def test_custody_payload_limit_boundary_accounts_for_odd_padding(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CHRONUS_MAX_PAYLOAD_BYTES", "1024")
    at_limit = tmp_path / "even.snapshot"
    at_limit.write_bytes(b"x" * 1024)
    assert discover(_manifest(tmp_path, at_limit, "snapshot"))[0]["size_bytes"] == 1024
    odd_under = tmp_path / "odd.snapshot"
    odd_under.write_bytes(b"x" * 1023)
    assert discover(_manifest(tmp_path, odd_under, "snapshot"))[0]["size_bytes"] == 1023
    over = tmp_path / "over.snapshot"
    over.write_bytes(b"x" * 1025)
    with pytest.raises(ValueError, match="outside byte policy"):
        discover(_manifest(tmp_path, over, "snapshot"))
