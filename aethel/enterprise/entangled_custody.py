"""Shared THESEUS + OVID data fabric for the computational organism.

This module gives the repository's cross-system *data entanglement* a concrete,
machine-checkable contract:

* OVID owns the transformation and its parent lineage.
* THESEUS owns the one durable operational record.
* Consumer systems share that record identity; the fabric does not make a
  private copy per subsystem.
* A derived record binds to the OVID lineage of its parents, so the relation
  between systems is replayable provenance rather than a label.

This is deliberately distinct from the F4 state-entanglement mathematics in
``l_hras.foundations.entanglement``.  The latter measures state separability;
this module is the shared data/custody relationship between subsystem owners.
Neither is a claim about a physical communication channel.

MLA1517 is a version identifier in this repository.  This fabric does not make
it a product or subsystem name; market naming remains outside the code-level
authority graph.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

from aethel.ovid import Ovid

from .records import OperationalRecord
from .schema import OVID_TRANSFORM_V1

SCHEMA = "aethel.entangled-custody/1"
BINDING_SCHEMA = "aethel.entangled-custody.binding/1"

# Architectural identities.  ``tensor`` is retained only as the existing
# THESEUS producer-contract spelling for the Kellogg-owned tensor substrate.
CANONICAL_DATA_SYSTEMS = frozenset(
    {
        "pythia",
        "turing",
        "al_haras",
        "salamander",
        "euclid",
        "toe",
        "kellogg",
        "chronus",
    }
)

_PRODUCER_ALIAS = {"kellogg": "tensor"}


class EntangledCustodyError(RuntimeError):
    """Shared-custody contract could not be satisfied."""


class EntangledAccessError(PermissionError):
    """A system attempted to consume a binding it does not participate in."""


def _canonical_payload(payload: Any) -> bytes:
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, bytearray):
        return bytes(payload)
    if isinstance(payload, str):
        return payload.encode("utf-8")
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise TypeError("payload must be bytes, text, or JSON-serialisable") from exc


def _normalise_system(system: str) -> str:
    value = str(system).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "alharas": "al_haras",
        "al_haras": "al_haras",
        "salamander": "salamander",
        "pythia": "pythia",
        "turing": "turing",
        "euclid": "euclid",
        "toe": "toe",
        "kellogg": "kellogg",
        "tensor": "kellogg",
        "chronus": "chronus",
    }
    value = aliases.get(value, value)
    if value not in CANONICAL_DATA_SYSTEMS:
        raise EntangledCustodyError(f"unknown data-system identity: {system!r}")
    return value


def _producer(system: str) -> str:
    return _PRODUCER_ALIAS.get(system, system)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class EntanglementBinding:
    """One shared custody identity and the systems entangled through it."""

    binding_id: str
    source_system: str
    participants: tuple[str, ...]
    kind: str
    custody_record_id: str
    ovid_lineage_record_id: str
    ovid_lineage_id: str
    content_sha256: str
    parent_binding_ids: tuple[str, ...]
    created_at: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": BINDING_SCHEMA,
            "binding_id": self.binding_id,
            "source_system": self.source_system,
            "participants": list(self.participants),
            "kind": self.kind,
            "custody_record_id": self.custody_record_id,
            "ovid_lineage_record_id": self.ovid_lineage_record_id,
            "ovid_lineage_id": self.ovid_lineage_id,
            "content_sha256": self.content_sha256,
            "parent_binding_ids": list(self.parent_binding_ids),
            "created_at": self.created_at,
        }


class SystemDataPort:
    """A bounded view of the shared fabric for one subsystem owner."""

    def __init__(self, fabric: "EntangledCustodyFabric", system: str) -> None:
        self.fabric = fabric
        self.system = _normalise_system(system)

    def put(
        self,
        kind: str,
        payload: Any,
        *,
        share_with: Iterable[str] = (),
        evidence_state: str = "MEASURED",
        parents: Sequence[str] = (),
        correlation_ids: Mapping[str, str] | None = None,
        meta: Mapping[str, Any] | None = None,
    ) -> EntanglementBinding:
        return self.fabric.put(
            self.system,
            kind,
            payload,
            participants=(self.system, *tuple(share_with)),
            evidence_state=evidence_state,
            parents=parents,
            correlation_ids=correlation_ids,
            meta=meta,
        )

    def read(self, binding_id: str) -> bytes:
        return self.fabric.read(binding_id, consumer=self.system)

    def record(self, binding_id: str) -> OperationalRecord:
        return self.fabric.record(binding_id, consumer=self.system)

    def latest(self, kind: str) -> EntanglementBinding | None:
        """Return the newest verified binding of ``kind`` owned by this system."""
        name = str(kind).strip()
        if not name:
            raise ValueError("kind must be non-empty")
        candidates = [
            binding
            for binding in self.fabric._bindings.values()
            if binding.source_system == self.system
            and binding.kind == name
            and self.system in binding.participants
        ]
        if not candidates:
            return None
        latest = max(
            candidates,
            key=lambda binding: (binding.created_at, binding.binding_id),
        )
        verdict = self.fabric.verify(latest.binding_id)
        if not verdict.get("passed"):
            raise EntangledCustodyError(
                f"latest binding {latest.binding_id} failed custody verification"
            )
        return latest

    def sink(
        self,
        kind: str,
        *,
        share_with: Iterable[str] = (),
        evidence_state: str = "MEASURED",
    ) -> Callable[[Mapping[str, Any]], None]:
        participants = tuple(share_with)

        def _sink(payload: Mapping[str, Any]) -> None:
            self.put(
                kind,
                dict(payload),
                share_with=participants,
                evidence_state=evidence_state,
            )

        return _sink


class EntangledCustodyFabric:
    """One shared OVID-lineage / THESEUS-custody graph.

    ``custody`` must be one already-open ``EnterpriseCustody`` instance and
    must be shared by every port.  The fabric never opens a second store.
    """

    def __init__(self, custody: Any, *, ovid: Ovid | None = None) -> None:
        required = ("put_record", "get_record", "get")
        missing = [name for name in required if not callable(getattr(custody, name, None))]
        if missing:
            raise TypeError(f"custody is missing required THESEUS surface: {missing}")
        self.custody = custody
        self.ovid = ovid or Ovid()
        self._bindings: dict[str, EntanglementBinding] = {}
        self._sequence = 0
        self._lock = threading.RLock()

    def port(self, system: str) -> SystemDataPort:
        return SystemDataPort(self, system)

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
        """Transform once, custody once, share the resulting identity.

        ``parents`` are prior *binding ids*.  Their OVID lineage ids become the
        parent lineage of this transform; the THESEUS operational record also
        carries the parent custody record ids.  Both relationships are checked
        by :meth:`verify`.
        """
        source = _normalise_system(source_system)
        members = {_normalise_system(item) for item in participants}
        members.add(source)
        if not kind or not str(kind).strip():
            raise ValueError("kind must be non-empty")
        data = _canonical_payload(payload)

        with self._lock:
            parent_bindings: list[EntanglementBinding] = []
            for parent_id in parents:
                try:
                    parent_bindings.append(self._bindings[str(parent_id)])
                except KeyError as exc:
                    raise EntangledCustodyError(
                        f"unknown parent binding: {parent_id!r}"
                    ) from exc

            parent_lineages = tuple(p.ovid_lineage_id for p in parent_bindings)
            form = self.ovid.metamorphose(data, parents=parent_lineages)
            if form.lineage is None:
                raise EntangledCustodyError("OVID emitted no transform lineage")
            verdict = self.ovid.verify_equivalence(data, form)
            if not verdict.equivalent:
                raise EntangledCustodyError(
                    f"OVID equivalence failed before custody: {verdict.detail}"
                )

            binding_id = uuid.uuid4().hex
            lineage_record_id = f"ovid-lineage-{form.lineage.lineage_id}"
            record_id = f"entangled-{binding_id}"
            self._sequence += 1

            lineage_payload = json.dumps(
                form.lineage.to_dict(),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            lineage_record = OperationalRecord(
                record_id=lineage_record_id,
                producer="ovid",
                producer_version="entangled-custody/1",
                schema_version=1,
                kind="transform_lineage",
                payload=lineage_payload,
                evidence_state=form.lineage.evidence_state,
                sequence=self._sequence,
                lineage=tuple(p.ovid_lineage_record_id for p in parent_bindings),
                correlation_ids={"binding_id": binding_id},
                dependencies={"ovid_transform": OVID_TRANSFORM_V1},
                meta={
                    "schema": SCHEMA,
                    "source_system": source,
                    "participants": sorted(members),
                    "relation": "ovid-parent-lineage",
                },
            )
            self.custody.put_record(
                lineage_record,
                idempotency_key=f"entangled-lineage:{form.lineage.lineage_id}",
            )

            record_meta = dict(meta or {})
            record_meta.update(
                {
                    "schema": SCHEMA,
                    "binding_id": binding_id,
                    "source_system": source,
                    "participants": sorted(members),
                    "relation": "shared-theseus-record-via-ovid-lineage",
                    "ovid_lineage_id": form.lineage.lineage_id,
                    "ovid_output_digest": form.lineage.output_digest,
                    # The fabric observes this; caller metadata cannot override it.
                    "custody_writer_process_id": os.getpid(),
                }
            )
            correlations = {str(k): str(v) for k, v in dict(correlation_ids or {}).items()}
            correlations.update(
                {
                    "binding_id": binding_id,
                    "ovid_lineage_id": form.lineage.lineage_id,
                }
            )
            record = OperationalRecord(
                record_id=record_id,
                producer=_producer(source),
                producer_version="entangled-custody/1",
                schema_version=1,
                kind=str(kind),
                payload=data,
                evidence_state=evidence_state,
                sequence=self._sequence,
                lineage=(
                    lineage_record_id,
                    *(p.custody_record_id for p in parent_bindings),
                ),
                correlation_ids=correlations,
                dependencies={"ovid_transform": OVID_TRANSFORM_V1},
                meta=record_meta,
            )
            self.custody.put_record(record)

            binding = EntanglementBinding(
                binding_id=binding_id,
                source_system=source,
                participants=tuple(sorted(members)),
                kind=str(kind),
                custody_record_id=record_id,
                ovid_lineage_record_id=lineage_record_id,
                ovid_lineage_id=form.lineage.lineage_id,
                content_sha256=_digest(data),
                parent_binding_ids=tuple(str(p) for p in parents),
                created_at=time.time(),
            )
            self._bindings[binding_id] = binding
            return binding

    def _binding_for(self, binding_id: str, consumer: str) -> EntanglementBinding:
        system = _normalise_system(consumer)
        try:
            binding = self._bindings[str(binding_id)]
        except KeyError as exc:
            raise EntangledCustodyError(f"unknown binding: {binding_id!r}") from exc
        if system not in binding.participants:
            raise EntangledAccessError(
                f"{system} is not a participant in binding {binding.binding_id}"
            )
        return binding

    def record(self, binding_id: str, *, consumer: str) -> OperationalRecord:
        binding = self._binding_for(binding_id, consumer)
        return self.custody.get_record(binding.custody_record_id)

    def read(self, binding_id: str, *, consumer: str) -> bytes:
        return bytes(self.record(binding_id, consumer=consumer).payload)

    def verify(self, binding_id: str) -> dict[str, Any]:
        """Re-read both records and prove lineage/content/binding coherence."""
        try:
            binding = self._bindings[str(binding_id)]
        except KeyError as exc:
            raise EntangledCustodyError(f"unknown binding: {binding_id!r}") from exc
        record = self.custody.get_record(binding.custody_record_id)
        lineage_record = self.custody.get_record(binding.ovid_lineage_record_id)
        stored_lineage = json.loads(lineage_record.payload.decode("utf-8"))
        payload_ok = _digest(record.payload) == binding.content_sha256
        identity_ok = (
            record.meta.get("binding_id") == binding.binding_id
            and tuple(sorted(record.meta.get("participants", ()))) == binding.participants
            and record.meta.get("source_system") == binding.source_system
        )
        lineage_ok = (
            stored_lineage.get("lineage_id") == binding.ovid_lineage_id
            and record.meta.get("ovid_lineage_id") == binding.ovid_lineage_id
            and binding.ovid_lineage_record_id in tuple(record.lineage)
        )
        parents_ok = True
        for parent_id in binding.parent_binding_ids:
            parent = self._bindings.get(parent_id)
            if parent is None or parent.custody_record_id not in tuple(record.lineage):
                parents_ok = False
                break
            if parent.ovid_lineage_id not in tuple(stored_lineage.get("parent_ids", ())):
                parents_ok = False
                break
        passed = bool(payload_ok and identity_ok and lineage_ok and parents_ok)
        return {
            "schema": "aethel.entangled-custody.verify/1",
            "binding_id": binding.binding_id,
            "passed": passed,
            "payload_digest": payload_ok,
            "shared_identity": identity_ok,
            "ovid_lineage": lineage_ok,
            "parent_lineage": parents_ok,
            "participants": list(binding.participants),
            "custody_record_id": binding.custody_record_id,
            "ovid_lineage_record_id": binding.ovid_lineage_record_id,
        }

    def graph(self) -> dict[str, Any]:
        """Return the measured sharing graph; edges exist only from bindings."""
        edges: dict[tuple[str, str], list[str]] = {}
        for binding in self._bindings.values():
            for left, right in itertools.combinations(binding.participants, 2):
                edges.setdefault((left, right), []).append(binding.binding_id)
        return {
            "schema": "aethel.entangled-custody.graph/1",
            "systems": sorted({s for b in self._bindings.values() for s in b.participants}),
            "bindings": [b.as_dict() for b in self._bindings.values()],
            "edges": [
                {"left": left, "right": right, "binding_ids": tuple(ids)}
                for (left, right), ids in sorted(edges.items())
            ],
        }

    def status(self) -> dict[str, Any]:
        graph = self.graph()
        return {
            "schema": SCHEMA,
            "bindings": len(self._bindings),
            "systems": graph["systems"],
            "edges": len(graph["edges"]),
            "custody_root": str(getattr(self.custody, "root", "unknown")),
            "ovid_owner": getattr(self.ovid, "owner_id", "ovid"),
            "theseus_owner": "theseus",
        }


__all__ = [
    "SCHEMA",
    "BINDING_SCHEMA",
    "CANONICAL_DATA_SYSTEMS",
    "EntangledCustodyError",
    "EntangledAccessError",
    "EntanglementBinding",
    "SystemDataPort",
    "EntangledCustodyFabric",
]
