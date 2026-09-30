from __future__ import annotations

import hashlib

import pytest

from gpu.provenance import ProvenanceError, validate_provenance
from gpu.readiness import ProductionEvidence, production_readiness
from gpu.reference import (
    grover_hendrix_iterate,
    grover_iterate,
    matmul_f4,
    matvec_f4,
    qfi_pure,
    sha256_midstate,
    sha256d,
    sha256d_merkle,
    sha256d_scan,
    sha256d_verify,
)
from igpu.seam.types import KERNEL_CLASS, KernelName
from gpu.tensor import TensorMeasurement


def test_matrix_references():
    assert matmul_f4([[1, 2]], [[3], [4]]) == [[11]]
    assert matvec_f4([[1, 2], [3, 4]], [5, 6]) == [17, 39]


def test_qfi_and_grover_references():
    assert qfi_pure([1, 0], [0, 1]) == pytest.approx(4.0)
    expected = grover_iterate([0.5] * 4, [2])
    assert grover_hendrix_iterate([0.5] * 4, [2], [3, 2, 1, 0]) == expected


def test_sha256d_operations():
    payload = b"payload"
    digest = sha256d(payload)
    assert sha256d_verify(payload, digest)
    assert not sha256d_verify(payload + b"x", digest)
    assert sha256d_merkle(b"\x00" * 32, b"\x01" * 32) == sha256d(
        b"\x00" * 32 + b"\x01" * 32
    )


def test_midstate_is_compression_state_not_padded_digest():
    block = bytes(range(64))
    assert len(sha256_midstate(block)) == 32
    assert sha256_midstate(block) != hashlib.sha256(block).digest()


def test_scan_counts_only_executed_hashes():
    header = b"\x00" * 80
    result = sha256d_scan(header, b"\xff" * 32, count=8)
    assert result.nonce == 0
    assert result.hashes_computed == 1
    assert result.digest == sha256d(b"\x00" * 80)


def test_production_provenance_fails_closed_on_placeholders():
    record = {
        "repo_sha": "a" * 40,
        "pr": "test",
        "human_merge_sha": None,
        "change_bundles": [],
        "replay": {"agent_versions": {}, "seed": 1517, "substrate_freeze_sha": "x"},
    }
    with pytest.raises(ProvenanceError, match="real PR identifier"):
        validate_provenance(record, production=True)


def test_seam_advertises_reference_sha256d_operations():
    assert KernelName.sha256d_midstate in KERNEL_CLASS
    assert KernelName.sha256d_merkle in KERNEL_CLASS


def test_tensor_measurement_never_claims_hashrate():
    measurement = TensorMeasurement(5_000_000_000_000, 1_000_000_000, "test")
    assert measurement.tflops == pytest.approx(5.0)
    assert measurement.as_dict()["hashrate_hps"] is None


def test_production_readiness_requires_external_evidence(monkeypatch):
    monkeypatch.setattr(
        "gpu.readiness.audit_software_surfaces",
        lambda: (),
    )
    report = production_readiness(ProductionEvidence())
    assert report["software_ready"] is True
    assert report["production_ready"] is False
    assert all(not gate["passed"] for gate in report["gates"])
