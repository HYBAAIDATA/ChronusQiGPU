"""Production bindings from live subsystem surfaces to shared THESEUS/OVID data.

The repository has multiple subsystem-local journals and caches.  They remain
useful implementation details, but they are not permitted to become competing
durable truth stores.  This module is the canonical integration layer used by
production composition roots:

* PYTHIA memory/run evidence is mirrored into its shared data port;
* TOE hash-chained receipts are committed through the TOE port;
* TURING pipeline program/result/certificate/witness/report evidence is
  committed through the TURING port, with OVID parent lineage between those
  records, and the certificate/witness boundary is semantically validated
  before any of it enters custody;
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

from .entangled_custody import (
    CANONICAL_DATA_SYSTEMS,
    EntangledCustodyError,
    EntanglementBinding,
    SystemDataPort,
)

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
    """Canonical KELLOGG tensor boundary over the shared THESEUS/OVID fabric.

    KELLOGG remains the owner of tensor mathematics. This adapter adds only
    production evidence: an input commitment, a state artefact, a verified
    KELLOGG attestation, lineage-linked custody, and semantic replay.
    """

    def __init__(self, port: SystemDataPort) -> None:
        super().__init__(component=None, port=port, system="kellogg")
        self.last_bindings: dict[str, EntanglementBinding] = {}
        self.last_attestation: dict[str, Any] | None = None
        self.last_replay: dict[str, Any] | None = None

    def _commit_state(
        self,
        *,
        input_digest: str,
        state_payload: Mapping[str, Any],
        attestation: Mapping[str, Any],
    ) -> None:
        replay = verify_kellogg_custody_boundary(
            input_payload={
                "schema": "kellogg.input_commitment/v1",
                "input_digest": input_digest,
            },
            state_payload=state_payload,
            attestation_payload=attestation,
        )
        if not replay["passed"]:
            failed = sorted(name for name, passed in replay["checks"].items() if not passed)
            raise RuntimeError(
                "KELLOGG semantic pre-custody verification failed: " + ", ".join(failed)
            )

        input_binding = self._put(
            "kellogg_input_commitment",
            {
                "schema": "kellogg.input_commitment/v1",
                "input_digest": input_digest,
            },
            meta={"authority": "kellogg"},
        )
        state_binding = self._put(
            "kellogg_tensor_state",
            dict(state_payload),
            parents=(input_binding.binding_id,),
            meta={
                "authority": "kellogg",
                "representation": str(state_payload.get("representation", "unknown")),
                "plane": str(state_payload.get("plane", "unknown")),
            },
        )
        attestation_binding = self._put(
            "kellogg_attestation",
            dict(attestation),
            parents=(state_binding.binding_id,),
            meta={
                "authority": "kellogg",
                "attestation_schema": str(attestation.get("schema", "")),
                "attestation_digest": str(attestation.get("attestation_digest", "")),
            },
        )

        for name, binding in (
            ("input", input_binding),
            ("state", state_binding),
            ("attestation", attestation_binding),
        ):
            verdict = self.port.fabric.verify(binding.binding_id)
            if not verdict.get("passed"):
                raise RuntimeError(
                    f"KELLOGG shared custody verification failed for {name}: {verdict}"
                )

        self.last_bindings = {
            "input": input_binding,
            "state": state_binding,
            "attestation": attestation_binding,
        }
        self.last_attestation = dict(attestation)
        self.last_replay = replay

    def encode(self, data: Any, *, dim: int = 32) -> Any:
        """Encode through the declared finite-precision diagnostic plane."""
        from kellogg.attest import attest
        from kellogg.exact_tensor import canonical_digest
        from kellogg.quantum_tensor import encode_data_to_state

        state = encode_data_to_state(data, dim=dim)
        input_digest = canonical_digest(data)
        payload = {
            "schema": "kellogg.tensor_state/v1",
            "plane": "diagnostic",
            "exact": False,
            "representation": "quantum_tensor",
            "field": "IEEE-754 complex",
            "dim": int(state.dim),
            "input_digest": input_digest,
            "amplitudes": [[float(a.re), float(a.im)] for a in state.amplitudes],
        }
        attestation = attest(
            payload,
            float_boundaries=("kellogg.quantum_tensor.encode_data_to_state",),
            notes=("canonical production diagnostic-plane custody",),
        )
        self._commit_state(
            input_digest=input_digest,
            state_payload=payload,
            attestation=attestation,
        )
        return state

    def encode_exact(
        self,
        data: Any,
        *,
        num_qubits: int = 5,
        max_amplitudes: int | None = None,
    ) -> Any:
        """Encode to the exact F4 plane and custody the exact amplitudes."""
        from kellogg.attest import attest
        from kellogg.exact_tensor import ExactTOETensor

        tensor = ExactTOETensor(
            num_qubits=num_qubits,
            max_amplitudes=max_amplitudes,
        )
        state, input_digest = tensor.encode(data)
        payload = {
            "schema": "kellogg.exact_tensor_state/v1",
            "plane": "exact",
            "exact": True,
            "representation": "exact_tensor",
            "field": "Q(sqrt(2)) + iQ(sqrt(2))",
            "num_qubits": int(state.num_qubits),
            "amplitude_count": len(state.amplitudes),
            "input_digest": input_digest,
            "state_commitment": tensor.commitment(state),
            "normalized_exact": bool(state.normalized_exact()),
            "amplitudes": [amplitude.to_json() for amplitude in state.amplitudes],
        }
        attestation = attest(
            payload,
            notes=("canonical production exact-plane custody",),
        )
        self._commit_state(
            input_digest=input_digest,
            state_payload=payload,
            attestation=attestation,
        )
        return state

    def replay_latest(self) -> dict[str, Any]:
        """Recover and semantically replay the newest KELLOGG custody set."""
        attestation_binding = _latest_binding(
            self.port,
            source="kellogg",
            kind="kellogg_attestation",
        )
        if attestation_binding is None:
            raise RuntimeError("no KELLOGG attestation is available for replay")

        state_parents = tuple(attestation_binding.get("parent_binding_ids", ()))
        if len(state_parents) != 1:
            raise RuntimeError("KELLOGG attestation does not have exactly one state parent")
        state_binding_id = str(state_parents[0])
        graph = self.port.fabric.graph().get("bindings", ())
        state_binding = next(
            (
                item
                for item in graph
                if str(item.get("binding_id")) == state_binding_id
                and item.get("source_system") == "kellogg"
                and item.get("kind") == "kellogg_tensor_state"
            ),
            None,
        )
        if state_binding is None:
            raise RuntimeError("KELLOGG state parent is missing from shared custody")

        input_parents = tuple(state_binding.get("parent_binding_ids", ()))
        if len(input_parents) != 1:
            raise RuntimeError("KELLOGG state does not have exactly one input parent")
        input_binding_id = str(input_parents[0])

        input_payload = json.loads(self.port.read(input_binding_id).decode("utf-8"))
        state_payload = json.loads(self.port.read(state_binding_id).decode("utf-8"))
        attestation_payload = json.loads(
            self.port.read(str(attestation_binding["binding_id"])).decode("utf-8")
        )
        report = verify_kellogg_custody_boundary(
            input_payload=input_payload,
            state_payload=state_payload,
            attestation_payload=attestation_payload,
        )
        report["custody"] = {
            "input": bool(self.port.fabric.verify(input_binding_id).get("passed")),
            "state": bool(self.port.fabric.verify(state_binding_id).get("passed")),
            "attestation": bool(
                self.port.fabric.verify(str(attestation_binding["binding_id"])).get("passed")
            ),
        }
        report["passed"] = bool(report["passed"] and all(report["custody"].values()))
        self.last_replay = report
        return report


def verify_kellogg_custody_boundary(
    *,
    input_payload: Mapping[str, Any] | None,
    state_payload: Mapping[str, Any] | None,
    attestation_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Semantically verify one recovered KELLOGG state/attestation custody set."""
    import math

    from kellogg.attest import verify_attestation
    from kellogg.exact_tensor import ExactStateVector, ExactTOETensor, F4

    checks: dict[str, bool] = {}
    input_record = input_payload if isinstance(input_payload, Mapping) else {}
    state_record = state_payload if isinstance(state_payload, Mapping) else {}
    attestation_record = (
        attestation_payload if isinstance(attestation_payload, Mapping) else {}
    )

    checks["input_schema"] = (
        input_record.get("schema") == "kellogg.input_commitment/v1"
    )
    input_digest = input_record.get("input_digest")
    checks["input_digest_present"] = bool(
        isinstance(input_digest, str) and len(input_digest) == 64
    )
    checks["state_binds_input"] = bool(
        checks["input_digest_present"]
        and state_record.get("input_digest") == input_digest
    )

    try:
        checks["attestation_verifies"] = bool(
            verify_attestation(state_record, attestation_record)
        )
    except Exception:
        checks["attestation_verifies"] = False

    plane = state_record.get("plane")
    checks["plane_declared"] = plane in {"exact", "diagnostic"}
    checks["exact_flag_matches_plane"] = (
        state_record.get("exact") is (plane == "exact")
    )

    if plane == "exact":
        checks["state_schema"] = (
            state_record.get("schema") == "kellogg.exact_tensor_state/v1"
        )
        checks["representation"] = state_record.get("representation") == "exact_tensor"
        checks["field"] = (
            state_record.get("field") == "Q(sqrt(2)) + iQ(sqrt(2))"
        )
        amplitudes = state_record.get("amplitudes")
        try:
            parsed = tuple(F4.from_json(value) for value in amplitudes)
            num_qubits = int(state_record.get("num_qubits"))
            exact_state = ExactStateVector(
                num_qubits,
                parsed,
                max_amplitudes=len(parsed),
            )
            checks["exact_amplitudes_reconstruct"] = True
            checks["amplitude_count"] = (
                int(state_record.get("amplitude_count")) == len(parsed)
            )
            checks["normalization"] = bool(
                state_record.get("normalized_exact") is True
                and exact_state.normalized_exact()
            )
            checks["state_commitment"] = (
                state_record.get("state_commitment")
                == ExactTOETensor.commitment(exact_state)
            )
        except Exception:
            checks["exact_amplitudes_reconstruct"] = False
            checks["amplitude_count"] = False
            checks["normalization"] = False
            checks["state_commitment"] = False
        boundary = attestation_record.get("boundary")
        checks["no_float_boundary_on_exact_plane"] = bool(
            isinstance(boundary, Mapping)
            and boundary.get("float_boundaries") == []
        )
    elif plane == "diagnostic":
        checks["state_schema"] = (
            state_record.get("schema") == "kellogg.tensor_state/v1"
        )
        checks["representation"] = (
            state_record.get("representation") == "quantum_tensor"
        )
        checks["field"] = state_record.get("field") == "IEEE-754 complex"
        amplitudes = state_record.get("amplitudes")
        try:
            dim = int(state_record.get("dim"))
            pairs = list(amplitudes)
            finite = all(
                isinstance(pair, list)
                and len(pair) == 2
                and all(math.isfinite(float(value)) for value in pair)
                for pair in pairs
            )
            checks["diagnostic_amplitudes_reconstruct"] = bool(
                finite and dim == len(pairs)
            )
            norm_sq = sum(
                float(pair[0]) * float(pair[0])
                + float(pair[1]) * float(pair[1])
                for pair in pairs
            )
            checks["normalization"] = bool(
                checks["diagnostic_amplitudes_reconstruct"]
                and abs(norm_sq - 1.0) <= 1e-12
            )
        except Exception:
            checks["diagnostic_amplitudes_reconstruct"] = False
            checks["normalization"] = False
        boundary = attestation_record.get("boundary")
        checks["float_boundary_declared"] = bool(
            isinstance(boundary, Mapping)
            and boundary.get("float_boundaries")
            and all(
                isinstance(item, str)
                for item in boundary.get("float_boundaries", ())
            )
        )
    else:
        checks["state_schema"] = False
        checks["representation"] = False
        checks["field"] = False
        checks["normalization"] = False

    return {
        "schema": "aethel.kellogg-custody-replay/1",
        "passed": all(checks.values()),
        "checks": checks,
        "plane": plane,
        "input_digest": input_digest,
        "attestation_digest": attestation_record.get("attestation_digest"),
    }


def verify_turing_custody_boundary(
    *,
    program_payload: Mapping[str, Any] | None,
    result_payload: Mapping[str, Any] | None,
    certificate_payload: Mapping[str, Any] | None,
    witness_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Semantic replay of one recovered TURING certificate custody set.

    Raw THESEUS/OVID integrity proves bytes survived; it does not prove the
    recovered program, result, certificate and witness describe *one*
    execution.  This replay parses each artefact, re-runs
    ``verify_integrity``/``verify_witness``, and cross-binds their identities,
    so an individually-valid but foreign certificate or witness fails here
    instead of replaying as PASS.

    Returns ``{"schema": ..., "passed": bool, "checks": {name: bool}}``.
    """
    from turing_universal_quantum_computer.backends.base import (
        ExecutionClass,
        ExecutionResult,
        Program,
        TruthClass,
    )
    from turing_universal_quantum_computer.certificates import (
        RunWitness,
        VQCComputationCertificate,
        verify_serialized_computation_certificate,
        verify_witness,
    )

    checks: dict[str, bool] = {}

    certificate: Any | None = None
    try:
        certificate = VQCComputationCertificate.from_dict(dict(certificate_payload or {}))
        checks["certificate_parses"] = True
    except Exception:
        checks["certificate_parses"] = False
    try:
        checks["certificate_integrity"] = bool(
            certificate is not None and certificate.verify_integrity()
        )
    except Exception:
        checks["certificate_integrity"] = False

    witness: Any | None = None
    try:
        witness = RunWitness.from_dict(dict(witness_payload or {}))
        checks["witness_parses"] = True
    except Exception:
        checks["witness_parses"] = False
    try:
        checks["witness_verification"] = bool(
            witness is not None and verify_witness(witness)
        )
    except Exception:
        checks["witness_verification"] = False

    # The certificate's first trace frame is the certified canonical program.
    certified_program: dict[str, Any] | None = None
    if certificate is not None and certificate.trace:
        head = certificate.trace[0]
        if isinstance(head, Mapping) and head.get("kind") == "input":
            candidate = head.get("program")
            if isinstance(candidate, Mapping):
                certified_program = dict(candidate)
    checks["certificate_has_program_trace"] = certified_program is not None

    program = None
    if isinstance(program_payload, Mapping):
        try:
            if {"n_qubits", "operations"} <= set(program_payload):
                program = Program.from_dict(dict(program_payload))
            elif "qasm" in program_payload:
                from turing_universal_quantum_computer.phi_machine import (
                    PhiQuantumCircuit,
                )

                circuit = PhiQuantumCircuit.from_qasm(str(program_payload["qasm"]))
                program = Program(n_qubits=circuit.num_qubits)
                for gate in circuit.gates:
                    program = program.then(gate.name, *gate.qubits)
        except Exception:
            program = None
    checks["program_record_reconstructs"] = program is not None
    checks["program_matches_certificate_trace"] = bool(
        program is not None
        and certified_program is not None
        and program.to_dict() == certified_program
    )
    checks["program_digest_matches_witness"] = bool(
        program is not None
        and witness is not None
        and program.digest() == witness.program_digest
    )

    result = result_payload if isinstance(result_payload, Mapping) else None
    if result is not None:
        try:
            embedded_certificate = result.get("certificate")
            if embedded_certificate is not None and not isinstance(
                embedded_certificate, Mapping
            ):
                raise TypeError("embedded certificate must be a mapping")
            backend_payload = result.get("payload", {})
            if not isinstance(backend_payload, Mapping):
                raise TypeError("backend payload must be a mapping")
            ExecutionResult(
                backend=str(result["backend"]),
                execution_class=ExecutionClass(str(result["execution_class"])),
                truth_class=TruthClass(str(result["truth_class"])),
                n_qubits=int(result["n_qubits"]),
                program_digest=str(result["program_digest"]),
                materialised=bool(result["materialised"]),
                payload=dict(backend_payload),
                refusals=tuple(str(item) for item in result.get("refusals", ())),
                measured_qpu=bool(result.get("measured_qpu", False)),
                certificate=(
                    dict(embedded_certificate)
                    if isinstance(embedded_certificate, Mapping)
                    else None
                ),
            )
            checks["result_reconstructs"] = True
        except Exception:
            checks["result_reconstructs"] = False
    else:
        checks["result_reconstructs"] = False

    checks["certificate_options_recovered"] = bool(
        certificate is not None
        and certificate.trace
        and isinstance(certificate.trace[0], Mapping)
        and isinstance(certificate.trace[0].get("options", {}), Mapping)
    )

    checks["certificate_binds_witness"] = bool(
        certificate is not None
        and witness is not None
        and witness.computation_certificate_digest is not None
        and witness.computation_certificate_digest == certificate.certificate_digest
    )
    checks["certificate_matches_result_identity"] = bool(
        certificate is not None
        and result is not None
        and certificate.backend == result.get("backend")
        and certificate.execution_class == result.get("execution_class")
        and certificate.truth_class == result.get("truth_class")
    )
    checks["result_embeds_certificate"] = bool(
        certificate is not None
        and result is not None
        and result.get("certificate") == certificate.to_dict()
    )

    certified_options: dict[str, Any] = {}
    if certificate is not None and certificate.trace:
        first = certificate.trace[0]
        if isinstance(first, Mapping):
            raw_options = first.get("options", {})
            if isinstance(raw_options, Mapping):
                certified_options = dict(raw_options)
    try:
        checks["certificate_binds_program_and_result"] = bool(
            program is not None
            and result is not None
            and certificate is not None
            and verify_serialized_computation_certificate(
                program,
                result,
                certificate,
                options=certified_options,
            )
        )
    except Exception:
        checks["certificate_binds_program_and_result"] = False

    checks["witness_binds_result"] = bool(
        witness is not None
        and result is not None
        and program is not None
        and witness.backend == result.get("backend")
        and witness.execution_class == result.get("execution_class")
        and witness.truth_class == result.get("truth_class")
        and witness.n_qubits == result.get("n_qubits")
        and witness.program_digest == result.get("program_digest")
        and witness.materialised == bool(result.get("materialised"))
        and witness.measured_qpu == bool(result.get("measured_qpu", False))
        and program is not None
        and witness.gate_counts == program.gate_counts()
    )
    checks["witness_provider_job_matches_result"] = bool(
        witness is not None
        and result is not None
        and (
            not witness.measured_qpu
            or witness.provider_job_id
            == str((result.get("payload") or {}).get("job_id", ""))
        )
    )

    return {
        "schema": "aethel.turing-custody-boundary.verify/1",
        "passed": all(checks.values()),
        "checks": checks,
    }


class SharedTuring(_BoundAdapter):
    """Canonical TURING pipeline with shared, lineage-linked custody evidence.

    The wrapped VQC pipeline's legacy optional custody switch is suppressed on
    this path so it cannot open a second THESEUS instance.  The program,
    result, computation certificate, witness and final pipeline report are
    instead committed to the single shared data port with parent lineage

        program -> result -> certificate -> witness -> pipeline_report -> replay

    The certificate/witness boundary is semantically validated before custody,
    then the committed artefacts are read back and revalidated before a
    successful execution is returned as production-accepted.
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

        certificate_payload = getattr(report, "certificate", None)
        witness_payload = getattr(report, "witness", None)
        if certificate_payload is not None or witness_payload is not None:
            # The certified boundary is validated before ANY artefact enters
            # shared custody: individually-valid but mutually inconsistent
            # certificate/witness records must never be custodied as if they
            # were one execution.
            boundary = verify_turing_custody_boundary(
                program_payload=program_payload,
                result_payload=getattr(report, "result", None),
                certificate_payload=certificate_payload,
                witness_payload=witness_payload,
            )
            if not boundary["passed"]:
                failed = sorted(
                    name for name, ok in boundary["checks"].items() if not ok
                )
                raise EntangledCustodyError(
                    "TURING certificate custody boundary is inconsistent "
                    f"({', '.join(failed)}); refusing to custody it"
                )

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
        if certificate_payload is not None:
            certificate_binding = self._put(
                "turing_certificate",
                certificate_payload,
                parents=parents,
                evidence_state="PASS",
            )
            self.last_bindings["certificate"] = certificate_binding
            parents = (*parents, certificate_binding.binding_id)
        if witness_payload is not None:
            witness_binding = self._put("turing_witness", witness_payload, parents=parents)
            self.last_bindings["witness"] = witness_binding
            parents = (*parents, witness_binding.binding_id)
        report_binding = self._put(
            "turing_pipeline_report",
            report,
            parents=parents,
            evidence_state=(
                "PASS" if getattr(report, "verdict", "") == "PASS" else "MEASURED"
            ),
            meta={"custody_mode": "shared_theseus_ovid_entanglement"},
        )
        self.last_bindings["report"] = report_binding

        # A successful computation is not a production-accepted voyage until
        # the artefacts that actually entered the shared durable fabric are
        # read back and semantically cross-bound.  Refused/failed computations
        # remain valid evidence records but have no completed result bundle to
        # replay.
        if (
            getattr(report, "result", None) is not None
            and certificate_payload is not None
            and witness_payload is not None
        ):
            replay = self.replay()
            replay_binding = self._put(
                "turing_replay",
                replay,
                parents=(report_binding.binding_id,),
                evidence_state="PASS" if replay["passed"] else "FAIL",
                meta={"production_gate": "post_custody_semantic_replay"},
            )
            self.last_bindings["replay"] = replay_binding
            if not replay["passed"]:
                failed = sorted(
                    name for name, ok in replay["checks"].items() if not ok
                )
                raise EntangledCustodyError(
                    "TURING shared-custody replay failed after commit "
                    f"({', '.join(failed)}); refusing production acceptance"
                )
        return report

    def replay(self) -> dict[str, Any]:
        """Re-read this run's artefacts from shared custody and prove the
        certificate boundary semantically, not just at byte level.

        Same-process replays resolve through ``last_bindings``.  After a
        restart the in-memory map is empty, so the newest
        ``turing_pipeline_report`` is resolved from the durable binding
        graph and its OVID parent lineage walked back to program, result,
        certificate and witness — the binding identity that THESEUS itself
        recovered.
        """
        records: dict[str, Any] = {}
        replay_source = "last_bindings"
        report_binding_id: str | None = None
        if {"program", "result", "certificate", "witness"} <= set(self.last_bindings):
            for name in ("program", "result", "certificate", "witness"):
                records[name] = json.loads(
                    self.port.read(self.last_bindings[name].binding_id).decode("utf-8")
                )
            report = self.last_bindings.get("report")
            report_binding_id = report.binding_id if report is not None else None
        else:
            replay_source = "durable_graph"
            latest = _latest_binding(
                self.port, source="turing", kind="turing_pipeline_report"
            )
            if latest is not None:
                report_binding_id = str(latest["binding_id"])
                by_id = {
                    item["binding_id"]: item
                    for item in self.port.fabric.graph().get("bindings", ())
                }
                for parent_id in latest.get("parent_binding_ids", ()):
                    parent = by_id.get(parent_id)
                    if parent is None:
                        continue
                    kind = str(parent.get("kind", ""))
                    if kind.startswith("turing_"):
                        records[kind[len("turing_"):]] = json.loads(
                            self.port.read(str(parent_id)).decode("utf-8")
                        )
        boundary = verify_turing_custody_boundary(
            program_payload=records.get("program"),
            result_payload=records.get("result"),
            certificate_payload=records.get("certificate"),
            witness_payload=records.get("witness"),
        )
        boundary["replay_source"] = replay_source
        boundary["report_binding_id"] = report_binding_id
        boundary["record_kinds"] = sorted(records)
        return boundary


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



def verify_chronus_custody_boundary(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Semantically verify a recovered Chronus startup-voyage record."""
    try:
        from chronus.production import verify_startup_report

        if not isinstance(payload, Mapping):
            raise TypeError("Chronus startup payload must be a mapping")
        return verify_startup_report(dict(payload))
    except Exception as exc:
        return {
            "schema": "aethel.chronus-custody-boundary.verify/1",
            "passed": False,
            "checks": {"payload_verifies": False},
            "error": f"{type(exc).__name__}: {exc}",
        }


class SharedChronus(_BoundAdapter):
    """Canonical Chronus runtime bound to shared THESEUS/OVID custody."""

    VOYAGE_KIND = "chronus_startup_voyage"
    REPLAY_KIND = "chronus_startup_replay"

    def __init__(self, runtime: Any, port: SystemDataPort) -> None:
        super().__init__(runtime, port, system="chronus")
        self.last_bindings: dict[str, EntanglementBinding] = {}

    def run_startup_voyage(self) -> dict[str, Any]:
        report = self.raw.startup_voyage()
        boundary = verify_chronus_custody_boundary(report)
        if not boundary.get("passed"):
            raise RuntimeError(
                f"Chronus startup report failed semantic verification: {boundary}"
            )

        voyage = self._put(
            self.VOYAGE_KIND,
            report,
            evidence_state="MEASURED",
            meta={
                "execution_owner": "chronus",
                "custody_owner": "theseus",
                "transform_lineage_owner": "ovid",
                "physical_gpu_required": bool(report.get("physical_gpu_required")),
            },
        )
        custody = self.port.fabric.verify(voyage.binding_id)
        if not custody.get("passed"):
            raise RuntimeError("Chronus startup voyage failed shared custody verification")

        recovered = json.loads(self.port.read(voyage.binding_id).decode("utf-8"))
        replay = verify_chronus_custody_boundary(recovered)
        replay["custody_verified"] = bool(custody.get("passed"))
        replay["voyage_binding_id"] = voyage.binding_id
        replay["replay_source"] = "post_custody_readback"
        replay["passed"] = bool(replay.get("passed") and replay["custody_verified"])
        if not replay["passed"]:
            raise RuntimeError(f"Chronus post-custody semantic replay failed: {replay}")

        replay_binding = self._put(
            self.REPLAY_KIND,
            replay,
            parents=(voyage.binding_id,),
            evidence_state="MEASURED",
        )
        if not self.port.fabric.verify(replay_binding.binding_id).get("passed"):
            raise RuntimeError("Chronus replay record failed shared custody verification")
        self.last_bindings = {"voyage": voyage, "replay": replay_binding}
        return {"report": report, "replay": replay}

    def replay(self) -> dict[str, Any]:
        source = "last_bindings"
        binding_id: str | None = None
        if "voyage" in self.last_bindings:
            binding_id = self.last_bindings["voyage"].binding_id
        else:
            latest = _latest_binding(
                self.port,
                source="chronus",
                kind=self.VOYAGE_KIND,
            )
            if latest is not None:
                binding_id = str(latest["binding_id"])
                source = "durable_graph"
        if binding_id is None:
            return {
                "schema": "aethel.chronus-custody-replay/1",
                "passed": False,
                "replay_source": "none",
                "error": "no Chronus startup voyage found",
            }
        payload = json.loads(self.port.read(binding_id).decode("utf-8"))
        boundary = verify_chronus_custody_boundary(payload)
        custody = self.port.fabric.verify(binding_id)
        return {
            **boundary,
            "passed": bool(boundary.get("passed") and custody.get("passed")),
            "custody_verified": bool(custody.get("passed")),
            "voyage_binding_id": binding_id,
            "replay_source": source,
        }

    def stop(self) -> None:
        self.raw.stop()


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

    def chronus(
        self,
        runtime: Any | None = None,
        *,
        store_dir: str | Path | None = None,
    ) -> SharedChronus:
        if runtime is None:
            from chronus.production import ChronusProductionRuntime

            if store_dir is None:
                raise ValueError("canonical Chronus binding requires store_dir")
            runtime = ChronusProductionRuntime(store_dir)
        return SharedChronus(runtime, self.ports["chronus"])

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
    "SharedChronus",
    "SharedTuring",
    "SharedEuclid",
    "ProductionSystemRelations",
    "verify_kellogg_custody_boundary",
    "verify_chronus_custody_boundary",
    "verify_turing_custody_boundary",
]
