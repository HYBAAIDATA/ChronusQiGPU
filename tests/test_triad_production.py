"""Production custody and triad close-out tests."""

from __future__ import annotations

import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from chronus.ovid.transform import OvidTransformService
from chronus.storage.durable import DurableTheseusService
from chronus.storage.theseus import StorageIntegrityError
from chronus.triad import ProductionTriad

pytestmark = pytest.mark.real


def test_ovid_transform_round_trip_even_and_odd_payloads():
    ovid = OvidTransformService()
    for payload in (b"ab", b"abc", bytes(range(255))):
        representation = ovid.fold(payload)
        assert representation.source_sha256 == hashlib.sha256(payload).hexdigest()
        assert representation.representation_sha256 == hashlib.sha256(
            representation.payload
        ).hexdigest()
        assert ovid.materialise(representation) == payload
    assert ovid.manifest()["durable_authority"] is False


def test_theseus_survives_fresh_process_style_reopen(tmp_path):
    path = tmp_path / "theseus.sqlite3"
    first = DurableTheseusService(str(path), lane_count=8)
    record = first.store("tenant-a", b"durable-state")
    entry = first.append_journal_event("tenant-a", "STATE_COMMITTED", b"durable-state")
    assert entry.sequence == 0
    assert first.verify_journal_continuity("tenant-a") is True

    reopened = DurableTheseusService(str(path), lane_count=8)
    assert reopened.reconstruct("tenant-a", record.object_id) == b"durable-state"
    assert reopened.verify_journal_continuity("tenant-a") is True
    assert reopened.stats()["durable"] is True
    assert reopened.evidence()["integrity"] == "PASS"


def test_theseus_tenant_isolation_survives_restart(tmp_path):
    path = tmp_path / "theseus.sqlite3"
    store = DurableTheseusService(str(path))
    a = store.store("tenant-a", b"same-content")
    store.store("tenant-b", b"same-content")
    reopened = DurableTheseusService(str(path))
    assert reopened.reconstruct("tenant-a", a.object_id) == b"same-content"
    assert reopened.reconstruct("tenant-b", a.object_id) == b"same-content"
    with pytest.raises(KeyError):
        reopened.reconstruct("tenant-c", a.object_id)


def test_theseus_fails_closed_on_durable_payload_corruption(tmp_path):
    path = tmp_path / "theseus.sqlite3"
    store = DurableTheseusService(str(path))
    record = store.store("tenant-a", b"original")
    store.append_journal_event("tenant-a", "STATE_COMMITTED", b"original")
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE objects SET payload=? WHERE object_id=?",
            (b"tampered", record.object_id),
        )
        db.commit()
    with pytest.raises(StorageIntegrityError):
        DurableTheseusService(str(path))


def test_theseus_concurrent_writers_preserve_integrity(tmp_path):
    path = tmp_path / "theseus.sqlite3"
    store = DurableTheseusService(str(path), lane_count=16)

    def write(i: int):
        return store.store("tenant-a", f"payload-{i}".encode()).object_id

    with ThreadPoolExecutor(max_workers=8) as pool:
        object_ids = list(pool.map(write, range(64)))
    assert len(set(object_ids)) == 64

    reopened = DurableTheseusService(str(path), lane_count=16)
    assert len(reopened.query("tenant-a")) == 64
    reopened.verify_store()


def test_production_triad_transform_custody_materialise_restart(tmp_path):
    path = tmp_path / "triad.sqlite3"
    triad = ProductionTriad(str(path))
    receipt = triad.put("tenant-a", b"customer-payload-123")
    assert triad.verify(receipt) is True
    assert triad.materialise(receipt) == b"customer-payload-123"

    reopened = ProductionTriad(str(path))
    assert reopened.verify(receipt) is True
    assert reopened.materialise(receipt) == b"customer-payload-123"
    posture = reopened.production_posture()
    assert posture["chronus_role"] == "execution"
    assert posture["durable_custody"]["integrity"] == "PASS"
    assert posture["production_admission"] == "EVIDENCE_GATED"
