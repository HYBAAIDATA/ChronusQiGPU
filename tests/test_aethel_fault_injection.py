import json
import os
import sys
import types
from unittest.mock import Mock

import pytest

from aethel.errors import EngineUnavailable, GapDetected, StorageCorruption
from aethel.gpu import TensorCoreGPU_Context
from aethel.manifold import ManifoldCurvature, PrimeStorageManifold
from aethel.storage import AddressSpace


def test_snapshot_crash_before_journal_publish_keeps_old_snapshot(tmp_path, monkeypatch):
    store = tmp_path / "store"
    space = AddressSpace()
    first = space.write(b"first")
    space.snapshot(store)
    second = space.write(b"second")
    original_replace = os.replace

    def crash_journal(source, destination):
        if os.fspath(destination).endswith("ledger.jsonl"):
            raise OSError("injected failure")
        return original_replace(source, destination)

    monkeypatch.setattr("aethel.storage.os.replace", crash_journal)
    with pytest.raises(OSError):
        space.snapshot(store)

    restored = AddressSpace.attach(store)
    assert restored.read(restored.address_of_index(first.index)) == b"first"
    with pytest.raises(GapDetected):
        restored.read(restored.address_of_index(second.index))


def test_attach_rejects_payload_digest_mismatch_without_exposing_bytes(tmp_path):
    store = tmp_path / "store"
    space = AddressSpace()
    address = space.write(b"original payload")
    space.snapshot(store)
    (store / "blocks" / f"{address.index}.blk").write_bytes(b"tampered payload")

    with pytest.raises(StorageCorruption, match="digest"):
        AddressSpace.attach(store)


def test_attach_rejects_truncated_and_regressed_journal(tmp_path):
    store = tmp_path / "store"
    space = AddressSpace()
    space.write(b"one")
    space.write(b"two")
    space.snapshot(store)
    journal = store / "ledger.jsonl"
    records = [json.loads(line) for line in journal.read_text().splitlines()]

    records[1]["seq"] = 4
    journal.write_text("".join(json.dumps(record) + "\n" for record in records))
    with pytest.raises(StorageCorruption, match="journal"):
        AddressSpace.attach(store)

    journal.write_bytes(journal.read_bytes().rstrip(b"\n")[:-3])
    with pytest.raises(StorageCorruption):
        AddressSpace.attach(store)


def test_recover_backs_up_and_truncates_to_verified_prefix(tmp_path):
    store = tmp_path / "store"
    space = AddressSpace()
    space.write(b"recoverable")
    space.write(b"also recoverable")
    space.snapshot(store)
    journal = store / "ledger.jsonl"
    with journal.open("ab") as handle:
        handle.write(b'{"seq":2')

    assert AddressSpace.truncate_to_last_consistent_prefix(store) == 2
    assert (store / "ledger.jsonl.bak").is_file()
    assert AddressSpace.attach(store).verify()


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_snapshot_rejects_symlinked_blocks_directory(tmp_path):
    store = tmp_path / "store"
    other = tmp_path / "outside"
    other.mkdir()
    store.mkdir()
    os.chmod(store, 0o700)
    (store / "blocks").symlink_to(other, target_is_directory=True)
    space = AddressSpace()
    space.write(b"not written through symlink")

    with pytest.raises(StorageCorruption, match="symlink"):
        space.snapshot(store)
    assert list(other.iterdir()) == []


def test_manifold_heals_digest_verified_copy_and_fails_closed_without_one():
    manifold = PrimeStorageManifold(TensorCoreGPU_Context())
    uid = manifold.ingest_sync(b"healthy backup", ManifoldCurvature.GOLDEN_DENSE)
    tensor = manifold.tensors[uid]
    tensor.sparse_topology = {0: 0}
    assert manifold.read_payload(tensor) == b"healthy backup"

    uid = manifold.ingest_sync(b"unrecoverable", ManifoldCurvature.GOLDEN_DENSE)
    tensor = manifold.tensors[uid]
    tensor.sparse_topology = {0: 0}
    tensor.raw_payload = None
    manifold.curved_storage.uuid_index.pop(uid, None)
    assert manifold.read_payload(tensor) is None
    assert [event["kind"] for event in manifold.self_healing.heal_log] == [
        "prime_exponent_restore",
        "unrecoverable",
    ]


def test_geodesic_fallback_is_observable_and_matches_query_delegation(monkeypatch):
    class BrokenPathfinder:
        def __init__(self, **_kwargs):
            raise RuntimeError("simulated unavailable pathfinder")

    module = types.ModuleType("Intelligence.pathfinder")
    module.Pathfinder = BrokenPathfinder
    monkeypatch.setitem(sys.modules, "Intelligence.pathfinder", module)
    manifold = PrimeStorageManifold(TensorCoreGPU_Context())
    expected = b"bisection result"
    query = Mock(return_value=expected)
    monkeypatch.setattr(manifold.geodesic, "query", query)

    assert manifold.geodesic.query_geodesic(__import__("numpy").zeros(11)) == expected
    query.assert_called_once()
    assert manifold.query_evidence == {
        "backend": "bisection",
        "fallback": True,
        "reason": "pathfinder_error:RuntimeError",
    }


def test_geodesic_fallback_can_be_denied(monkeypatch):
    class MissingPathfinder:
        def __init__(self, **_kwargs):
            raise ImportError("not installed")

    module = types.ModuleType("Intelligence.pathfinder")
    module.Pathfinder = MissingPathfinder
    monkeypatch.setitem(sys.modules, "Intelligence.pathfinder", module)
    manifold = PrimeStorageManifold(TensorCoreGPU_Context())
    with pytest.raises(EngineUnavailable):
        manifold.geodesic.query_geodesic(
            __import__("numpy").zeros(11), allow_fallback=False
        )
    assert manifold.query_evidence["fallback"] is False
    assert manifold.query_fallbacks == 0


def test_gpu_opcode_0x15_policy_records_fallback_and_fails_when_required():
    class UnsupportedPunchHost:
        use_opencl = True
        backend = "opencl:gpu"

        def run_punch_batch(self, opcode, **_kwargs):
            assert opcode == 0x15
            raise NotImplementedError

    auto = TensorCoreGPU_Context(punch_host=UnsupportedPunchHost())
    auto.project_and_collapse_pv(__import__("numpy").ones(11))
    assert auto.projection_backend == "cpu"
    assert auto.fallback_reason == "opcode_0x15_unsupported"

    required = TensorCoreGPU_Context(
        punch_host=UnsupportedPunchHost(), require_gpu=True
    )
    with pytest.raises(RuntimeError, match="fallback denied"):
        required.project_and_collapse_pv(__import__("numpy").ones(11))


def test_gpu_cpu_fallback_can_be_disabled():
    with pytest.raises(RuntimeError, match="execution policy"):
        TensorCoreGPU_Context(allow_cpu_fallback=False)
