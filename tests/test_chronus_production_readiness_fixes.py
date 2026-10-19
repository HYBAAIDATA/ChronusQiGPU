from __future__ import annotations

import hashlib
import json

import pytest

from chronus.mining_bridge import submit_via_virtual_igpu
from chronus.virtual_igpu.abi import (
    ExecutionPolicy,
    Workload,
    WorkloadKind,
)
from chronus.virtual_igpu.adapters import (
    AdapterUnavailable,
    CPUEmulatorAdapter,
)
from chronus.virtual_igpu.client import ChronusClientError, ChronusClient
from chronus.virtual_igpu.evidence import EvidenceLedger, validate_receipt
from chronus.virtual_igpu.memory import VirtualMemoryPlane
from chronus.virtual_igpu.runtime import RuntimeDaemon


def _easy_target() -> str:
    return "ff" * 32


def test_unknown_kind_and_policy_fail_closed() -> None:
    with pytest.raises(ValueError, match="unsupported workload kind"):
        Workload(id="bad-kind", kind="typo", input={})
    with pytest.raises(ValueError, match="unsupported execution policy"):
        Workload(
            id="bad-policy",
            kind=WorkloadKind.PROBE,
            execution_policy="required_devce",
        )


def test_content_hash_tampering_is_rejected() -> None:
    with pytest.raises(ValueError, match="content_hash"):
        Workload(
            id="tampered",
            kind=WorkloadKind.PROBE,
            content_hash="0" * 64,
        )


def test_disabled_software_fallback_fails_closed(tmp_path) -> None:
    daemon = RuntimeDaemon(
        adapters=[CPUEmulatorAdapter()],
        store_dir=tmp_path / "runtime",
    )
    workload = Workload(
        id="no-fallback",
        kind=WorkloadKind.PROBE,
        allow_software_fallback=False,
    )
    with pytest.raises(AdapterUnavailable, match="fallback is disabled"):
        daemon.submit(workload)


def test_sha256d_hashes_header76_plus_nonce(tmp_path) -> None:
    header = bytes(range(76)) + (7).to_bytes(4, "little")
    daemon = RuntimeDaemon(
        adapters=[CPUEmulatorAdapter()],
        store_dir=tmp_path / "sha",
    )
    result = daemon.submit(
        Workload(
            id="sha",
            kind=WorkloadKind.SHA256D_SCAN,
            execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
            input={
                "header80_hex": header.hex(),
                "target_hex": _easy_target(),
                "start_nonce": 7,
                "count": 1,
            },
        )
    )
    expected = hashlib.sha256(
        hashlib.sha256(header[:76] + (7).to_bytes(4, "little")).digest()
    ).hexdigest()
    assert result.output["hits"][0]["hash_hex"] == expected
    assert result.output["checked"] == 1


def test_mining_bridge_independently_verifies_candidate(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("CHRONUS_VIGPU_STORE", str(tmp_path / "bridge"))
    header = bytes(range(76)) + (0).to_bytes(4, "little")
    result = submit_via_virtual_igpu(
        {"windows": [{"start": 0, "count": 1}]},
        header80=header,
        target_hex=_easy_target(),
        execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
    )
    assert result["host_verification"]["status"] == "passed"
    assert result["host_verification"]["verified_hits"][0]["host_verified"] is True


def test_tenant_scoped_handles_do_not_replace_ownership(tmp_path) -> None:
    memory = VirtualMemoryPlane(tmp_path / "memory")
    a = memory.store({"same": True}, tenant="a")
    b = memory.store({"same": True}, tenant="b")
    assert a.object_id != b.object_id
    assert memory.retrieve(a.object_id, tenant="a") == {"same": True}
    assert memory.retrieve(b.object_id, tenant="b") == {"same": True}
    with pytest.raises(PermissionError):
        memory.retrieve(a.object_id, tenant="b")


def test_ledger_reload_rejects_tampering(tmp_path) -> None:
    ledger = EvidenceLedger(tmp_path)
    ledger.append(
        workload_id="w",
        adapter_id="cpu-emulator",
        kind="probe",
        result_dict={"status": "ok"},
        receipt_dict={},
    )
    path = tmp_path / "evidence_ledger.jsonl"
    record = json.loads(path.read_text())
    record["result"]["status"] = "forged"
    path.write_text(json.dumps(record) + "\n")
    with pytest.raises(ValueError, match="content hash mismatch"):
        EvidenceLedger(tmp_path)


def test_receipt_expectations_bind_kernel_and_package() -> None:
    report = validate_receipt(
        {
            "trust_class": "runtime_signed",
            "hardware_rooted": False,
            "actual_backend": "cpu-emulator",
            "kernel_identity": "wrong",
            "package_version": "wrong",
        },
        expected_kernel="expected-kernel",
        expected_package="expected-package",
    )
    assert report["ok"] is False
    assert "kernel_identity mismatch" in report["errors"]
    assert "package_version mismatch" in report["errors"]


def test_remote_service_requires_https_off_loopback() -> None:
    with pytest.raises(ChronusClientError, match="requires HTTPS"):
        ChronusClient(
            delivery_mode="remote_service",
            endpoint="http://example.invalid",
            auth_token="token",
        )