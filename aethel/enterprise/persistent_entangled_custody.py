"""Restart-persistent shared THESEUS/OVID entanglement fabric.

``EntangledCustodyFabric`` establishes one shared custody identity and OVID
lineage for a live process.  This production wrapper additionally stores the
binding graph itself as an OVID-authored operational record in the SAME
THESEUS custody root.  Reopening the composition root therefore reconstructs
which systems shared which record and which bindings were derived from which
parents; restart does not silently collapse the relationship into raw bytes.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Sequence

from .entangled_custody import (
    BINDING_SCHEMA,
    EntangledCustodyError,
    EntangledCustodyFabric,
    EntanglementBinding,
)
from .records import OperationalRecord
from .schema import OVID_TRANSFORM_V1

INDEX_KIND = "entanglement_binding"
INDEX_SCHEMA = "aethel.entangled-custody.binding-index/1"
_INDEX_PREFIX = "entangled-binding-"


class PersistentEntangledCustodyFabric(EntangledCustodyFabric):
    """Shared fabric whose relationship graph is itself in THESEUS custody."""

    def __init__(self, custody: Any, *, ovid: Any | None = None) -> None:
        super().__init__(custody, ovid=ovid)
        self._rehydrate()

    def _rehydrate(self) -> None:
        inventory = getattr(self.custody, "list_records", None)
        if not callable(inventory):
            raise TypeError("production entangled custody requires list_records()")
        recovered: dict[str, EntanglementBinding] = {}
        max_sequence = 0
        for item in inventory():
            if item.get("kind") != INDEX_KIND:
                continue
            record_id = str(item.get("record_id", ""))
            if not record_id.startswith(_INDEX_PREFIX):
                continue
            try:
                record = self.custody.get_record(record_id)
                payload = json.loads(record.payload.decode("utf-8"))
                if payload.get("schema") != BINDING_SCHEMA:
                    raise EntangledCustodyError(
                        f"binding index {record_id} has wrong schema"
                    )
                binding = EntanglementBinding(
                    binding_id=str(payload["binding_id"]),
                    source_system=str(payload["source_system"]),
                    participants=tuple(str(v) for v in payload["participants"]),
                    kind=str(payload["kind"]),
                    custody_record_id=str(payload["custody_record_id"]),
                    ovid_lineage_record_id=str(payload["ovid_lineage_record_id"]),
                    ovid_lineage_id=str(payload["ovid_lineage_id"]),
                    content_sha256=str(payload["content_sha256"]),
                    parent_binding_ids=tuple(
                        str(v) for v in payload.get("parent_binding_ids", ())
                    ),
                    created_at=float(payload["created_at"]),
                )
                # Fail closed on an index that points at a missing/corrupt
                # record.  Recovery must not advertise a relationship whose
                # underlying shared custody cannot be re-read.
                self.custody.get_record(binding.custody_record_id)
                self.custody.get_record(binding.ovid_lineage_record_id)
                recovered[binding.binding_id] = binding
                max_sequence = max(max_sequence, int(record.sequence))
            except Exception as exc:
                raise EntangledCustodyError(
                    f"failed to recover entanglement binding {record_id}: {exc}"
                ) from exc
        self._bindings = recovered
        self._sequence = max(self._sequence, max_sequence)

    def _persist_binding(self, binding: EntanglementBinding) -> None:
        payload = json.dumps(
            binding.as_dict(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self._sequence += 1
        parent_index_records = tuple(
            f"{_INDEX_PREFIX}{parent_id}" for parent_id in binding.parent_binding_ids
        )
        record = OperationalRecord(
            record_id=f"{_INDEX_PREFIX}{binding.binding_id}",
            producer="ovid",
            producer_version="entangled-custody/1",
            schema_version=1,
            kind=INDEX_KIND,
            payload=payload,
            evidence_state="PASS",
            sequence=self._sequence,
            lineage=(
                binding.ovid_lineage_record_id,
                binding.custody_record_id,
                *parent_index_records,
            ),
            correlation_ids={
                "binding_id": binding.binding_id,
                "ovid_lineage_id": binding.ovid_lineage_id,
                "custody_record_id": binding.custody_record_id,
            },
            dependencies={"ovid_transform": OVID_TRANSFORM_V1},
            meta={
                "schema": INDEX_SCHEMA,
                "relation": "durable-entanglement-binding-index",
                "source_system": binding.source_system,
                "participants": list(binding.participants),
            },
        )
        self.custody.put_record(
            record,
            idempotency_key=f"entangled-binding:{binding.binding_id}",
        )

    def put(
        self,
        source_system: str,
        kind: str,
        payload: Any,
        *,
        participants: Iterable[str] = (),
        evidence_state: str = "MEASURED",
        parents: Sequence[str] = (),
        correlation_ids: Mapping[str, str] | None = None,
        meta: Mapping[str, Any] | None = None,
    ) -> EntanglementBinding:
        binding = super().put(
            source_system,
            kind,
            payload,
            participants=participants,
            evidence_state=evidence_state,
            parents=parents,
            correlation_ids=correlation_ids,
            meta=meta,
        )
        self._persist_binding(binding)
        return binding

    def status(self) -> dict[str, Any]:
        status = super().status()
        status.update(
            {
                "schema": "aethel.entangled-custody.persistent/1",
                "binding_index": INDEX_SCHEMA,
                "restart_recoverable": True,
            }
        )
        return status


__all__ = [
    "INDEX_KIND",
    "INDEX_SCHEMA",
    "PersistentEntangledCustodyFabric",
]
