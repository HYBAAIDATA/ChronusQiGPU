"""Restart-persistent shared THESEUS/OVID entanglement fabric.

``EntangledCustodyFabric`` establishes one shared custody identity and OVID
lineage for a live process. This production wrapper additionally stores the
binding graph itself as an OVID-authored operational record in the SAME
THESEUS custody root. Reopening the composition root reconstructs which
systems shared which record and which bindings were derived from which parents.

Recovery is fail-closed: the binding index, referenced THESEUS record, OVID
lineage, participant identities, parent graph, and content digest are verified
before any consumer receives a data port.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .entangled_custody import (
    BINDING_SCHEMA,
    EntangledCustodyError,
    EntangledCustodyFabric,
    EntanglementBinding,
    _normalise_system,
    _producer,
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

    def _binding_index_ids(self) -> set[str]:
        """Discover every durable binding index, including corrupt envelopes.

        ``EnterpriseCustody.list_records()`` intentionally omits unrecoverable
        envelopes. For relationship recovery that would turn corruption into a
        silent disappearance, so index filenames are also enumerated from both
        custody sides and then individually verified through ``get_record``.
        """
        ids: set[str] = set()
        inventory = getattr(self.custody, "list_records", None)
        if not callable(inventory):
            raise TypeError("production entangled custody requires list_records()")
        for item in inventory():
            record_id = str(item.get("record_id", ""))
            if item.get("kind") == INDEX_KIND and record_id.startswith(_INDEX_PREFIX):
                ids.add(record_id)

        for attr in ("primary_dir", "replica_dir"):
            directory = getattr(self.custody, attr, None)
            if directory is None:
                continue
            base = Path(directory)
            if not base.is_dir():
                continue
            ids.update(
                path.stem
                for path in base.glob(f"{_INDEX_PREFIX}*.json")
                if path.is_file()
            )
        return ids

    @staticmethod
    def _normalise_binding(binding: EntanglementBinding) -> EntanglementBinding:
        source = _normalise_system(binding.source_system)
        participants = tuple(sorted({_normalise_system(v) for v in binding.participants}))
        if source not in participants:
            raise EntangledCustodyError(
                f"binding {binding.binding_id} omits source from participants"
            )
        return EntanglementBinding(
            binding_id=binding.binding_id,
            source_system=source,
            participants=participants,
            kind=binding.kind,
            custody_record_id=binding.custody_record_id,
            ovid_lineage_record_id=binding.ovid_lineage_record_id,
            ovid_lineage_id=binding.ovid_lineage_id,
            content_sha256=binding.content_sha256,
            parent_binding_ids=binding.parent_binding_ids,
            created_at=binding.created_at,
        )

    def _decode_index_record(self, record_id: str) -> tuple[OperationalRecord, EntanglementBinding]:
        record = self.custody.get_record(record_id)
        if record.kind != INDEX_KIND or record.producer != "ovid":
            raise EntangledCustodyError(
                f"binding index {record_id} has wrong producer/kind"
            )
        if record.meta.get("schema") != INDEX_SCHEMA:
            raise EntangledCustodyError(
                f"binding index {record_id} has wrong metadata schema"
            )
        payload = json.loads(record.payload.decode("utf-8"))
        if payload.get("schema") != BINDING_SCHEMA:
            raise EntangledCustodyError(f"binding index {record_id} has wrong schema")
        binding = self._normalise_binding(
            EntanglementBinding(
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
        )

        expected_record_id = f"{_INDEX_PREFIX}{binding.binding_id}"
        if record_id != expected_record_id or record.record_id != expected_record_id:
            raise EntangledCustodyError(
                f"binding index identity mismatch: {record_id} != {expected_record_id}"
            )
        expected_correlations = {
            "binding_id": binding.binding_id,
            "ovid_lineage_id": binding.ovid_lineage_id,
            "custody_record_id": binding.custody_record_id,
        }
        for key, expected in expected_correlations.items():
            if str(record.correlation_ids.get(key, "")) != expected:
                raise EntangledCustodyError(
                    f"binding index {record_id} correlation mismatch for {key}"
                )
        if record.meta.get("source_system") != binding.source_system:
            raise EntangledCustodyError(
                f"binding index {record_id} source identity mismatch"
            )
        if tuple(sorted(record.meta.get("participants", ()))) != binding.participants:
            raise EntangledCustodyError(
                f"binding index {record_id} participant identity mismatch"
            )

        expected_lineage = (
            binding.ovid_lineage_record_id,
            binding.custody_record_id,
            *(f"{_INDEX_PREFIX}{parent_id}" for parent_id in binding.parent_binding_ids),
        )
        if tuple(record.lineage) != expected_lineage:
            raise EntangledCustodyError(
                f"binding index {record_id} durable lineage mismatch"
            )

        # Re-read and bind the declared source/participant identity to the
        # durable producer records, not merely to self-consistent index fields.
        shared_record = self.custody.get_record(binding.custody_record_id)
        lineage_record = self.custody.get_record(binding.ovid_lineage_record_id)
        if shared_record.producer != _producer(binding.source_system):
            raise EntangledCustodyError(
                f"binding {binding.binding_id} producer/source identity mismatch"
            )
        if shared_record.kind != binding.kind:
            raise EntangledCustodyError(
                f"binding {binding.binding_id} shared-record kind mismatch"
            )
        if shared_record.meta.get("source_system") != binding.source_system:
            raise EntangledCustodyError(
                f"binding {binding.binding_id} shared-record source identity mismatch"
            )
        if tuple(sorted(shared_record.meta.get("participants", ()))) != binding.participants:
            raise EntangledCustodyError(
                f"binding {binding.binding_id} shared-record participant mismatch"
            )
        if str(shared_record.correlation_ids.get("binding_id", "")) != binding.binding_id:
            raise EntangledCustodyError(
                f"binding {binding.binding_id} shared-record binding correlation mismatch"
            )
        if str(shared_record.correlation_ids.get("ovid_lineage_id", "")) != binding.ovid_lineage_id:
            raise EntangledCustodyError(
                f"binding {binding.binding_id} shared-record OVID correlation mismatch"
            )
        if lineage_record.producer != "ovid" or lineage_record.kind != "transform_lineage":
            raise EntangledCustodyError(
                f"binding {binding.binding_id} OVID lineage producer/kind mismatch"
            )
        if lineage_record.meta.get("source_system") != binding.source_system:
            raise EntangledCustodyError(
                f"binding {binding.binding_id} OVID source identity mismatch"
            )
        if tuple(sorted(lineage_record.meta.get("participants", ()))) != binding.participants:
            raise EntangledCustodyError(
                f"binding {binding.binding_id} OVID participant identity mismatch"
            )
        if str(lineage_record.correlation_ids.get("binding_id", "")) != binding.binding_id:
            raise EntangledCustodyError(
                f"binding {binding.binding_id} OVID binding correlation mismatch"
            )
        return record, binding

    @staticmethod
    def _validate_parent_graph(bindings: Mapping[str, EntanglementBinding]) -> None:
        """Validate completeness/cycles without recursion-depth failure."""

        state: dict[str, int] = {}
        for root_id in sorted(bindings):
            if state.get(root_id) == 2:
                continue
            stack: list[tuple[str, bool]] = [(root_id, False)]
            while stack:
                binding_id, expanded = stack.pop()
                if expanded:
                    state[binding_id] = 2
                    continue
                current = state.get(binding_id, 0)
                if current == 2:
                    continue
                if current == 1:
                    raise EntangledCustodyError(
                        f"cycle in entanglement parent graph at {binding_id}"
                    )
                state[binding_id] = 1
                stack.append((binding_id, True))
                binding = bindings[binding_id]
                for parent_id in reversed(binding.parent_binding_ids):
                    if parent_id not in bindings:
                        raise EntangledCustodyError(
                            f"binding {binding_id} references missing parent {parent_id}"
                        )
                    parent_state = state.get(parent_id, 0)
                    if parent_state == 1:
                        raise EntangledCustodyError(
                            f"cycle in entanglement parent graph at {parent_id}"
                        )
                    if parent_state == 0:
                        stack.append((parent_id, False))

    def _verify_recovered_parent_lineage(self, binding: EntanglementBinding) -> None:
        """Require exact equality across all durable parent representations."""

        parents = tuple(self._bindings[parent_id] for parent_id in binding.parent_binding_ids)
        shared_record = self.custody.get_record(binding.custody_record_id)
        lineage_record = self.custody.get_record(binding.ovid_lineage_record_id)
        stored_lineage = json.loads(lineage_record.payload.decode("utf-8"))

        expected_shared_lineage = (
            binding.ovid_lineage_record_id,
            *(parent.custody_record_id for parent in parents),
        )
        if tuple(shared_record.lineage) != expected_shared_lineage:
            raise EntangledCustodyError(
                f"binding {binding.binding_id} parent custody lineage mismatch"
            )

        expected_lineage_records = tuple(parent.ovid_lineage_record_id for parent in parents)
        if tuple(lineage_record.lineage) != expected_lineage_records:
            raise EntangledCustodyError(
                f"binding {binding.binding_id} parent OVID record lineage mismatch"
            )

        expected_parent_ids = tuple(parent.ovid_lineage_id for parent in parents)
        if tuple(stored_lineage.get("parent_ids", ())) != expected_parent_ids:
            raise EntangledCustodyError(
                f"binding {binding.binding_id} parent OVID lineage-id mismatch"
            )

    def _rehydrate(self) -> None:
        recovered: dict[str, EntanglementBinding] = {}
        max_sequence = 0
        for record_id in sorted(self._binding_index_ids()):
            try:
                record, binding = self._decode_index_record(record_id)
                if binding.binding_id in recovered:
                    raise EntangledCustodyError(
                        f"duplicate binding identity {binding.binding_id}"
                    )
                recovered[binding.binding_id] = binding
                max_sequence = max(max_sequence, int(record.sequence))
            except Exception as exc:
                raise EntangledCustodyError(
                    f"failed to recover entanglement binding {record_id}: {exc}"
                ) from exc

        self._validate_parent_graph(recovered)
        self._bindings = recovered
        self._sequence = max(self._sequence, max_sequence)

        # Verify the complete graph only after every parent is loaded. Exact
        # parent-set equality prevents a validly authenticated index rewrite
        # from silently dropping provenance edges.
        for binding_id in sorted(self._bindings):
            binding = self._bindings[binding_id]
            self._verify_recovered_parent_lineage(binding)
            verdict = super().verify(binding_id)
            if not verdict.get("passed"):
                raise EntangledCustodyError(
                    f"binding {binding_id} failed structural verification: {verdict}"
                )

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
                "restart_integrity_verified": True,
            }
        )
        return status


__all__ = [
    "INDEX_KIND",
    "INDEX_SCHEMA",
    "PersistentEntangledCustodyFabric",
]
