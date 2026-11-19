"""Protected THESEUS integration using real maintained SQLite/WAL custody.

These are correctness/fault-injection tests, not simulated production telemetry.
"""
from dataclasses import replace
import pytest

from chronus.storage.durable import DurableTheseusService
from chronus.storage.protected import ProtectedTheseusService
from chronus.triad import ProductionTriad

pytestmark = pytest.mark.real


@pytest.mark.parametrize("payload", [
    b"A", b"hello!", bytes(range(255)), b"x" * 1023,
    bytes(range(256)) * 128,
])
def test_real_restart_and_single_shard_loss(tmp_path, payload):
    database = str(tmp_path / "actual-theseus.sqlite3")
    root = tmp_path / "shards"
    first = ProtectedTheseusService(DurableTheseusService(database), root)
    receipt = first.store("tenant-A", payload, shard_count=4)
    assert first.reconstruct(receipt) == payload

    # New canonical custody instance, NOT the process-local compatibility store.
    second = ProtectedTheseusService(DurableTheseusService(database), root)
    assert second.reconstruct(receipt) == payload

    # A genuinely persisted shard FILE is removed, then a third service opens.
    folder = second._directory("tenant-A", receipt.payload_sha256)
    (folder / "1.shard").unlink()
    third = ProtectedTheseusService(DurableTheseusService(database), root)
    assert third.reconstruct(receipt) == payload


def test_one_corrupt_shard_recovers_but_two_fail_closed(tmp_path):
    database = str(tmp_path / "custody.sqlite3")
    service = ProtectedTheseusService(
        DurableTheseusService(database), tmp_path / "shards",
    )
    payload = b"external-redundancy" * 19
    receipt = service.store("tenant-A", payload)
    folder = service._directory("tenant-A", receipt.payload_sha256)
    first = folder / "0.shard"
    first.write_bytes(b"?" * len(first.read_bytes()))
    assert service.reconstruct(receipt) == payload
    (folder / "2.shard").unlink()
    with pytest.raises(ValueError, match="multiple failures"):
        service.reconstruct(receipt)


def test_tenant_access_and_modified_receipt_fail_closed(tmp_path):
    service = ProtectedTheseusService(
        DurableTheseusService(str(tmp_path / "x.sqlite3")),
        tmp_path / "shards",
    )
    receipt = service.store("tenant-A", b"payload")
    with pytest.raises(KeyError):
        service.reconstruct(replace(receipt, tenant_id="tenant-B"))
    with pytest.raises(ValueError, match="mismatch"):
        service.reconstruct(replace(receipt, payload_sha256="0" * 64))


def test_symlink_and_immutable_conflict_rejected(tmp_path):
    service = ProtectedTheseusService(
        DurableTheseusService(str(tmp_path / "y.sqlite3")),
        tmp_path / "shards",
    )
    receipt = service.store("tenant-A", b"protected-secret")
    folder = service._directory("tenant-A", receipt.payload_sha256)
    (folder / "0.shard").unlink()
    (folder / "0.shard").symlink_to(folder / "1.shard")
    with pytest.raises(ValueError, match="symlink"):
        service.reconstruct(receipt)
    with pytest.raises(ValueError, match="symlink"):
        service.store("tenant-A", b"protected-secret")


def test_canonical_triad_entrypoint_with_reopen(tmp_path):
    path = str(tmp_path / "triad.sqlite3")
    root = tmp_path / "shards"
    first = ProductionTriad(path)
    payload = b"real-app-bytes" * 10
    receipt = first.protect_payload("tenant-A", payload, root, shard_count=3)
    reopened = ProductionTriad(path)
    assert reopened.recover_protected_payload(receipt, root) == payload
    folder = root / __import__("hashlib").sha256(b"tenant-A").hexdigest() / receipt.payload_sha256
    (folder / "0.shard").unlink()
    again = ProductionTriad(path)
    assert again.recover_protected_payload(receipt, root) == payload
    assert again.theseus.verify_journal_continuity("tenant-A")

def test_oversized_corrupt_shard_is_bounded_one_erasure(tmp_path):
    service = ProtectedTheseusService(
        DurableTheseusService(str(tmp_path / "bounded.sqlite3")),
        tmp_path / "shards",
    )
    source = b"observed-bytes" * 128
    receipt = service.store("tenant-A", source)
    folder = service._directory("tenant-A", receipt.payload_sha256)
    # Actual oversized file is not read into memory; its size fails policy.
    (folder / "0.shard").write_bytes(b"x" * 500_000)
    assert service.reconstruct(receipt) == source
    (folder / "1.shard").write_bytes(b"y" * 500_000)
    with pytest.raises(ValueError, match="multiple failures"):
        service.reconstruct(receipt)
