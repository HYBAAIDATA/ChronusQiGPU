"""THESEUS self-healing under crashes, concurrency, restarts and older stores.

Faults are real: bytes are corrupted directly in the SQLite file, crashes are
real process exits (``os._exit``) in a child interpreter, and concurrency uses
separate processes on one database file.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess
import sys
import textwrap
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import pytest

from chronus.storage.durable import DurableTheseusService
from chronus.storage.theseus import StorageIntegrityError

pytestmark = pytest.mark.real

SRC = str(Path(__file__).resolve().parents[1] / "src")
PAYLOAD = bytes((i * 131 + 7) % 256 for i in range(4096))


@pytest.fixture(autouse=True)
def _default_env(monkeypatch):  # mock-ok: sets environment configuration only; no behaviour is replaced
    monkeypatch.delenv("CHRONUS_SELF_HEALING", raising=False)  # mock-ok: sets environment configuration only; no behaviour is replaced
    monkeypatch.delenv("CHRONUS_SELF_HEALING_MAX_BYTES", raising=False)  # mock-ok: sets environment configuration only; no behaviour is replaced


def _corrupt(path, object_id, positions):
    with closing(sqlite3.connect(path)) as db, db:
        (blob,) = db.execute("SELECT payload FROM objects WHERE object_id=?", (object_id,)).fetchone()
        damaged = bytearray(blob)
        for p in positions:
            damaged[p] ^= 0xA5
        db.execute("UPDATE objects SET payload=? WHERE object_id=?", (bytes(damaged), object_id))


def _raw(path, object_id):
    with closing(sqlite3.connect(path)) as db:
        return bytes(db.execute("SELECT payload FROM objects WHERE object_id=?", (object_id,)).fetchone()[0])


def _events(path, kind=None):
    with closing(sqlite3.connect(path)) as db:
        rows = db.execute("SELECT object_id, kind, corrected_bytes FROM self_heal_events ORDER BY event_id").fetchall()
    return [r for r in rows if kind is None or r[1] == kind]


def _snapshot(path):
    with closing(sqlite3.connect(path)) as db:
        return {
            "objects": db.execute("SELECT object_id, size_bytes FROM objects ORDER BY object_id").fetchall(),
            "records": db.execute("SELECT * FROM records ORDER BY tenant_id, object_id").fetchall(),
            "journal": db.execute("SELECT * FROM journal ORDER BY tenant_id, sequence").fetchall(),
        }


def _run_child(code: str, path) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONPATH=SRC + os.pathsep + os.environ.get("PYTHONPATH", ""))
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code), str(path)],
        env=env, capture_output=True, text=True, timeout=120,
    )


def _damage_every_block(path, object_id, length, per_block=8):
    positions = [b + i * 3 for b in range(0, length, 32) for i in range(per_block) if b + i * 3 < length]
    _corrupt(path, object_id, positions)
    return positions


def test_repair_keeps_content_address_records_and_journal(tmp_path):
    path = tmp_path / "t.sqlite3"
    store = DurableTheseusService(str(path))
    record = store.store("tenant-a", PAYLOAD)
    store.store("tenant-b", PAYLOAD)
    before = _snapshot(path)
    _damage_every_block(path, record.object_id, len(PAYLOAD))
    reopened = DurableTheseusService(str(path))
    assert _snapshot(path) == before
    assert hashlib.sha256(_raw(path, record.object_id)).hexdigest() == record.object_id
    assert reopened.reconstruct("tenant-b", record.object_id) == PAYLOAD
    repaired = _events(path, "REPAIRED")
    assert len(repaired) == 1 and repaired[0][0] == record.object_id and repaired[0][2] == 8 * 128


def test_crash_between_write_back_and_commit_rolls_back_then_heals(tmp_path):
    """Kill the process after the repaired payload is written but before commit."""
    path = tmp_path / "t.sqlite3"
    record = DurableTheseusService(str(path)).store("tenant-a", PAYLOAD)
    _corrupt(path, record.object_id, [1, 2, 3, 100, 2000])
    damaged = _raw(path, record.object_id)
    child = _run_child(
        """
        import os, sys
        from chronus.storage import durable
        def crash(db, object_id, kind, corrected, detail):  # mock-ok: injects a real process crash after the UPDATE, before COMMIT
            if kind == "REPAIRED":
                os._exit(17)
        durable.DurableTheseusService._log_heal = staticmethod(crash)  # mock-ok: crash-injection point only
        durable.DurableTheseusService(sys.argv[1])
        """,
        path,
    )
    assert child.returncode == 17, child.stderr
    # The uncommitted write-back is gone: still the damaged bytes, no event.
    assert _raw(path, record.object_id) == damaged
    assert _events(path) == []
    store = DurableTheseusService(str(path))
    assert _raw(path, record.object_id) == PAYLOAD
    assert [e[1] for e in _events(path)] == ["REPAIRED"]
    assert store.reconstruct("tenant-a", record.object_id) == PAYLOAD


def test_committed_repair_survives_immediate_process_exit(tmp_path):
    path = tmp_path / "t.sqlite3"
    record = DurableTheseusService(str(path)).store("tenant-a", PAYLOAD)
    _corrupt(path, record.object_id, [5, 6, 7])
    child = _run_child(
        """
        import os, sys
        from chronus.storage.durable import DurableTheseusService
        DurableTheseusService(sys.argv[1])
        os._exit(0)  # no close, no checkpoint
        """,
        path,
    )
    assert child.returncode == 0, child.stderr
    assert _raw(path, record.object_id) == PAYLOAD
    assert [e[1] for e in _events(path)] == ["REPAIRED"]


def _open_and_read(args):
    path, tenant, object_id = args
    store = DurableTheseusService(path)
    return store.reconstruct(tenant, object_id)


def test_concurrent_processes_repair_once(tmp_path):
    path = tmp_path / "t.sqlite3"
    store = DurableTheseusService(str(path))
    record = store.store("tenant-a", PAYLOAD)
    _damage_every_block(path, record.object_id, len(PAYLOAD), per_block=4)
    env_path = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = SRC + os.pathsep + env_path
    try:
        with ProcessPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(_open_and_read, [(str(path), "tenant-a", record.object_id)] * 8))
    finally:
        os.environ["PYTHONPATH"] = env_path
    assert results == [PAYLOAD] * 8
    assert [e[1] for e in _events(path)] == ["REPAIRED"]


def test_repair_concurrent_with_writers_and_readers(tmp_path):
    path = tmp_path / "t.sqlite3"
    store = DurableTheseusService(str(path))
    damaged_record = store.store("tenant-a", PAYLOAD)
    _damage_every_block(path, damaged_record.object_id, len(PAYLOAD))

    def write(i):
        payload = hashlib.sha256(str(i).encode()).digest() * 64
        rec = store.store(f"tenant-{i % 3}", payload)
        return store.reconstruct(f"tenant-{i % 3}", rec.object_id) == payload

    def read(_):
        return store.reconstruct("tenant-a", damaged_record.object_id) == PAYLOAD

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(write, i) for i in range(24)] + [pool.submit(read, i) for i in range(8)]
        assert all(f.result() for f in futures)
    assert [e[1] for e in _events(path)] == ["REPAIRED"]
    reopened = DurableTheseusService(str(path))
    assert reopened.self_healing_status()["protected_objects"] == reopened.self_healing_status()["objects"] == 25


def test_unrecoverable_corruption_fails_closed_across_restarts(tmp_path):
    path = tmp_path / "t.sqlite3"
    record = DurableTheseusService(str(path)).store("tenant-a", PAYLOAD)
    _corrupt(path, record.object_id, range(64, 64 + 9))  # 9 bytes in one block: beyond t = 8
    damaged = _raw(path, record.object_id)
    for _ in range(3):
        with pytest.raises(StorageIntegrityError):
            DurableTheseusService(str(path))
    assert _raw(path, record.object_id) == damaged  # never overwritten with a guess
    assert [e[1] for e in _events(path)] == ["UNREPAIRABLE"]  # recorded once, not per retry


def _legacy_store(path, payloads):
    """A store as written before parity existed (no parity tables at all)."""
    store = DurableTheseusService(str(path), self_healing=False)
    records = [store.store("tenant-a", p) for p in payloads]
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("DROP INDEX self_heal_events_object")
        db.execute("DROP TABLE self_heal_events")
        db.execute("DROP TABLE object_parity")
    return records


def test_existing_database_without_parity_opens_and_is_backfilled(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    payloads = [PAYLOAD, b"small", bytes(300 * 1024)]  # last one is over the 256 KiB default bound
    records = _legacy_store(path, payloads)
    before = _snapshot(path)
    store = DurableTheseusService(str(path))
    assert _snapshot(path) == before
    status = store.self_healing_status()
    assert status["objects"] == 3 and status["protected_objects"] == 2
    assert sorted(e[0] for e in _events(path, "PARITY_BACKFILLED")) == sorted(r.object_id for r in records[:2])
    for rec, payload in zip(records, payloads):
        assert store.reconstruct("tenant-a", rec.object_id) == payload
    # A backfilled object is now repairable; the unprotected one still fails closed.
    _corrupt(path, records[0].object_id, [0, 1, 2])
    _corrupt(path, records[2].object_id, [0])
    assert store.reconstruct("tenant-a", records[0].object_id) == PAYLOAD
    with pytest.raises(StorageIntegrityError):
        store.reconstruct("tenant-a", records[2].object_id)
    # Reopening does not backfill twice.
    _corrupt(path, records[2].object_id, [0])  # undo the flip so the store opens
    DurableTheseusService(str(path))
    assert len(_events(path, "PARITY_BACKFILLED")) == 2


def test_damaged_legacy_object_without_parity_fails_closed(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    (record,) = _legacy_store(path, [PAYLOAD])
    _corrupt(path, record.object_id, [10])
    with pytest.raises(StorageIntegrityError):
        DurableTheseusService(str(path))
    assert [(e[1]) for e in _events(path)] == ["UNREPAIRABLE"]


def test_disabled_store_reads_existing_parity_database_unchanged(tmp_path):
    path = tmp_path / "t.sqlite3"
    record = DurableTheseusService(str(path)).store("tenant-a", PAYLOAD)
    strict = DurableTheseusService(str(path), self_healing=False)
    assert strict.reconstruct("tenant-a", record.object_id) == PAYLOAD
    _corrupt(path, record.object_id, [0])
    with pytest.raises(StorageIntegrityError):
        strict.reconstruct("tenant-a", record.object_id)
    assert _events(path) == []
