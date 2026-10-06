"""Production bindings from live subsystem surfaces to shared THESEUS/OVID data.

The repository has multiple subsystem-local journals and caches.  They remain
useful implementation details, but they are not permitted to become competing
durable truth stores.  This module is the canonical integration layer used by
production composition roots:

* PYTHIA memory/run evidence is mirrored into its shared data port;
* TOE hash-chained receipts are committed through the TOE port;
* TURING pipeline program/result/witness/report evidence is committed through
  the TURING port, with OVID parent lineage between those records;
* Salamander healing/optimisation calls emit their actual returned evidence;
* AL HARAS verdicts are bound to the security/governance port;
* EUCLID dispatch/evidence is committed while preserving the original owner;
* Kellogg tensor states can be admitted directly and are also participants in
  PYTHIA/TOE records.

Every adapter receives a :class:`SystemDataPort` created by one already-started
``aethel.enterprise.lifecycle.CompositionRoot``.  No adapter opens a private
THESEUS instance and no adapter constructs a substitute OVID.  Local subsystem
state may remain as a cache/journal, while cross-system durable identity and
lineage are held by the one shared fabric.

This data entanglement is a custody/lineage relationship.  It is deliberately
distinct from AL HARAS's F4 mathematical state-entanglement formalism.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .entangled_custody import CANONICAL_DATA_SYSTEMS, EntanglementBinding, SystemDataPort

# Shared relationships, not authority transfers.  Each producer remains the
# owner of its semantics; participants gain a governed view of the same record.
DEFAULT_PEERS: dict[str, tuple[str, ...]] = {
    "pythia": ("toe", "kellogg", "euclid", "salamander", "al_haras", "turing"),
    "toe": ("pythia", "kellogg", "euclid", "al_haras"),
    "kellogg": ("pythia", "toe", "turing", "euclid"),
    "turing": ("pythia", "euclid", "al_haras", "chronus"),
    "salamander": ("pythia", "euclid", "al_haras", "chronus"),
    "al_haras": ("euclid", "pythia", "salamander", "turing", "toe"),
    "euclid": ("pythia", "toe", "turing", "salamander", "al_haras", "chronus", "kellogg"),
    "chronus": ("turing", "euclid", "salamander", "pythia"),
}

if set(DEFAULT_PEERS) != set(CANONICAL_DATA_SYSTEMS):  # import-time architecture invariant
    raise RuntimeError("shared-system relationship map does not cover every canonical data system")


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return {"encoding": "hex", "value": value.hex()}
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _jsonable(dataclasses.asdict(value))
    for name in ("as_dict", "to_dict"):
        method = getattr(value, name, None)
        if callable(method):
            return _jsonable(method())
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return _jsonable(tolist())
    if hasattr(value, "re") and hasattr(value, "im"):
        return [float(value.re), float(value.im)]
    return repr(value)


def _latest_binding(
    port: SystemDataPort,
    *,
    source: str,
    kind: str,
) -> dict[str, Any] | None:
    bindings = [
        item
        for item in port.fabric.graph().get("bindings", ())
        if item.get("source_system") == source
        and item.get("kind") == kind
        and port.system in set(item.get("participants", ()))
    ]
    if not bindings:
        return None
    return max(bindings, key=lambda item: float(item.get("created_at", 0.0)))


class _BoundAdapter:
    def __init__(self, component: Any, port: SystemDataPort, *, system: str) -> None:
        if port.system != system:
            raise ValueError(f"{system} adapter requires the {system!r} data port")
        self.raw = component
        self.port = port
        self.system = system
        self.last_binding: EntanglementBinding | None = None

    @property
    def peers(self) -> tuple[str, ...]:
        return DEFAULT_PEERS[self.system]

    def _put(
        self,
        kind: str,
        payload: Any,
        *,
        parents: Sequence[str] = (),
        evidence_state: str = "MEASURED",
        share_with: Iterable[str] | None = None,
        meta: Mapping[str, Any] | None = None,
    ) -> EntanglementBinding:
        binding = self.port.put(
            kind,
            _jsonable(payload),
            share_with=self.peers if share_with is None else tuple(share_with),
            parents=tuple(parents),
            evidence_state=evidence_state,
            meta=dict(meta or {}),
        )
        self.last_binding = binding
        return binding

    def __getattr__(self, name: str) -> Any:
        return getattr(self.raw, name)


class SharedPythiaStore(_BoundAdapter):
    """PYTHIA store with local cache plus canonical shared durable snapshots."""

    SNAPSHOT_KIND = "pythia_memory_snapshot"

    def __init__(self, store: Any, port: SystemDataPort) -> None:
        super().__init__(store, port, system="pythia")

    def record_run(self, kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        entry = self.raw.record_run(kind, dict(payload))
        self._put(
            "pythia_run",
            entry,
            meta={"local_journal": str(getattr(self.raw.journal, "path", ""))},
        )
        return entry

    def save(self) -> Path:
        path = Path(self.raw.save())
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        parent = (self.last_binding.binding_id,) if self.last_binding is not None else ()
        self._put(
            self.SNAPSHOT_KIND,
            snapshot,
            parents=parent,
            meta={"local_cache_path": str(path), "canonical_durable_copy": True},
        )
        return path

    def load(self) -> bool:
        """Prefer the newest shared snapshot; local cache is fallback only."""
        latest = _latest_binding(self.port, source="pythia", kind=self.SNAPSHOT_KIND)
        if latest is None:
            return bool(self.raw.load())
        payload = json.loads(self.port.read(str(latest["binding_id"])).decode("utf-8"))
        self.raw.memory.load_snapshot(payload.get("memory", {}))
        self.raw.pythia.load_snapshot(payload.get("learning", {}))
        self.raw.qudits.load_snapshot(payload.get("qudits", {}))
        self.raw._since_save = 0
        return True

    def curate(self, emergence_signal: float | None = None) -> dict[str, Any]:
        report = self.raw.curate(emergence_signal)
        self._put("pythia_curation", report)
        # raw.curate() performs its own local save; commit that resulting state
        # to the shared fabric as the canonical durable copy too.
        self.save()
        return report


class SharedTOEBridge(_BoundAdapter):
    """TOE bridge whose native hash-chained receipts enter shared custody."""

    def __init__(self, bridge: Any, port: SystemDataPort) -> None:
        super().__init__(bridge, port, system="toe")
        self._receipt_cursor = 0

    def flush_receipts(self) -> tuple[EntanglementBinding, ...]:
        records = list(self.raw.receipts.records)
        written: list[EntanglementBinding] = []
        parent = (self.last_binding.binding_id,) if self.last_binding is not None else ()
        for receipt in records[self._receipt_cursor :]:
            binding = self._put(
                "toe_receipt",
                receipt,
                parents=parent,
                meta={"receipt_sha256": getattr(receipt, "receipt_sha256", "")},
            )
            parent = (binding.binding_id,)
            written.append(binding)
        self._receipt_cursor = len(records)
        return tuple(written)

    def __getattr__(self, name: str) -> Any:
        target = getattr(self.raw, name)
        if not callable(target) or name.startswith("_"):
            return target

        def _call(*args: Any, **kwargs: Any) -> Any:
            try:
                result = target(*args, **kwargs)
            except Exception as exc:
                self._put(
                    "toe_execution_failure",
                    {"method": name, "error": f"{type(exc).__name__}: {exc}"},
                    evidence_state="FAIL",
                )
                raise
            self.flush_receipts()
            return result

        return _call


class SharedSalamander(_BoundAdapter):
    """Salamander surface that retains measured healing/optimisation evidence."""

    def __init__(self, engine: Any, port: SystemDataPort) -> None:
        super().__init__(engine, port, system="salamander")

    def __getattr__(self, name: str) -> Any:
        target = getattr(self.raw, name)
        if not callable(target) or name.startswith("_"):
            return target

        def _call(*args: Any, **kwargs: Any) -> Any:
            try:
                result = target(*args, **kwargs)
            except Exception as exc:
                self._put(
                    "salamander_failure",
                    {"operation": name, "error": f"{type(exc).__name__}: {exc}"},
                    evidence_state="FAIL",
                )
                raise
            self._put(
                f"salamander_{name}",
                {"operation": name, "result": result},
            )
            return result

        return _call


class SharedALHaras(_BoundAdapter):
    """AL HARAS security boundary with shared custody for real verdicts."""

    def __init__(self, guardian: Any, port: SystemDataPort) -> None:
        super().__init__(guardian, port, system="al_haras")

    def __getattr__(self, name: str) -> Any:
        target = getattr(self.raw, name)
        if not callable(target) or name.startswith("_") or name not in {
            "evaluate", "preflight", "complete", "record_boundary_verdict"
        }:
            return target

        def _call(*args: Any, **kwargs: Any) -> Any:
            result = target(*args, **kwargs)
            self._put(
                f"al_haras_{name}",
                {"operation": name, "result": result},
                meta={"authority": "al_haras.security"},
            )
            return result

        return _call


class SharedKellogg(_BoundAdapter):
    """Kellogg exact/intelligence tensor entry point on the shared fabric."""

    def __init__(self, port: SystemDataPort) -> None:
        super().__init__(component=None, port=port, system="kellogg")

    def encode(self, data: Any, *, dim: int = 32) -> Any:
        from kellogg.quantum_tensor import encode_data_to_state

        state = encode_data_to_state(data, dim=dim)
        payload = {
            "dim": int(state.dim),
            "amplitudes": [[float(a.re), float(a.im)] for a in state.amplitudes],
        }
        self._put(
            "kellogg_tensor_state",
            payload,
            meta={"authority": "kellogg", "representation": "quantum_tensor"},
        )
        return state


class SharedTuring(_BoundAdapter):
    """Canonical TURING pipeline with shared, lineage-linked custody evidence.

    The wrapped VQC pipeline's legacy optional custody switch is suppressed on
    this path so it cannot open a second THESEUS instance.  The actual program,
    result, witness and final pipeline report are instead committed to the
    single shared data port with parent lineage.
    """

    def __init__(self, port: SystemDataPort, pipeline: Any | None = None) -> None:
        if pipeline is None:
            from turing_universal_quantum_computer.pipeline import VQCPipeline

            pipeline = VQCPipeline()
        super().__init__(pipeline, port, system="turing")
        self.last_bindings: dict[str, EntanglementBinding] = {}

    def run(self, request: Any) -> Any:
        # Canonical shared-data path owns durability/replay.  Avoid opening the
        # historical per-call Theseus adapter inside VQCPipeline._custody().
        if dataclasses.is_dataclass(request):
            fields = {field.name for field in dataclasses.fields(request)}
            updates = {}
            if "custody" in fields:
                updates["custody"] = False
            if "replay" in fields:
                updates["replay"] = False
            if updates:
                request = dataclasses.replace(request, **updates)

        report = self.raw.run(request)
        program_payload: dict[str, Any]
        program = getattr(request, "program", None)
        if program is not None and callable(getattr(program, "to_dict", None)):
            program_payload = program.to_dict()
        else:
            program_payload = {"qasm": getattr(request, "qasm", None)}
        program_binding = self._put(
            "turing_program",
            program_payload,
            meta={"program_digest": getattr(report, "program_digest", None)},
        )
        self.last_bindings["program"] = program_binding

        parents: tuple[str, ...] = (program_binding.binding_id,)
        if getattr(report, "result", None) is not None:
            result_binding = self._put("turing_result", report.result, parents=parents)
            self.last_bindings["result"] = result_binding
            parents = (program_binding.binding_id, result_binding.binding_id)
        if getattr(report, "witness", None) is not None:
            witness_binding = self._put("turing_witness", report.witness, parents=parents)
            self.last_bindings["witness"] = witness_binding
            parents = (*parents, witness_binding.binding_id)
        report_binding = self._put(
            "turing_pipeline_report",
            report,
            parents=parents,
            evidence_state="PASS" if getattr(report, "verdict", "") == "PASS" else "MEASURED",
            meta={"custody_mode": "shared_theseus_ovid_entanglement"},
        )
        self.last_bindings["report"] = report_binding
        return report


class SharedEuclid(_BoundAdapter):
    """EUCLID runtime proxy that persists its real evidence and owner handoffs."""

    def __init__(self, runtime: Any, port: SystemDataPort, *, salamander_port: SystemDataPort | None = None,
                 turing_port: SystemDataPort | None = None, chronus_port: SystemDataPort | None = None) -> None:
        super().__init__(runtime, port, system="euclid")
        self._evidence_cursor = len(getattr(runtime.evidence, "records", ()))
        self._salamander_port = salamander_port
        self._turing_port = turing_port
        self._chronus_port = chronus_port

    def flush_evidence(self) -> tuple[EntanglementBinding, ...]:
        records = list(getattr(self.raw.evidence, "records", ()))
        written: list[EntanglementBinding] = []
        for record in records[self._evidence_cursor :]:
            payload = _jsonable(record)
            destination = self.port
            kind = f"euclid_{getattr(record, 'kind', 'evidence')}"
            if str(getattr(record, "kind", "")).startswith("salamander") and self._salamander_port:
                destination = self._salamander_port
                kind = "salamander_control_evidence"
            binding = destination.put(
                kind,
                payload,
                share_with=DEFAULT_PEERS[destination.system],
                meta={"euclid_evidence_head": getattr(self.raw.evidence, "head", None)},
            )
            written.append(binding)
        self._evidence_cursor = len(records)
        return tuple(written)

    def __getattr__(self, name: str) -> Any:
        target = getattr(self.raw, name)
        if not callable(target) or name.startswith("_"):
            return target

        def _call(*args: Any, **kwargs: Any) -> Any:
            result = target(*args, **kwargs)
            self.flush_evidence()
            if isinstance(result, Mapping):
                organ = str(result.get("organ", "")).lower()
                if organ == "turing" and self._turing_port is not None:
                    self._turing_port.put(
                        "turing_euclid_handoff",
                        _jsonable(result),
                        share_with=DEFAULT_PEERS["turing"],
                    )
                elif organ == "chronus" and self._chronus_port is not None:
                    self._chronus_port.put(
                        "chronus_euclid_handoff",
                        _jsonable(result),
                        share_with=DEFAULT_PEERS["chronus"],
                    )
            return result

        return _call


class ProductionSystemRelations:
    """Bind live subsystem objects to one started enterprise CompositionRoot."""

    def __init__(self, lifecycle: Any) -> None:
        if not lifecycle.readiness().get("ready"):
            raise RuntimeError("shared THESEUS/OVID lifecycle must be started before system binding")
        self.lifecycle = lifecycle
        self.ports = {system: lifecycle.data_port(system) for system in sorted(CANONICAL_DATA_SYSTEMS)}

    def bind_intelligence(self, orchestrator: Any) -> Any:
        shared_store = SharedPythiaStore(orchestrator.store, self.ports["pythia"])
        # Shared state, when it exists, is authoritative over the local cache.
        shared_store.load()
        orchestrator.store = shared_store
        orchestrator.toe = SharedTOEBridge(orchestrator.toe, self.ports["toe"])
        orchestrator.salamander = SharedSalamander(orchestrator.salamander, self.ports["salamander"])
        return orchestrator

    def bind_al_haras(self, guardian: Any) -> SharedALHaras:
        return SharedALHaras(guardian, self.ports["al_haras"])

    def bind_euclid(self, runtime: Any) -> SharedEuclid:
        return SharedEuclid(
            runtime,
            self.ports["euclid"],
            salamander_port=self.ports["salamander"],
            turing_port=self.ports["turing"],
            chronus_port=self.ports["chronus"],
        )

    def turing(self, pipeline: Any | None = None) -> SharedTuring:
        return SharedTuring(self.ports["turing"], pipeline=pipeline)

    def kellogg(self) -> SharedKellogg:
        return SharedKellogg(self.ports["kellogg"])

    def status(self) -> dict[str, Any]:
        return {
            "schema": "aethel.production-system-relations/1",
            "ready": True,
            "systems": sorted(self.ports),
            "shared_custody": self.lifecycle.readiness().get("entangled_custody", {}),
            "authority_preserved": True,
        }


__all__ = [
    "DEFAULT_PEERS",
    "SharedPythiaStore",
    "SharedTOEBridge",
    "SharedSalamander",
    "SharedALHaras",
    "SharedKellogg",
    "SharedTuring",
    "SharedEuclid",
    "ProductionSystemRelations",
]
