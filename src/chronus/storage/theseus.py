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
