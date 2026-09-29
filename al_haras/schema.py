"""Frozen logical 11-axis schema and distinct 64-byte transport ABI."""

from __future__ import annotations
from dataclasses import dataclass
import struct

CANONICAL_VERSION = 1
_HOT = struct.Struct("<Q14I")


@dataclass(frozen=True)
class MLAObjectV1:
    payload_type: str
    lucas_scale: int
    pisot_fold: str
    fibonacci_state: int
    zeckendorf_code: int
    binet_view: str
    prime_address: int
    polyhedral_location: int
    transform_state: str
    cassini_seal: int
    lineage_and_time: str
    object_id: str
    tenant: str
    instance: str
    residual: str | None = None
    version: int = CANONICAL_VERSION

    def validate(self):
        if self.version != CANONICAL_VERSION:
            raise ValueError("unknown schema version")
        if not all((self.object_id, self.tenant, self.instance, self.lineage_and_time)):
            raise ValueError("identity, tenant, instance and lineage required")


@dataclass(frozen=True)
class HotDescriptorV1:
    d1: int
    d2: int
    d3: int
    d4: int
    d5: int
    d6: int
    d7: int
    d8: int
    d9: int
    d10: int
    d11: int
    route: int
    reserved1: int = 0
    reserved2: int = 0
    reserved3: int = 0

    def pack(self) -> bytes:
        # D1 is 8 bytes; ten remaining axes, route, and three reserved
        # uint32 slots make the native transport descriptor exactly 64 bytes.
        if self.reserved1 or self.reserved2 or self.reserved3:
            raise ValueError("reserved transport fields must be zero")
        raw = _HOT.pack(
            self.d1,
            *[getattr(self, f"d{i}") & 0xFFFFFFFF for i in range(2, 12)],
            self.route,
            self.reserved1,
            self.reserved2,
            self.reserved3,
        )
        if len(raw) != 64:
            raise AssertionError("hot descriptor ABI drift")
        return raw


def reject_historical_schema(value: dict) -> None:
    if "d12_gauge" in value:
        raise ValueError("unsupported historical d12_gauge schema")
