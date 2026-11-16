"""Canonical production composition for Chronus, OVID and THESEUS."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from chronus.ovid.transform import OvidRepresentation, OvidTransformService
from chronus.storage.durable import DurableTheseusService


@dataclass(frozen=True)
class TriadReceipt:
    tenant_id: str
    representation_object_id: str
    receipt_object_id: str
    source_sha256: str
    representation_sha256: str
    contract_id: str
    contract_version: int

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "representation_object_id": self.representation_object_id,
            "receipt_object_id": self.receipt_object_id,
            "source_sha256": self.source_sha256,
            "representation_sha256": self.representation_sha256,
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
        }


class ProductionTriad:
    """Production-shaped triad: transform -> durable custody -> verified materialisation."""

    def __init__(self, state_path: str) -> None:
        if not state_path:
            raise ValueError("state_path is required for production triad custody")
        self.ovid = OvidTransformService()
        self.theseus = DurableTheseusService(state_path)

    def put(self, tenant_id: str, payload: bytes) -> TriadReceipt:
        representation = self.ovid.fold(payload)
        stored = self.theseus.store(tenant_id, representation.payload)
        envelope = {
            **representation.envelope(),
            "tenant_id": tenant_id,
            "representation_object_id": stored.object_id,
        }
        receipt_bytes = json.dumps(
            envelope, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        receipt_record = self.theseus.store(tenant_id, receipt_bytes)
        self.theseus.append_journal_event(
            tenant_id, "TRIAD_REPRESENTATION_COMMITTED", receipt_bytes
        )
        return TriadReceipt(
            tenant_id=tenant_id,
            representation_object_id=stored.object_id,
            receipt_object_id=receipt_record.object_id,
            source_sha256=representation.source_sha256,
            representation_sha256=representation.representation_sha256,
            contract_id=representation.contract_id,
            contract_version=representation.contract_version,
        )

    def materialise(self, receipt: TriadReceipt) -> bytes:
        receipt_bytes = self.theseus.reconstruct(
            receipt.tenant_id, receipt.receipt_object_id
        )
        envelope = json.loads(receipt_bytes.decode("utf-8"))
        if envelope["representation_object_id"] != receipt.representation_object_id:
            raise ValueError("triad receipt/object mismatch")
        if envelope["source_sha256"] != receipt.source_sha256:
            raise ValueError("triad source digest mismatch")
        encoded = self.theseus.reconstruct(
            receipt.tenant_id, receipt.representation_object_id
        )
        representation = OvidRepresentation(
            contract_id=envelope["contract_id"],
            contract_version=int(envelope["contract_version"]),
            source_sha256=envelope["source_sha256"],
            representation_sha256=envelope["representation_sha256"],
            original_length=int(envelope["original_length"]),
            payload=encoded,
        )
        return self.ovid.materialise(representation)

    def verify(self, receipt: TriadReceipt) -> bool:
        payload = self.materialise(receipt)
        if hashlib.sha256(payload).hexdigest() != receipt.source_sha256:
            return False
        return self.theseus.verify_journal_continuity(receipt.tenant_id)

    def production_posture(self) -> dict:
        evidence = self.theseus.evidence()
        return {
            "triad": "Chronus-OVID-THESEUS",
            "chronus_role": "execution",
            "ovid_role": "versioned representation transformation/materialisation",
            "theseus_role": "durable custody/integrity/continuity/recovery/provenance",
            "durable_custody": evidence,
            "ovid": self.ovid.manifest(),
            "production_admission": "EVIDENCE_GATED",
        }


def open_production_triad(root: str | Path, name: str = "triad") -> ProductionTriad:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    return ProductionTriad(str(root / f"{name}.sqlite3"))
