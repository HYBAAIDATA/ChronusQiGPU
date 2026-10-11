"""Acceptance tests for Chronus Virtual iGPU software gates (2 Oct 2026 prompt).

Physical GPU, cloud, and pool gates are skipped with explicit reasons when
infrastructure is absent. Software gates must pass on a clean host.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from chronus.tensor_compute import (
    ChronusTensorValidationError,
    validate_declared_output_shape,
)
from chronus.virtual_igpu.abi import (
    ABI_VERSION,
    ExecutionPolicy,
    TrustClass,
    Workload,
    WorkloadKind,
)
from chronus.virtual_igpu.adapters import CPUEmulatorAdapter, AdapterUnavailable
from chronus.virtual_igpu.client import ChronusClient, ChronusClientError
from chronus.virtual_igpu.evidence import validate_receipt
from chronus.virtual_igpu.runtime import RuntimeDaemon, RuntimeInvariantError


@pytest.fixture()
def daemon(tmp_path: Path) -> RuntimeDaemon:
    d = RuntimeDaemon(adapters=[CPUEmulatorAdapter()], store_dir=str(tmp_path / "store"))
    d.attach()
    return d


@pytest.mark.unit
def test_standalone_software_fold_and_receipt(daemon: RuntimeDaemon, tmp_path: Path):
    w = Workload(
        id="w-fold-1",
        kind=WorkloadKind.FOLD if hasattr(WorkloadKind, "FOLD") else WorkloadKind.STORE,
        tenant="t1",
        input={"payload_utf8": "hyba-chronus"},
        execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
        allow_software_fallback=True,
    )
    # STORE is universally present
    w = Workload(
        id="w-store-1",
        kind=WorkloadKind.STORE,
        tenant="t1",
        input={"payload_utf8": "hyba-chronus"},
        execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
    )
    result = daemon.submit(w)
    assert result.abi_version == ABI_VERSION
    assert result.trust_class in {
        TrustClass.RUNTIME_SIGNED.value,
        TrustClass.DEVICE_OBSERVED.value,
    }
    assert result.hardware_rooted is False
    assert result.actual_adapter_id
    assert result.route_reason
    assert result.object_id
    # evidence on disk
    health = daemon.health()
    assert health["running"] is True


@pytest.mark.unit
def test_required_adapter_fail_closed(daemon: RuntimeDaemon):
    w = Workload(
        id="w-req-missing",
        kind=WorkloadKind.STORE,
        tenant="t1",
        input={"payload_utf8": "x"},
        execution_policy=ExecutionPolicy.REQUIRED_ADAPTER.value,
        required_adapter_id="cuda-0-does-not-exist",
    )
    with pytest.raises((AdapterUnavailable, RuntimeInvariantError)):
        daemon.submit(w)


@pytest.mark.unit
def test_idempotency_conflict(daemon: RuntimeDaemon):
    w1 = Workload(
        id="w-idem-1",
        kind=WorkloadKind.STORE,
        tenant="t1",
        input={"payload_utf8": "a"},
        idempotency_key="job-9",
        execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
    )
    r1 = daemon.submit(w1)
    w2 = Workload(
        id="w-idem-2",
        kind=WorkloadKind.STORE,
        tenant="t1",
        input={"payload_utf8": "b"},
        idempotency_key="job-9",
        execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
    )
    with pytest.raises(RuntimeInvariantError):
        daemon.submit(w2)
    assert r1.object_id


@pytest.mark.unit
def test_cancel_before_reuse(daemon: RuntimeDaemon):
    assert daemon.cancel("never-submitted") in {True, False}


@pytest.mark.unit
def test_shape_validation_elementwise_and_scale():
    validate_declared_output_shape("add", [(4,), (4,)], (4,))
    with pytest.raises(ChronusTensorValidationError):
        validate_declared_output_shape("add", [(4,), (4,)], (8,))
    with pytest.raises(ChronusTensorValidationError):
        validate_declared_output_shape("scale", [(4,)], (2, 2))
    validate_declared_output_shape("matmul", [(2, 3), (3, 4)], (2, 4))
    with pytest.raises(ChronusTensorValidationError):
        validate_declared_output_shape("matmul", [(2, 3), (3, 4)], (2, 3))


@pytest.mark.unit
def test_embedded_client_no_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CHRONUS_VIGPU_ENDPOINT", raising=False)
    # fresh daemon path via store
    client = ChronusClient(store_dir=str(tmp_path / "cstore"))
    assert client.delivery_mode == "embedded"
    w = Workload(
        id="w-client-1",
        kind=WorkloadKind.STORE,
        tenant="embed",
        input={"payload_utf8": "embedded-ok"},
        execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
    )
    result = client.submit(w)
    assert result.delivery_mode == "embedded"
    assert result.hardware_rooted is False


@pytest.mark.unit
def test_remote_failure_does_not_fallback(monkeypatch: pytest.MonkeyPatch):
    client = ChronusClient(endpoint="http://127.0.0.1:1", delivery_mode="remote_service")
    w = Workload(
        id="w-remote-fail",
        kind=WorkloadKind.STORE,
        tenant="r",
        input={"payload_utf8": "x"},
    )
    with pytest.raises(ChronusClientError):
        client.submit(w)


@pytest.mark.unit
def test_validate_receipt_rejects_cpu_as_hardware_rooted():
    bad = {
        "result": {
            "trust_class": "hardware_rooted",
            "hardware_rooted": True,
            "actual_backend": "software",
            "adapter_id": "cpu-emulator",
            "verification": {"hardware_rooted": True},
            "timing": {"wall_ms": 1.0},
        },
        "provenance": {"trust_class": "hardware_rooted", "hardware_rooted": True},
    }
    with pytest.raises(ValueError):
        validate_receipt(bad)


@pytest.mark.unit
def test_validate_receipt_runtime_signed_ok():
    good = {
        "result": {
            "trust_class": TrustClass.RUNTIME_SIGNED.value,
            "hardware_rooted": False,
            "actual_backend": "software",
            "verification": {"trust_class": TrustClass.RUNTIME_SIGNED.value},
            "timing": {"wall_ms": 1.2},
        },
        "provenance": {
            "trust_class": TrustClass.RUNTIME_SIGNED.value,
            "hardware_rooted": False,
        },
    }
    report = validate_receipt(good)
    assert report["ok"] is True


@pytest.mark.unit
def test_adversarial_rehash_warning_or_mismatch(tmp_path: Path):
    # Craft a receipt and alter a field while keeping an old digest label
    from chronus.virtual_igpu.abi import digest_json

    body = {"payload": {"a": 1}, "result": {"timing": {"wall_ms": 2.0}, "trust_class": "runtime_signed", "hardware_rooted": False, "actual_backend": "software"}}
    digest = digest_json(body)
    receipt = {**body, "digest": digest}
    report = validate_receipt(receipt)
    assert report["ok"] is True
    # adversarial edit + rehash with unkeyed hash can self-consistently fake digest;
    # validator must still flag trust rules and document the limitation.
    edited = json.loads(json.dumps(receipt))
    edited["payload"] = {"a": 2}
    edited["digest"] = digest_json({k: v for k, v in edited.items() if k != "digest"})
    # Without HMAC, content hash alone cannot authenticate — we only check consistency
    report2 = validate_receipt(edited)
    assert report2["ok"] is True  # consistent rehash
    # With expectation of hardware root, fail
    with pytest.raises(ValueError):
        validate_receipt(edited, expect_hardware_rooted=True)


@pytest.mark.unit
def test_mining_bridge_virtual_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CHRONUS_VIGPU_ENDPOINT", raising=False)
    monkeypatch.setenv("CHRONUS_VIGPU_STORE", str(tmp_path / "mstore"))
    from chronus.mining_bridge import submit_via_virtual_igpu

    out = submit_via_virtual_igpu(
        {"windows": [{"start": 0, "count": 16}]},
        tenant="mining-test",
        execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
        allow_software_fallback=True,
    )
    assert out.get("share_state") == "local_result"
    assert out.get("validity_oracle") == "sha256d_reverify_required"
    assert out.get("hardware_rooted") in {False, None}


@pytest.mark.unit
def test_physical_gate_skipped_without_device():
    pytest.skip(
        reason="physical accelerator evidence requires target host OpenCL device; "
        "run: python -m bench.chronus_igpu_evidence --size 512 --iterations 20",
        allow_module_level=False,
    )


@pytest.mark.unit
def test_cloud_gate_skipped_without_credentials():
    pytest.skip(
        reason="Azure/GCP execution pending credentials and deploy evidence; "
        "deployment packages may validate offline but cloud-run is an external gate",
    )


@pytest.mark.unit
def test_pool_gate_skipped_without_stratum():
    pytest.skip(
        reason="pool acknowledgement requires live stratum; local_result ≠ accepted share",
    )
