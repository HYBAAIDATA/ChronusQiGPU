"""Falsifiable phyllotaxis, prime indexing, and custody tests."""
import sqlite3

import pytest

from chronus.storage.durable import DurableTheseusService
from chronus.storage.phyllotaxis import fibonacci_cassini_witness
from chronus.storage.prime_product import (
    encode_labels, decode_labels, packed_address_bytes,
)
from chronus.storage.theseus import StorageIntegrityError


@pytest.mark.parametrize("n", [1, 2, 3, 8, 15, 64, 65, 100])
def test_cassini_identity(n):
    assert fibonacci_cassini_witness(n) == (-1 if n % 2 else 1)


@pytest.mark.parametrize("bad", [0, -1, True, 1.5])
def test_cassini_rejects_invalid_index(bad):
    with pytest.raises(ValueError):
        fibonacci_cassini_witness(bad)


def test_prime_product_unique_set_and_inverse():
    address = encode_labels([0, 4095, 127, 17])
    assert address == encode_labels([17, 127, 0, 4095])
    assert decode_labels(address) == (0, 17, 127, 4095)
    assert packed_address_bytes(address) > 0
    assert encode_labels([]) == 1
    assert decode_labels(1) == ()


@pytest.mark.parametrize("bad", [[0, 0], [4096], [-1], [True], list(range(33))])
def test_prime_product_rejects_invalid_input(bad):
    with pytest.raises(ValueError):
        encode_labels(bad)


def test_prime_product_rejects_bad_factors():
    with pytest.raises(ValueError):
        decode_labels(4)
    with pytest.raises(ValueError):
        decode_labels(65537)


def test_restart_rejects_tampered_phyllotaxis_angle(tmp_path):
    path = tmp_path / "angle.sqlite3"
    store = DurableTheseusService(str(path), lane_count=32)
    record = store.store("tenant", b"coordinate")
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE records SET golden_turns_numerator=? WHERE tenant_id=? AND object_id=?",
            (str(record.coordinate.golden_turns_numerator + 1), "tenant", record.object_id),
        )
    with pytest.raises(StorageIntegrityError, match="phyllotaxis"):
        DurableTheseusService(str(path), lane_count=32)


def test_restart_rejects_tampered_phyllotaxis_lane(tmp_path):
    path = tmp_path / "lane.sqlite3"
    store = DurableTheseusService(str(path), lane_count=32)
    record = store.store("tenant", b"coordinate")
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE records SET lane=? WHERE tenant_id=? AND object_id=?",
            ((record.coordinate.lane + 1) % 32, "tenant", record.object_id),
        )
    with pytest.raises(StorageIntegrityError, match="phyllotaxis"):
        DurableTheseusService(str(path), lane_count=32)


def test_restart_rejects_tampered_journal_coordinate(tmp_path):
    path = tmp_path / "journal.sqlite3"
    store = DurableTheseusService(str(path), lane_count=32)
    store.append_journal_event("tenant", "STATE_COMMITTED", b"journal")
    with sqlite3.connect(path) as db:
        db.execute("UPDATE journal SET golden_turns_denominator='17' WHERE tenant_id='tenant'")
    with pytest.raises(StorageIntegrityError, match="journal continuity"):
        DurableTheseusService(str(path), lane_count=32)


def test_healthy_durable_roundtrip(tmp_path):
    path = tmp_path / "healthy.sqlite3"
    store = DurableTheseusService(str(path), lane_count=32)
    record = store.store("tenant", b"exact-payload")
    store.append_journal_event("tenant", "STATE_COMMITTED", b"exact-payload")
    reopened = DurableTheseusService(str(path), lane_count=32)
    assert reopened.reconstruct("tenant", record.object_id) == b"exact-payload"
    assert reopened.verify_journal_continuity("tenant")

def test_restart_rejects_orphaned_foreign_key(tmp_path):
    path = tmp_path / "orphan.sqlite3"
    store = DurableTheseusService(str(path), lane_count=32)
    record = store.store("tenant", b"foreign-key")
    # Deliberately corrupt a DB with SQLite FK checks disabled on this connection.
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=OFF")
        db.execute("DELETE FROM objects WHERE object_id=?", (record.object_id,))
    with pytest.raises(StorageIntegrityError, match="foreign-key"):
        DurableTheseusService(str(path), lane_count=32)


def test_restart_rejects_record_size_corruption(tmp_path):
    path = tmp_path / "size.sqlite3"
    store = DurableTheseusService(str(path), lane_count=32)
    record = store.store("tenant", b"size-protected")
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE records SET size_bytes=size_bytes+1 WHERE tenant_id=? AND object_id=?",
            ("tenant", record.object_id),
        )
    with pytest.raises(StorageIntegrityError, match="size mismatch"):
        DurableTheseusService(str(path), lane_count=32)


def test_prime_address_bounds_fail_closed():
    with pytest.raises(ValueError, match="bit length"):
        decode_labels(1 << 513)
