"""Canonical production composition for the shared computational organism.

This root turns the shared THESEUS/OVID relationship from an available library
into the governed startup path for the memory/data-bearing subsystem surface.
It composes real PYTHIA, TOE, Kellogg, TURING, Salamander, AL HARAS and EUCLID
objects over one :class:`CompositionRoot` and exposes only shared-data-bound
views.

Authority is not collapsed:

* EUCLID orchestrates/delegates intelligence;
* PYTHIA retains predictive/causal intelligence ownership;
* Kellogg remains an intelligence/tensor substrate consumed by PYTHIA/TOE;
* TURING retains post-classical quantum computation ownership;
* Salamander retains healing/optimisation ownership;
* AL HARAS retains security/governance ownership;
* THESEUS owns durable custody; OVID owns transform/lineage.

EUCLID's ordinary organism factory historically opens a separate durable Triad
for its custody specialist. That is forbidden here. The runtime is created with
``organism=False`` and then composed with a shared Triad specialist backed by
the already-started SystemDataPort. Thus the EUCLID custody organ cannot become
a second source of truth.
"""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any, Mapping

from .entangled_custody import SystemDataPort
from .lifecycle import CompositionRoot
from .system_relations import DEFAULT_PEERS, ProductionSystemRelations


class _SharedTriadOrgan:
    """EUCLID's THESEUS/OVID specialist over the one shared enterprise fabric."""

    organ_id = "triad"
    owner = "THESEUS/OVID"

    def __init__(self, port: SystemDataPort) -> None:
        if port.system != "euclid":
            raise ValueError("shared Triad specialist requires the EUCLID data port")
        self.port = port

    @staticmethod
    def _payload_bytes(request: Mapping[str, Any]) -> bytes:
        if "payload_b64" in request:
            return base64.b64decode(str(request["payload_b64"]), validate=True)
        if "payload_utf8" in request:
            return str(request["payload_utf8"]).encode("utf-8")
        raise ValueError("request requires payload_b64 or payload_utf8")

    def _put(self, data: bytes, *, kind: str) -> Any:
        return self.port.put(
            kind,
            data,
            share_with=DEFAULT_PEERS["euclid"],
            meta={
                "custody_owner": "theseus",
                "transform_lineage_owner": "ovid",
                "euclid_specialist": "triad",
            },
        )

    def execute(self, request: Mapping[str, Any]) -> dict[str, Any]:
        operation = str(request.get("operation", "verify"))
        if operation == "put":
            data = self._payload_bytes(request)
            binding = self._put(data, kind="euclid_triad_payload")
            return {
                "owner": "THESEUS",
                "operation": operation,
                "binding_id": binding.binding_id,
                "custody_record_id": binding.custody_record_id,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        if operation == "get":
            binding_id = str(request["binding_id"])
            data = self.port.read(binding_id)
            return {
                "owner": "THESEUS",
                "operation": operation,
                "binding_id": binding_id,
                "payload_b64": base64.b64encode(data).decode("ascii"),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        if operation == "fold":
            data = self._payload_bytes(request)
            binding = self._put(data, kind="euclid_ovid_transform")
            restored = self.port.read(binding.binding_id)
            verdict = self.port.fabric.verify(binding.binding_id)
            return {
                "owner": "OVID",
                "operation": operation,
                "binding_id": binding.binding_id,
                "ovid_lineage_id": binding.ovid_lineage_id,
                "round_trip": restored == data,
                "verified": bool(verdict.get("passed")),
            }
        if operation == "verify":
            binding_id = request.get("binding_id")
            if binding_id is not None:
                verdict = self.port.fabric.verify(str(binding_id))
                return {
                    "owner": "THESEUS/OVID",
                    "operation": operation,
                    "verified": bool(verdict.get("passed")),
                    "binding_id": str(binding_id),
                }
            bindings = self.port.fabric.graph().get("bindings", ())
            verified = all(
                self.port.fabric.verify(str(item["binding_id"])).get("passed")
                for item in bindings
            )
            return {
                "owner": "THESEUS/OVID",
                "operation": operation,
                "verified": bool(verified),
                "bindings_checked": len(bindings),
            }
        raise ValueError(f"unsupported shared Triad operation: {operation}")


class ProductionOrganism:
    """One governed startup/shutdown boundary for the shared system graph."""

    def __init__(
        self,
        root: str | Path,
        *,
        hmac_key: bytes,
        creator_id: str = "pythia-operator",
        guardian: Any,
        tenant: str = "default",
        allow_insecure_dev_key: bool = False,
        intelligence: Any | None = None,
        euclid_runtime: Any | None = None,
    ) -> None:
        if guardian is None:
            raise ValueError("production organism requires an AL HARAS guardian")
        self.root = Path(root)
        self.creator_id = str(creator_id)
        self.guardian_input = guardian
        self._intelligence_input = intelligence
        self._euclid_input = euclid_runtime
        self.lifecycle = CompositionRoot(
            self.root / "theseus-ovid",
            tenant=tenant,
            hmac_key=hmac_key,
            allow_insecure_dev_key=allow_insecure_dev_key,
        )
        self.relations: ProductionSystemRelations | None = None
        self.intelligence: Any | None = None
        self.pythia: Any | None = None
        self.toe: Any | None = None
        self.kellogg: Any | None = None
        self.chronus: Any | None = None
        self.turing: Any | None = None
        self.salamander: Any | None = None
        self.al_haras: Any | None = None
        self.euclid: Any | None = None
        self._euclid_raw: Any | None = None
        self._chronus_startup_evidence: dict[str, Any] | None = None
        self._turing_startup_evidence: dict[str, Any] | None = None
        self._started = False

    @staticmethod
    def _registered_organs(runtime: Any) -> set[str]:
        registry = getattr(runtime, "registry", None)
        report = getattr(registry, "report", None)
        if not callable(report):
            return set()
        return {str(item.get("organ_id")) for item in report() if item.get("organ_id")}

    def start(self) -> "ProductionOrganism":
        if self._started:
            return self
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            self.lifecycle.start()
            relations = ProductionSystemRelations(self.lifecycle)

            if self._intelligence_input is None:
                from Intelligence.orchestrator import IntelligenceOrchestrator

                intelligence = IntelligenceOrchestrator(
                    store_dir=self.root / "pythia-local-cache"
                )
            else:
                intelligence = self._intelligence_input
            self.intelligence = relations.bind_intelligence(intelligence)
            self.pythia = self.intelligence
            self.toe = self.intelligence.toe
            self.salamander = self.intelligence.salamander

            self.al_haras = relations.bind_al_haras(self.guardian_input)
            self.kellogg = relations.kellogg()
            self.chronus = relations.chronus(store_dir=self.root / "chronus-runtime")
            self.turing = relations.turing()

            if self._euclid_input is None:
                from euclid import EuclidRuntime

                euclid_runtime = EuclidRuntime.production(
                    creator_id=self.creator_id,
                    state_dir=self.root / "euclid",
                    pythia=self.intelligence.pythia,
                    memory=self.intelligence.memory,
                    store=self.intelligence.store,
                    organism=False,
                )
            else:
                euclid_runtime = self._euclid_input
                already = self._registered_organs(euclid_runtime)
                if already & {"triad", "turing", "chronus"}:
                    raise RuntimeError(
                        "injected EUCLID runtime is already organism-composed; "
                        "production root cannot prove it avoided private Triad custody"
                    )

            self._euclid_raw = euclid_runtime
            euclid_runtime.compose_organism(
                guardian=self.al_haras,
                implementations={
                    "triad": _SharedTriadOrgan(relations.ports["euclid"]),
                },
            )
            self.euclid = relations.bind_euclid(euclid_runtime)
            self.relations = relations
            self._run_chronus_startup_gate()
            self._run_turing_startup_gate()
            self._started = True
            return self
        except Exception:
            self._fail_closed_cleanup()
            raise

    def _run_chronus_startup_gate(self) -> None:
        """Fail closed unless the canonical Chronus production voyage works."""
        self._chronus_startup_evidence = {
            "schema": "aethel.chronus-startup-gate/1",
            "passed": False,
        }
        try:
            if self.chronus is None:
                raise RuntimeError("canonical SharedChronus binding is unavailable")

            outcome = self.chronus.run_startup_voyage()
            report = outcome["report"]
            replay = self.chronus.replay()
            if not replay.get("passed"):
                raise RuntimeError("post-custody Chronus semantic replay did not pass")

            required = {"voyage", "replay"}
            missing = sorted(required - set(self.chronus.last_bindings))
            if missing:
                raise RuntimeError(
                    f"Chronus production evidence is missing bindings: {missing}"
                )

            binding_ids: dict[str, str] = {}
            failed: list[str] = []
            for name in sorted(required):
                binding = self.chronus.last_bindings[name]
                binding_ids[name] = binding.binding_id
                verdict = self.lifecycle.fabric.verify(binding.binding_id)
                if not verdict.get("passed"):
                    failed.append(name)
            if failed:
                raise RuntimeError(
                    f"Chronus shared custody verification failed: {failed}"
                )

            execution = report.get("execution") or {}
            self._chronus_startup_evidence = {
                "schema": "aethel.chronus-startup-gate/1",
                "passed": True,
                "mode": report.get("mode"),
                "physical_gpu_required": report.get("physical_gpu_required"),
                "actual_adapter_id": execution.get("actual_adapter_id"),
                "verification": execution.get("verification"),
                "math_pipeline": report.get("math_pipeline"),
                "qx_pipeline": report.get("qx_pipeline"),
                "replay_source": replay.get("replay_source"),
                "bindings": binding_ids,
                "hardware_claimed": report.get("hardware_claimed", False),
                "physical_qpu_claimed": report.get("physical_qpu_claimed", False),
            }
        except Exception as exc:
            self._chronus_startup_evidence = {
                "schema": "aethel.chronus-startup-gate/1",
                "passed": False,
                "error": f"{type(exc).__name__}: {exc}",
                "physical_gpu_required": False,
                "hardware_claimed": False,
                "physical_qpu_claimed": False,
            }
            raise RuntimeError(
                f"CHRONUS production startup gate failed: {exc}"
            ) from exc

    def _run_turing_startup_gate(self) -> None:
        """Fail closed unless the canonical TURING production voyage works.

        This is a real software execution through SharedTuring: exact VQC
        execution, computation certificate, witness, shared THESEUS/OVID
        custody, post-custody readback, and semantic replay. Hardware/QPU
        execution is deliberately not required for the software production
        gate and is not claimed by it.
        """
        self._turing_startup_evidence = {
            "schema": "aethel.turing-startup-gate/1",
            "passed": False,
        }
        try:
            if self.turing is None:
                raise RuntimeError("canonical SharedTuring binding is unavailable")

            from turing_universal_quantum_computer import Program
            from turing_universal_quantum_computer.pipeline import VQCRequest

            report = self.turing.run(
                VQCRequest(
                    program=(
                        Program(n_qubits=2)
                        .then("h", 0)
                        .then("cx", 0, 1)
                    ),
                    marginal_of=(0, 1),
                    differential=True,
                    notes="production_startup_gate",
                )
            )
            if report.verdict != "PASS":
                raise RuntimeError(
                    f"canonical TURING voyage verdict is {report.verdict!r}, not PASS"
                )

            replay = self.turing.replay()
            if not replay.get("passed"):
                raise RuntimeError(
                    "post-custody TURING semantic replay did not pass"
                )

            required = {
                "program",
                "result",
                "certificate",
                "witness",
                "report",
                "replay",
            }
            missing = sorted(required - set(self.turing.last_bindings))
            if missing:
                raise RuntimeError(
                    f"TURING production evidence is missing bindings: {missing}"
                )

            fabric = self.lifecycle.fabric
            failed = []
            binding_ids: dict[str, str] = {}
            for name in sorted(required):
                binding = self.turing.last_bindings[name]
                binding_ids[name] = binding.binding_id
                verdict = fabric.verify(binding.binding_id)
                if not verdict.get("passed"):
                    failed.append(name)
            if failed:
                raise RuntimeError(
                    f"TURING shared custody verification failed: {failed}"
                )

            certificate = report.certificate or {}
            self._turing_startup_evidence = {
                "schema": "aethel.turing-startup-gate/1",
                "passed": True,
                "pipeline_verdict": report.verdict,
                "program_digest": report.program_digest,
                "backend": (
                    report.result.get("backend")
                    if isinstance(report.result, dict)
                    else None
                ),
                "certificate_digest": certificate.get("certificate_digest"),
                "replay_source": replay.get("replay_source"),
                "report_binding_id": replay.get("report_binding_id"),
                "bindings": binding_ids,
                "hardware_claimed": False,
                "physical_qpu_claimed": False,
            }
        except Exception as exc:
            self._turing_startup_evidence = {
                "schema": "aethel.turing-startup-gate/1",
                "passed": False,
                "error": f"{type(exc).__name__}: {exc}",
                "hardware_claimed": False,
                "physical_qpu_claimed": False,
            }
            raise RuntimeError(
                f"TURING production startup gate failed: {exc}"
            ) from exc

    def _close_euclid(self) -> None:
        runtime = self.euclid
        raw = getattr(runtime, "raw", runtime) if runtime is not None else self._euclid_raw
        if raw is None:
            return
        close = getattr(raw, "close", None)
        if callable(close):
            close()
        self._euclid_raw = None

    def _fail_closed_cleanup(self) -> None:
        try:
            if self.chronus is not None:
                self.chronus.stop()
        except Exception:
            pass
        try:
            self._close_euclid()
        except Exception:
            pass
        try:
            self.lifecycle.stop()
        finally:
            self._started = False

    def stop(self) -> None:
        """Persist final state and close every layer even when one step fails."""
        if not self._started:
            self._fail_closed_cleanup()
            return

        first_error: Exception | None = None
        try:
            if self.intelligence is not None:
                store = getattr(self.intelligence, "store", None)
                save = getattr(store, "save", None)
                if callable(save):
                    save()
        except Exception as exc:
            first_error = exc

        try:
            if self.chronus is not None:
                self.chronus.stop()
        except Exception as exc:
            if first_error is None:
                first_error = exc

        try:
            self._close_euclid()
        except Exception as exc:
            if first_error is None:
                first_error = exc

        try:
            self.lifecycle.stop()
        except Exception as exc:
            if first_error is None:
                first_error = exc
        finally:
            self._started = False

        if first_error is not None:
            raise first_error

    def status(self) -> dict[str, Any]:
        lifecycle = self.lifecycle.readiness()
        raw_euclid = getattr(self.euclid, "raw", self.euclid)
        organs = self._registered_organs(raw_euclid) if raw_euclid is not None else set()
        chronus_gate_passed = bool(
            self._chronus_startup_evidence
            and self._chronus_startup_evidence.get("passed")
        )
        turing_gate_passed = bool(
            self._turing_startup_evidence
            and self._turing_startup_evidence.get("passed")
        )
        bound = {
            "pythia": self.pythia is not None,
            "toe": self.toe is not None,
            "kellogg": self.kellogg is not None,
            "turing": (
                self.turing is not None
                and "turing" in organs
                and turing_gate_passed
            ),
            "salamander": self.salamander is not None,
            "al_haras": self.al_haras is not None,
            "euclid": self.euclid is not None,
            "chronus": (
                self.chronus is not None
                and "chronus" in organs
                and chronus_gate_passed
            ),
            "theseus_ovid": "triad" in organs,
        }
        ready = bool(self._started and lifecycle.get("ready") and all(bound.values()))
        return {
            "schema": "aethel.production-organism/1",
            "ready": ready,
            "shared_custody_ready": bool(lifecycle.get("ready")),
            "bound_systems": bound,
            "authority_preserved": True,
            "custody_owner": "theseus",
            "transform_lineage_owner": "ovid",
            "euclid_private_triad_opened": False,
            "chronus_startup_gate": self._chronus_startup_evidence,
            "turing_startup_gate": self._turing_startup_evidence,
            "relations": self.relations.status() if self.relations is not None else None,
        }

    def __enter__(self) -> "ProductionOrganism":
        return self.start()

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.stop()


__all__ = ["ProductionOrganism"]
