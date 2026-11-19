"""Fault-injection tests for THESEUS bounded self-healing (RS parity sidecar).

Each test corrupts bytes directly in the SQLite file, the way a storage fault
would, then checks that the store detects it and either repairs it (within the
Reed-Solomon bound, verified by SHA-256) or fails closed.
"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing

import pytest

from chronus.storage import self_heal
from chronus.storage.durable import DurableTheseusService
from chronus.storage.theseus import StorageIntegrityError
from chronus.triad import ProductionTriad

pytestmark = pytest.mark.real

PAYLOAD = bytes((i * 37 + 11) % 256 for i in range(200))


def _corrupt(path, object_id: str, positions) -> bytes:
    with closing(sqlite3.connect(path)) as db, db:
        (blob,) = db.execute("SELECT payload FROM objects WHERE object_id=?", (object_id,)).fetchone()
        damaged = bytearray(blob)
        for p in positions:
            damaged[p] ^= 0xA5
        db.execute("UPDATE objects SET payload=? WHERE object_id=?", (bytes(damaged), object_id))
        db.commit()
    return bytes(damaged)


def _raw(path, object_id: str) -> bytes:
    with closing(sqlite3.connect(path)) as db, db:
        return bytes(db.execute("SELECT payload FROM objects WHERE object_id=?", (object_id,)).fetchone()[0])


def _events(path):
    with closing(sqlite3.connect(path)) as db, db:
        return [r[0] for r in db.execute("SELECT kind FROM self_heal_events ORDER BY event_id")]


@pytest.fixture(autouse=True)
def _default_env(monkeypatch):  # mock-ok: sets environment configuration only; no behaviour is replaced
    monkeypatch.delenv("CHRONUS_SELF_HEALING", raising=False)  # mock-ok: sets environment configuration only; no behaviour is replaced
    monkeypatch.delenv("CHRONUS_SELF_HEALING_MAX_BYTES", raising=False)  # mock-ok: sets environment configuration only; no behaviour is replaced


def test_enabled_by_default_and_writes_parity(tmp_path):
    store = DurableTheseusService(str(tmp_path / "t.sqlite3"))
    store.store("tenant-a", PAYLOAD)
    status = store.evidence()["self_healing"]
    assert status["enabled"] is True
    assert status["protected_objects"] == status["objects"] == 1
    assert status["repairs"] == 0


def test_corruption_detected_and_repaired_on_reopen(tmp_path):
    path = tmp_path / "t.sqlite3"
    record = DurableTheseusService(str(path)).store("tenant-a", PAYLOAD)
    # 8 bytes in block 0 (the maximum per block) plus 3 more in other blocks
    damaged = _corrupt(path, record.object_id, [0, 3, 7, 12, 18, 22, 27, 31, 40, 100, 199])
    assert hashlib.sha256(damaged).hexdigest() != record.object_id

    reopened = DurableTheseusService(str(path))  # verify_store detects and heals
    assert _raw(path, record.object_id) == PAYLOAD  # written back
    assert reopened.reconstruct("tenant-a", record.object_id) == PAYLOAD
    events = reopened.self_heal_events()
    assert [e["kind"] for e in events] == ["REPAIRED"]
    assert events[0]["corrected_bytes"] == 11
    assert reopened.evidence()["self_healing"]["repairs"] == 1


def test_corruption_repaired_on_read_path(tmp_path):
    path = tmp_path / "t.sqlite3"
    store = DurableTheseusService(str(path))
    record = store.store("tenant-a", PAYLOAD)
    _corrupt(path, record.object_id, [5, 50, 150])
    assert store.reconstruct("tenant-a", record.object_id) == PAYLOAD
    assert _events(path) == ["REPAIRED"]


def test_beyond_bound_fails_closed_and_is_recorded(tmp_path):
    path = tmp_path / "t.sqlite3"
    record = DurableTheseusService(str(path)).store("tenant-a", PAYLOAD)
    original = _corrupt(path, record.object_id, list(range(9)))  # 9 > t=8 in one block
    with pytest.raises(StorageIntegrityError):
        DurableTheseusService(str(path))
    assert _raw(path, record.object_id) == original  # nothing written
    assert _events(path) == ["UNREPAIRABLE"]


def test_length_change_fails_closed(tmp_path):
    path = tmp_path / "t.sqlite3"
    record = DurableTheseusService(str(path)).store("tenant-a", PAYLOAD)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("UPDATE objects SET payload=? WHERE object_id=?", (PAYLOAD[:-1], record.object_id))
        db.commit()
    with pytest.raises(StorageIntegrityError):
        DurableTheseusService(str(path))


def test_corrupted_parity_cannot_forge_and_is_regenerated(tmp_path):
    path = tmp_path / "t.sqlite3"
    record = DurableTheseusService(str(path)).store("tenant-a", PAYLOAD)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("UPDATE object_parity SET parity=? WHERE object_id=?", (b"\x00" * 10, record.object_id))
        db.commit()
    reopened = DurableTheseusService(str(path))  # payload intact; parity rebuilt
    assert _events(path) == ["PARITY_REGENERATED"]
    _corrupt(path, record.object_id, [1, 2])
    assert reopened.reconstruct("tenant-a", record.object_id) == PAYLOAD


def test_disabled_by_env_keeps_strict_fail_closed(tmp_path, monkeypatch):  # mock-ok: sets environment configuration only; no behaviour is replaced
    monkeypatch.setenv("CHRONUS_SELF_HEALING", "0")  # mock-ok: sets environment configuration only; no behaviour is replaced
    path = tmp_path / "t.sqlite3"
    store = DurableTheseusService(str(path))
    record = store.store("tenant-a", PAYLOAD)
    assert store.self_healing_status()["protected_objects"] == 0
    _corrupt(path, record.object_id, [0])
    with pytest.raises(StorageIntegrityError):
        DurableTheseusService(str(path))


def test_objects_over_size_bound_are_not_protected(tmp_path, monkeypatch):  # mock-ok: sets environment configuration only; no behaviour is replaced
    monkeypatch.setenv("CHRONUS_SELF_HEALING_MAX_BYTES", "64")  # mock-ok: sets environment configuration only; no behaviour is replaced
    path = tmp_path / "t.sqlite3"
    store = DurableTheseusService(str(path))
    record = store.store("tenant-a", PAYLOAD)
    assert store.self_healing_status()["protected_objects"] == 0
    _corrupt(path, record.object_id, [0])
    with pytest.raises(StorageIntegrityError):
        store.reconstruct("tenant-a", record.object_id)
    assert _events(path) == ["UNREPAIRABLE"]


def test_invalid_env_value_rejected(monkeypatch):  # mock-ok: sets environment configuration only; no behaviour is replaced
    monkeypatch.setenv("CHRONUS_SELF_HEALING", "maybe")  # mock-ok: sets environment configuration only; no behaviour is replaced
    with pytest.raises(ValueError):
        self_heal.self_healing_enabled()


def test_heal_payload_never_returns_bytes_off_the_content_address():
    parity = self_heal.encode_parity(PAYLOAD)
    wrong_id = hashlib.sha256(b"something else").hexdigest()
    outcome = self_heal.heal_payload(PAYLOAD, wrong_id, parity, len(PAYLOAD))
    assert not outcome.ok and outcome.repaired is None


def test_production_triad_materialises_through_storage_fault(tmp_path):
    path = tmp_path / "triad.sqlite3"
    triad = ProductionTriad(str(path))
    source = b"production payload " * 20
    receipt = triad.put("tenant-a", source)
    _corrupt(path, receipt.representation_object_id, [0, 33, 66, 99])
    _corrupt(path, receipt.receipt_object_id, [4, 8])

    reopened = ProductionTriad(str(path))
    assert reopened.materialise(receipt) == source
    assert reopened.verify(receipt) is True
    posture = reopened.production_posture()["durable_custody"]["self_healing"]
    assert posture["enabled"] is True and posture["repairs"] == 2


def test_repeated_failed_reads_do_not_grow_the_audit_log(tmp_path, monkeypatch):  # mock-ok: sets environment configuration only; no behaviour is replaced
    monkeypatch.setenv("CHRONUS_SELF_HEALING_MAX_BYTES", "64")  # mock-ok: sets environment configuration only; no behaviour is replaced
    path = tmp_path / "t.sqlite3"
    store = DurableTheseusService(str(path))
    record = store.store("tenant-a", PAYLOAD)  # above the limit: no sidecar
    _corrupt(path, record.object_id, [0])
    for _ in range(3):
        with pytest.raises(StorageIntegrityError):
            store.reconstruct("tenant-a", record.object_id)
    assert _events(path) == ["UNREPAIRABLE"]
    assert store.self_healing_status()["unrepairable_objects"] == 1


@pytest.mark.parametrize("column,value", [("n", 0), ("k", 48), ("scheme", "other")])
def test_damaged_sidecar_metadata_fails_closed_then_is_regenerated(tmp_path, column, value):
    path = tmp_path / "t.sqlite3"
    store = DurableTheseusService(str(path))
    record = store.store("tenant-a", PAYLOAD)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(f"UPDATE object_parity SET {column}=? WHERE object_id=?", (value, record.object_id))
        db.commit()
    _corrupt(path, record.object_id, [3])
    with pytest.raises(StorageIntegrityError):  # not ZeroDivisionError / ReedSolomonError
        store.reconstruct("tenant-a", record.object_id)
    assert _events(path) == ["UNREPAIRABLE"]
    # restore the payload; reopening rebuilds the sidecar, which then repairs again
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("UPDATE objects SET payload=? WHERE object_id=?", (PAYLOAD, record.object_id))
        db.commit()
    reopened = DurableTheseusService(str(path))
    assert _events(path)[-1] == "PARITY_REGENERATED"
    _corrupt(path, record.object_id, [3])
    assert reopened.reconstruct("tenant-a", record.object_id) == PAYLOAD


def test_lowered_limit_still_maintains_existing_sidecar(tmp_path, monkeypatch):  # mock-ok: sets environment configuration only; no behaviour is replaced
    path = tmp_path / "t.sqlite3"
    record = DurableTheseusService(str(path)).store("tenant-a", PAYLOAD)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("UPDATE object_parity SET parity=? WHERE object_id=?", (b"\x01" * 4, record.object_id))
        db.commit()
    monkeypatch.setenv("CHRONUS_SELF_HEALING_MAX_BYTES", "16")  # mock-ok: sets environment configuration only; no behaviour is replaced
    reopened = DurableTheseusService(str(path))
    assert _events(path) == ["PARITY_REGENERATED"]
    _corrupt(path, record.object_id, [9])
    assert reopened.reconstruct("tenant-a", record.object_id) == PAYLOAD


def test_limit_is_capped_at_encoder_maximum_and_large_writes_succeed(tmp_path, monkeypatch):  # mock-ok: sets environment configuration only; no behaviour is replaced
    monkeypatch.setenv("CHRONUS_SELF_HEALING_MAX_BYTES", str(8 << 20))  # mock-ok: sets environment configuration only; no behaviour is replaced
    monkeypatch.setenv("CHRONUS_MAX_PAYLOAD_BYTES", str(2 << 20))  # mock-ok: sets environment configuration only; no behaviour is replaced
    assert self_heal.self_healing_max_bytes() == self_heal.encoder_max_bytes() == 1 << 20
    store = DurableTheseusService(str(tmp_path / "t.sqlite3"))
    big = bytes(range(256)) * ((1 << 20) // 256 + 1)  # just over 1 MiB
    record = store.store("tenant-a", big)
    assert store.reconstruct("tenant-a", record.object_id) == big
    status = store.self_healing_status()
    assert status["protected_objects"] == 0 and status["max_protected_bytes"] == 1 << 20


def test_concurrent_readers_share_one_repair(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "t.sqlite3"
    store = DurableTheseusService(str(path))
    record = store.store("tenant-a", PAYLOAD)
    _corrupt(path, record.object_id, [0, 40, 80, 120, 160])
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: store.reconstruct("tenant-a", record.object_id), range(6)))
    assert results == [PAYLOAD] * 6
    assert _events(path) == ["REPAIRED"]


def test_heal_locks_are_released_after_repair(tmp_path):
    path = tmp_path / "t.sqlite3"
    store = DurableTheseusService(str(path))
    record = store.store("tenant-a", PAYLOAD)
    _corrupt(path, record.object_id, [0, 1])
    assert store.reconstruct("tenant-a", record.object_id) == PAYLOAD
    assert store._heal_locks == {}


def test_restoring_existing_content_keeps_its_sidecar(tmp_path):
    path = tmp_path / "t.sqlite3"
    store = DurableTheseusService(str(path))
    store.store("tenant-a", PAYLOAD)
    store.store("tenant-b", PAYLOAD)  # same content: no second sidecar, still protected
    status = store.self_healing_status()
    assert status["objects"] == status["protected_objects"] == 1
