import base64
import hashlib
import json
from pathlib import Path

import pytest

from chronus.virtual_igpu.abi import ABI_VERSION, Workload, WorkloadKind
from chronus.virtual_igpu.adapters import CPUEmulatorAdapter
from chronus.virtual_igpu.attestation import replay, verify
from chronus.virtual_igpu.runtime import (
    Quota, RuntimeConfig, RuntimeDaemon, RuntimeInvariantError,
)


def workload(kind, value, wid="w1", tenant="tenant-a"):
    return Workload(id=wid, kind=kind, input=value, tenant=tenant)


def runtime(tmp_path, **kwargs):
    return RuntimeDaemon(
        RuntimeConfig(store_root=str(tmp_path), **kwargs),
        adapters=[CPUEmulatorAdapter()],
    )


def test_abi_is_versioned_and_required_fields_fail_closed():
    assert ABI_VERSION == "virtual_igpu_v1"
    with pytest.raises(ValueError):
        Workload(id="", kind=WorkloadKind.FOLD, input={}, tenant="t")


def test_daemon_fails_closed_without_adapters(tmp_path):
    with pytest.raises(RuntimeInvariantError, match="no execution adapter"):
        RuntimeDaemon(RuntimeConfig(store_root=str(tmp_path)), adapters=[])


def test_end_to_end_fold_is_attested_persisted_and_content_addressed(tmp_path):
    daemon = runtime(tmp_path)
    result = daemon.submit(workload(WorkloadKind.FOLD, {"payload_utf8": "chronus"}))
    assert result.status == "ok"
    assert result.digest and result.attestation
    assert result.object_id and result.evidence_digest
    artifact = daemon.memory.retrieve("tenant-a", "w1")
    assert artifact["result"]["digest"] == result.digest
    evidence = tmp_path / "evidence-ledger" / f"{result.evidence_digest}.json"
    assert evidence.is_file()
    assert hashlib.sha256(evidence.read_bytes()).hexdigest() == result.evidence_digest


def test_fold_unfold_roundtrip(tmp_path):
    daemon = runtime(tmp_path)
    folded = daemon.submit(
        workload(WorkloadKind.FOLD, {"payload_b64": base64.b64encode(b"fold me").decode()})
    )
    restored = daemon.submit(
        workload(WorkloadKind.UNFOLD, folded.output, wid="w2")
    )
    assert base64.b64decode(restored.output["payload_b64"]) == b"fold me"


def test_scheduler_uses_policy_not_insertion_index(tmp_path):
    low = CPUEmulatorAdapter()
    low.id, low.priority = "z-low", -100
    high = CPUEmulatorAdapter()
    high.id, high.priority = "a-high", 50
    daemon = RuntimeDaemon(
        RuntimeConfig(store_root=str(tmp_path)), adapters=[low, high]
    )
    assert daemon.submit(workload(WorkloadKind.PHI_TRANSFORM, {"vector": [1]})).executed_on == "a-high"


def test_refusal_and_quota_are_recorded_or_enforced(tmp_path):
    daemon = runtime(tmp_path)
    daemon.quotas["tenant-a"] = Quota(max_workloads=0)
    with pytest.raises(RuntimeInvariantError, match="quota"):
        daemon.submit(workload(WorkloadKind.FOLD, {"payload_utf8": "x"}))


def test_attestation_replay_and_forgery_detection():
    records = [{"a": 1}, {"b": 2}]
    chain = replay(records, b"key")
    assert verify(records, chain, b"key")
    assert not verify([{"a": 9}, {"b": 2}], chain, b"key")


def test_checkpoint_and_migration(tmp_path):
    daemon = runtime(tmp_path)
    result = daemon.submit(workload(WorkloadKind.FOLD, {"payload_utf8": "x"}))
    checkpoint = daemon.memory.checkpoint()
    assert Path(checkpoint["path"]).is_file()
    daemon.memory.migrate(result.object_id, "next-adapter")
    assert daemon.memory.residency[result.object_id] == "next-adapter"