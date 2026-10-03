"""Custody envelope schema and canonicalization (format v1)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional

THESEUS_FORMAT_VERSION = 1
OVID_TRANSFORM_V1 = 1


@dataclass
class CustodyEvent:
    event_type: str
    record_id: str
    generation: int
    ts: float
    content_digest: str = ""
    note: str = ""
    tenant: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CustodyEvent":
        return cls(
            event_type=str(data["event_type"]),
            record_id=str(data["record_id"]),
            generation=int(data.get("generation", 0)),
            ts=float(data.get("ts", 0.0)),
            content_digest=str(data.get("content_digest", "")),
            note=str(data.get("note", "")),
            tenant=str(data.get("tenant", "")),
        )


@dataclass
class CustodyEnvelope:
    """On-disk custody record (Theseus format v1)."""

    record_id: str
    payload_b64: str
    content_digest: str
    generation: int = 1
    format_version: int = THESEUS_FORMAT_VERSION
    ovid_transform_version: int = OVID_TRANSFORM_V1
    tenant: str = "default"
    idempotency_key: str = ""
    mac: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "payload_b64": self.payload_b64,
            "content_digest": self.content_digest,
            "generation": self.generation,
            "format_version": self.format_version,
            "ovid_transform_version": self.ovid_transform_version,
            "tenant": self.tenant,
            "idempotency_key": self.idempotency_key,
            "mac": self.mac,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CustodyEnvelope":
        fmt = int(data.get("format_version", THESEUS_FORMAT_VERSION))
        if fmt != THESEUS_FORMAT_VERSION:
            from .errors import SchemaVersionError
            raise SchemaVersionError(f"unsupported format_version={fmt}")
        meta = data.get("meta") or {}
        if not isinstance(meta, dict):
            meta = dict(meta)
        return cls(
            record_id=str(data["record_id"]),
            payload_b64=str(data["payload_b64"]),
            content_digest=str(data["content_digest"]),
            generation=int(data.get("generation", 1)),
            format_version=fmt,
            ovid_transform_version=int(
                data.get("ovid_transform_version", OVID_TRANSFORM_V1)
            ),
            tenant=str(data.get("tenant", "default")),
            idempotency_key=str(data.get("idempotency_key", "")),
            mac=str(data.get("mac", "")),
            meta=meta,
        )


def canonical_manifest_bytes(envelope: CustodyEnvelope | Mapping[str, Any]) -> bytes:
    """Stable HMAC input: envelope without mac, sorted keys, compact JSON."""
    if isinstance(envelope, CustodyEnvelope):
        data = envelope.to_dict()
    else:
        data = dict(envelope)
    data = {k: v for k, v in data.items() if k != "mac"}
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode("utf-8")


__all__ = [
    "THESEUS_FORMAT_VERSION",
    "OVID_TRANSFORM_V1",
    "CustodyEvent",
    "CustodyEnvelope",
    "canonical_manifest_bytes",
]
