"""Versioned OVID representation transforms.

OVID owns reversible working representations and materialisation. It does not
own durable custody; callers persist resulting representations through THESEUS.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from chronus.execution.structural import fold_pair, unfold_pair


@dataclass(frozen=True)
class TransformationContract:
    contract_id: str = "ovid.m15-byte-pairs/v1"
    version: int = 1
    reversible: bool = True


@dataclass(frozen=True)
class OvidRepresentation:
    contract_id: str
    contract_version: int
    source_sha256: str
    representation_sha256: str
    original_length: int
    payload: bytes

    def envelope(self) -> dict:
        return {
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "source_sha256": self.source_sha256,
            "representation_sha256": self.representation_sha256,
            "original_length": self.original_length,
        }


class OvidTransformService:
    """Apply and reverse the canonical byte-pair working representation."""

    def __init__(self, contract: TransformationContract | None = None) -> None:
        self.contract = contract or TransformationContract()

    def fold(self, payload: bytes) -> OvidRepresentation:
        if not isinstance(payload, bytes) or not payload:
            raise ValueError("payload must be non-empty bytes")
        padded = payload if len(payload) % 2 == 0 else payload + b"\x00"
        output = bytearray(len(padded))
        for offset in range(0, len(padded), 2):
            a, b = fold_pair(padded[offset], padded[offset + 1])
            output[offset] = a
            output[offset + 1] = b
        encoded = bytes(output)
        return OvidRepresentation(
            contract_id=self.contract.contract_id,
            contract_version=self.contract.version,
            source_sha256=hashlib.sha256(payload).hexdigest(),
            representation_sha256=hashlib.sha256(encoded).hexdigest(),
            original_length=len(payload),
            payload=encoded,
        )

    def materialise(self, representation: OvidRepresentation) -> bytes:
        if representation.contract_id != self.contract.contract_id:
            raise ValueError("unsupported OVID transformation contract")
        if representation.contract_version != self.contract.version:
            raise ValueError("unsupported OVID transformation version")
        if hashlib.sha256(representation.payload).hexdigest() != representation.representation_sha256:
            raise ValueError("OVID representation digest mismatch")
        if len(representation.payload) % 2:
            raise ValueError("OVID representation must contain complete byte pairs")
        output = bytearray(len(representation.payload))
        for offset in range(0, len(representation.payload), 2):
            a, b = unfold_pair(
                representation.payload[offset], representation.payload[offset + 1]
            )
            output[offset] = a
            output[offset + 1] = b
        materialised = bytes(output[: representation.original_length])
        if hashlib.sha256(materialised).hexdigest() != representation.source_sha256:
            raise ValueError("OVID materialisation digest mismatch")
        return materialised

    def manifest(self) -> dict:
        payload = {
            "authority": "OVID",
            "contract_id": self.contract.contract_id,
            "contract_version": self.contract.version,
            "reversible": self.contract.reversible,
            "durable_authority": False,
        }
        payload["contract_sha256"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return payload
