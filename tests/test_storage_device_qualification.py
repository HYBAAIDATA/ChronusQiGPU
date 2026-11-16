"""Non-production contract tests; never use these fixture timings as evidence."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

import pytest
import yaml
from benchmarks.qualify_storage_performance import main, measure

pytestmark = pytest.mark.simulated


def manifest_of(folder: Path, payloads: list[bytes]) -> Path:
    assets = []
    for i, payload in enumerate(payloads):
        file = folder / f"observed-{i}.snapshot"
        file.write_bytes(payload)
        assets.append({
            "path": str(file), "kind": "snapshot",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "source_class": "TEST_FIXTURE_NON_PRODUCTION",
            "provenance": "contract-test-only",
        })
    manifest = folder / "manifest.yaml"
    manifest.write_text(yaml.safe_dump({
        "schema": "chronus.real-workload-manifest/1", "data_sources": assets
    }), encoding="utf-8")
    return manifest


def test_distinct_writes_reopen_and_no_physical_qualification(tmp_path):
    manifest = manifest_of(tmp_path, [b"first", b"second-distinct-content"])
    result = measure(manifest, tmp_path)
    assert result["distinct_source_count"] == 2
    assert result["input_classification"] == "TEST_FIXTURE_NON_PRODUCTION"
    assert result["write_application"]["count"] == 2
    assert result["read_application"]["count"] == 2
    assert result["all_payloads_byte_exact"]
    assert result["fresh_service_restart_verified"]
    assert result["physical_device_iops"] is None
    assert result["power_loss_recovery"] is None
    assert result["production_qualified"] is False
    assert not list(tmp_path.glob("chronus-device-reference-*"))


def test_reject_same_payload_twice_before_storage(tmp_path):
    manifest = manifest_of(tmp_path, [b"same", b"same"])
    with pytest.raises(ValueError, match="duplicate source content"):
        measure(manifest, tmp_path)
    assert not list(tmp_path.glob("chronus-device-reference-*"))


def test_reject_source_mutation_before_storage(tmp_path):
    manifest = manifest_of(tmp_path, [b"before"])
    (tmp_path / "observed-0.snapshot").write_bytes(b"after")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        measure(manifest, tmp_path)
    assert not list(tmp_path.glob("chronus-device-reference-*"))


def test_refuse_unknown_target_and_output_alias(tmp_path):
    manifest = manifest_of(tmp_path, [b"one"])
    with pytest.raises(ValueError, match="existing non-symlink"):
        measure(manifest, tmp_path / "nonexistent")
    assert main(["--manifest", str(manifest), "--target-directory", str(tmp_path),
                 "--output", str(tmp_path / "observed-0.snapshot")]) == 2
    assert (tmp_path / "observed-0.snapshot").read_bytes() == b"one"


def test_never_overwrite_existing_evidence(tmp_path):
    manifest = manifest_of(tmp_path, [b"one"])
    output = tmp_path / "evidence.json"
    args = ["--manifest", str(manifest), "--target-directory", str(tmp_path),
            "--output", str(output)]
    assert main(args) == 0
    result = json.loads(output.read_text())
    assert result["status"] == "MEASURED_LOCAL_APPLICATION_REFERENCE"
    assert result["physical_disk_model"] is None
    assert result["production_qualified"] is False
    assert main(args) == 2
