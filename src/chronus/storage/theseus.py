"""Theseus reconstruction service over OVID content-addressed storage.

Stores caller payloads as content-addressed OVID objects, assigns each one a
phyllotaxis coordinate, and reconstructs them with digest verification. State
is process-local; it is not durable across restart.
"""

import hashlib
from dataclasses import dataclass

from chronus.config import runtime_bounds
from chronus.security.ovid import OVIDStorage
from chronus.storage.phyllotaxis import PhyllotaxisCoordinate, phyllotaxis_coordinate


class StorageIntegrityError(RuntimeError):
    """Retrieved content does not match its content address."""


@dataclass(frozen=True)
class TheseusRecord:
    object_id: str
    tenant_id: str
    size_bytes: int
    coordinate: PhyllotaxisCoordinate
    scale_index: int

    def to_dict(self) -> dict:
        return {
            "object_id": self.object_id,
            "tenant_id": self.tenant_id,
            "size_bytes": self.size_bytes,
            "coordinate": self.coordinate.to_dict(),
            "scale_index": self.scale_index,
        }


class TheseusService:
    """Store, query and reconstruct exact payloads with phyllotaxis addressing."""

    def __init__(self, ovid: OVIDStorage, lane_count: int | None = None) -> None:
        if lane_count is None:
            lane_count = runtime_bounds()["storage_lanes"]
        if not isinstance(lane_count, int) or isinstance(lane_count, bool) or lane_count < 1:
            raise ValueError("lane_count must be a positive integer")
        self.ovid = ovid
        self.lane_count = lane_count
        self._records: dict[tuple[str, str], TheseusRecord] = {}
        self._sequence = 0

    def store(
        self, tenant_id: str, payload: bytes, scale_index: int = 0
    ) -> TheseusRecord:
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a non-empty string")
        max_payload = runtime_bounds()["max_payload_bytes"]
        if not isinstance(payload, bytes) or not 1 <= len(payload) <= max_payload:
            raise ValueError(f"payload must be 1 to {max_payload} bytes")
        if not isinstance(scale_index, int) or isinstance(scale_index, bool) or scale_index < 0:
            raise ValueError("scale_index must be a non-negative integer")
        object_id = self.ovid.store(payload)
        key = (tenant_id, object_id)
        existing = self._records.get(key)
        if existing is not None:
            return existing
        coordinate = phyllotaxis_coordinate(
            self._sequence, bytes.fromhex(object_id), self.lane_count
        )
        self._sequence += 1
        record = TheseusRecord(
            object_id=object_id,
            tenant_id=tenant_id,
            size_bytes=len(payload),
            coordinate=coordinate,
            scale_index=scale_index,
        )
        self._records[key] = record
        return record

    def query(self, tenant_id: str) -> list[str]:
        """List object IDs stored by a tenant, in storage order."""
        return [
            object_id
            for (record_tenant, object_id) in self._records
            if record_tenant == tenant_id
        ]

    def scale_record(
        self, tenant_id: str, object_id: str, increment: int
    ) -> TheseusRecord:
        """Advance a record's PV scale lineage without touching its content.

        The content address is unchanged; the scale index advances by exact
        addition and the record receives a fresh phyllotaxis coordinate in
        the lineage.
        """
        record = self.get_record(tenant_id, object_id)
        from chronus.core.scaling import PVScale

        scale = PVScale(record.scale_index).advance(increment)
        coordinate = phyllotaxis_coordinate(
            self._sequence, bytes.fromhex(object_id), self.lane_count
        )
        self._sequence += 1
        scaled = TheseusRecord(
            object_id=object_id,
            tenant_id=tenant_id,
            size_bytes=record.size_bytes,
            coordinate=coordinate,
            scale_index=scale.index,
        )
        self._records[(tenant_id, object_id)] = scaled
        return scaled

    def stats(self) -> dict:
        histogram = [0] * self.lane_count
        for record in self._records.values():
            histogram[record.coordinate.lane] += 1
        return {
            "records": len(self._records),
            "lane_count": self.lane_count,
            "lane_histogram": histogram,
            "tenants": len({record.tenant_id for record in self._records.values()}),
            "durable": False,
        }

    def get_record(self, tenant_id: str, object_id: str) -> TheseusRecord:
        record = self._records.get((tenant_id, object_id))
        if record is None:
            raise KeyError(object_id)
        return record

    def reconstruct(self, tenant_id: str, object_id: str) -> bytes:
        """Retrieve a payload and prove its content matches its address."""
        self.get_record(tenant_id, object_id)
        payload = self.ovid.retrieve(object_id)
        if payload is None or hashlib.sha256(payload).hexdigest() != object_id:
            raise StorageIntegrityError(f"content for {object_id} failed digest verification")
        return payload


@dataclass(frozen=True)
class TenantStateJournalEntry:
    """Immutable hash-chained entry in a tenant's append-only THESEUS state journal."""

    sequence: int
    tenant_id: str
    ovid_namespace: str
    event_type: str
    object_id: str
    prev_entry_hash: str
    entry_hash: str
    timestamp_ns: int
    coordinate: PhyllotaxisCoordinate

    def to_dict(self) -> dict:
        return {
            "sequence": self.sequence,
            "tenant_id": self.tenant_id,
            "ovid_namespace": self.ovid_namespace,
            "event_type": self.event_type,
            "object_id": self.object_id,
            "ovid_uri": f"{self.ovid_namespace}/{self.object_id}",
            "prev_entry_hash": self.prev_entry_hash,
            "entry_hash": self.entry_hash,
            "timestamp_ns": self.timestamp_ns,
            "coordinate": self.coordinate.to_dict(),
        }


class TenantStorageFabricRegistry:
    """Manages tenant-isolated OVID partitions (o1_<tenant_id>) and append-only THESEUS journals."""

    def __init__(self) -> None:
        import threading

        self._lock = threading.RLock()
        self._partitions: dict[str, tuple[OVIDStorage, TheseusService]] = {}
        self._journals: dict[str, list[TenantStateJournalEntry]] = {}

    @staticmethod
    def namespace_for(tenant_id: str) -> str:
        return f"o1_{tenant_id}"

    def initialize_tenant_fabric(
        self, tenant_id: str, genesis_payload: bytes
    ) -> TenantStateJournalEntry:
        """Provision isolated o1_<tenant_id> OVID store and append genesis THESEUS journal entry."""
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a non-empty string")
        with self._lock:
            if tenant_id not in self._partitions:
                tenant_ovid = OVIDStorage()
                tenant_theseus = TheseusService(tenant_ovid)
                self._partitions[tenant_id] = (tenant_ovid, tenant_theseus)
                self._journals[tenant_id] = []
            return self.append_journal_event(
                tenant_id=tenant_id,
                event_type="GENESIS_MSA_PROVISIONED",
                payload=genesis_payload,
            )

    def append_journal_event(
        self, tenant_id: str, event_type: str, payload: bytes
    ) -> TenantStateJournalEntry:
        """Append an immutable state transition record to the tenant's THESEUS journal."""
        import time

        with self._lock:
            if tenant_id not in self._partitions:
                tenant_ovid = OVIDStorage()
                tenant_theseus = TheseusService(tenant_ovid)
                self._partitions[tenant_id] = (tenant_ovid, tenant_theseus)
                self._journals[tenant_id] = []

            _, tenant_theseus = self._partitions[tenant_id]
            journal = self._journals[tenant_id]
            record = tenant_theseus.store(tenant_id, payload)
            seq = len(journal)
            prev_hash = journal[-1].entry_hash if journal else ("0" * 64)
            ts_ns = time.time_ns()
            ovid_ns = self.namespace_for(tenant_id)
            chain_material = (
                f"{ovid_ns}|{seq}|{event_type}|{record.object_id}|{prev_hash}|{ts_ns}"
            ).encode("utf-8")
            entry_hash = hashlib.sha256(chain_material).hexdigest()

            entry = TenantStateJournalEntry(
                sequence=seq,
                tenant_id=tenant_id,
                ovid_namespace=ovid_ns,
                event_type=event_type,
                object_id=record.object_id,
                prev_entry_hash=prev_hash,
                entry_hash=entry_hash,
                timestamp_ns=ts_ns,
                coordinate=record.coordinate,
            )
            journal.append(entry)
            return entry

    def get_journal(self, tenant_id: str) -> list[TenantStateJournalEntry]:
        with self._lock:
            return list(self._journals.get(tenant_id, []))

    def verify_journal_continuity(self, tenant_id: str) -> bool:
        """Cryptographically verify hash-chain continuity and OVID content digests."""
        with self._lock:
            partition = self._partitions.get(tenant_id)
            journal = self._journals.get(tenant_id)
            if partition is None or journal is None:
                return False
            _, tenant_theseus = partition
            expected_prev = "0" * 64
            for idx, entry in enumerate(journal):
                if entry.sequence != idx or entry.prev_entry_hash != expected_prev:
                    return False
                # Reconstruct verifies SHA-256 content-address integrity
                tenant_theseus.reconstruct(tenant_id, entry.object_id)
                chain_material = (
                    f"{entry.ovid_namespace}|{entry.sequence}|{entry.event_type}|"
                    f"{entry.object_id}|{entry.prev_entry_hash}|{entry.timestamp_ns}"
                ).encode("utf-8")
                if hashlib.sha256(chain_material).hexdigest() != entry.entry_hash:
                    return False
                expected_prev = entry.entry_hash
            return True

    def remove_tenant_fabric(self, tenant_id: str) -> None:
        with self._lock:
            self._partitions.pop(tenant_id, None)
            self._journals.pop(tenant_id, None)


tenant_storage_registry = TenantStorageFabricRegistry()
