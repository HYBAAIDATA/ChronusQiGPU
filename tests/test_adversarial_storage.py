"""Adversarial and edge-case tests for storage integrity, journals, and bounds.

Attack-oriented cases: content corruption, hash-chain tampering, tenant
isolation abuse, boundary violations, and invalid input fuzzing.
"""

import hashlib

import pytest

from chronus.security.ovid import OVIDStorage
from chronus.storage.theseus import (
    StorageIntegrityError,
    TenantStorageFabricRegistry,
    TheseusService,
)


# ---------------------------------------------------------------------------
# OVID content-addressed store abuse
# ---------------------------------------------------------------------------


def test_ovid_rejects_non_bytes_payload():
    ovid = OVIDStorage()
    with pytest.raises(TypeError):
        ovid.store("not bytes")
    with pytest.raises(TypeError):
        ovid.store(12345)


def test_ovid_retrieve_unknown_object_returns_none():
    ovid = OVIDStorage()
    assert ovid.retrieve("0" * 64) is None


def test_ovid_retrieve_counts_accesses():
    ovid = OVIDStorage()
    ovid.store(b"data")
    ovid.retrieve("x")
    ovid.retrieve("y")
    stats = ovid.stats() if hasattr(ovid, "stats") else None
    # access counters exist on the storage object
    assert ovid._retrieve_count == 2


# ---------------------------------------------------------------------------
# Theseus integrity under corruption
# ---------------------------------------------------------------------------


def test_theseus_reconstruct_detects_corrupted_content():
    """If the backing store is tampered with, reconstruction must fail closed."""
    ovid = OVIDStorage()
    svc = TheseusService(ovid, lane_count=8)
    record = svc.store("tenant-a", b"original payload")
    # Adversary overwrites the content-addressed slot
    ovid._store[record.object_id] = b"attacker controlled bytes"
    with pytest.raises(StorageIntegrityError):
        svc.reconstruct("tenant-a", record.object_id)


def test_theseus_reconstruct_detects_deleted_content():
    ovid = OVIDStorage()
    svc = TheseusService(ovid, lane_count=8)
    record = svc.store("tenant-a", b"payload")
    del ovid._store[record.object_id]
    with pytest.raises(StorageIntegrityError):
        svc.reconstruct("tenant-a", record.object_id)


def test_theseus_store_validation_edges():
    svc = TheseusService(OVIDStorage(), lane_count=8)
    with pytest.raises(ValueError):
        svc.store("", b"payload")  # empty tenant
    with pytest.raises(ValueError):
        svc.store("tenant-a", b"")  # empty payload
    with pytest.raises(ValueError):
        svc.store("tenant-a", b"payload", scale_index=-1)
    with pytest.raises(ValueError):
        svc.store("tenant-a", b"payload", scale_index=True)
    with pytest.raises(ValueError):
        TheseusService(OVIDStorage(), lane_count=0)


def test_theseus_store_rejects_oversized_payload(monkeypatch):
    from chronus.storage import theseus as theseus_module

    real_bounds = theseus_module.runtime_bounds
    monkeypatch.setattr(
        theseus_module,
        "runtime_bounds",
        lambda: {**real_bounds(), "max_payload_bytes": 16},
    )
    svc = TheseusService(OVIDStorage(), lane_count=8)
    with pytest.raises(ValueError, match="payload"):
        svc.store("tenant-a", b"x" * 17)
    assert svc.store("tenant-a", b"x" * 16).size_bytes == 16


def test_theseus_stats_histogram_covers_all_records():
    svc = TheseusService(OVIDStorage(), lane_count=4)
    for i in range(10):
        svc.store("tenant-a", f"payload-{i}".encode())
    stats = svc.stats()
    assert stats["records"] == 10
    assert sum(stats["lane_histogram"]) == 10
    assert len(stats["lane_histogram"]) == 4
    assert all(count >= 0 for count in stats["lane_histogram"])


# ---------------------------------------------------------------------------
# THESEUS journal hash-chain tamper evidence
# ---------------------------------------------------------------------------


def _registry_with_events():
    registry = TenantStorageFabricRegistry()
    registry.initialize_tenant_fabric("tenant-a", b"genesis")
    registry.append_journal_event("tenant-a", "WORKLOAD_STORED", b"payload-1")
    registry.append_journal_event("tenant-a", "WORKLOAD_STORED", b"payload-2")
    return registry


def test_journal_continuity_valid_for_untouched_chain():
    registry = _registry_with_events()
    assert registry.verify_journal_continuity("tenant-a") is True


def test_journal_continuity_detects_entry_tampering():
    registry = _registry_with_events()
    journal = registry._journals["tenant-a"]
    forged = journal[1]
    object.__setattr__(forged, "event_type", "ADMIN_GRANTED")  # frozen bypass
    journal[1] = forged
    assert registry.verify_journal_continuity("tenant-a") is False


def test_journal_continuity_detects_chain_break():
    registry = _registry_with_events()
    journal = registry._journals["tenant-a"]
    # Remove the middle entry: subsequent prev hashes no longer line up
    del journal[1]
    assert registry.verify_journal_continuity("tenant-a") is False


def test_journal_continuity_detects_sequence_reorder():
    registry = _registry_with_events()
    journal = registry._journals["tenant-a"]
    journal[1], journal[2] = journal[2], journal[1]
    assert registry.verify_journal_continuity("tenant-a") is False


def test_journal_continuity_detects_content_corruption():
    registry = _registry_with_events()
    journal = registry._journals["tenant-a"]
    victim = journal[1]
    ovid, _ = registry._partitions["tenant-a"]
    ovid._store[victim.object_id] = b"forged content"
    with pytest.raises(StorageIntegrityError):
        registry.verify_journal_continuity("tenant-a")


def test_journal_continuity_unknown_tenant_is_false():
    registry = TenantStorageFabricRegistry()
    assert registry.verify_journal_continuity("ghost-tenant") is False


def test_tenant_fabrics_are_isolated():
    registry = TenantStorageFabricRegistry()
    registry.initialize_tenant_fabric("tenant-a", b"genesis-a")
    registry.initialize_tenant_fabric("tenant-b", b"genesis-b")
    assert registry.namespace_for("tenant-a") != registry.namespace_for("tenant-b")
    assert len(registry.get_journal("tenant-a")) == 1
    assert len(registry.get_journal("tenant-b")) == 1
    # Corrupting A must not break B
    ovid_a, _ = registry._partitions["tenant-a"]
    entry_a = registry.get_journal("tenant-a")[0]
    ovid_a._store[entry_a.object_id] = b"tampered"
    with pytest.raises(StorageIntegrityError):
        registry.verify_journal_continuity("tenant-a")
    assert registry.verify_journal_continuity("tenant-b") is True


def test_remove_tenant_fabric_clears_state():
    registry = _registry_with_events()
    registry.remove_tenant_fabric("tenant-a")
    assert registry.get_journal("tenant-a") == []
    assert registry.verify_journal_continuity("tenant-a") is False


def test_journal_entry_hash_matches_material():
    """The hash chain material must be exactly reproducible from entry fields."""
    registry = _registry_with_events()
    for entry in registry.get_journal("tenant-a"):
        material = (
            f"{entry.ovid_namespace}|{entry.sequence}|{entry.event_type}|"
            f"{entry.object_id}|{entry.prev_entry_hash}|{entry.timestamp_ns}"
        ).encode()
        assert hashlib.sha256(material).hexdigest() == entry.entry_hash
        assert entry.to_dict()["ovid_uri"].endswith(entry.object_id)
