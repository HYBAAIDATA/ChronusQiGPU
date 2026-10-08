"""PCI API — FastAPI surface over the exact engines.

Every endpoint computes a real result: exact quantum state operations or
exact causal inference.  There are no civilization/consciousness/national-
security endpoints — the retired versions fabricated those outputs and
are not reimplemented.

Session state is process-local (one engine per session id); the contract
is stateless-per-request where possible: create a session, apply declared
gates, read exact results.  Unrepresentable rotations return 422 with the
honest reason.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from pci.engine import (
    CausalMode,
    ExactQuantumComputer,
    GateNotExactlyRepresentable,
    InsufficientEvidence,
    PredictiveCausalIntelligence,
)

try:
    from pci.transparency_dashboard import PCITransparencyDashboard
except ImportError:  # pragma: no cover
    PCITransparencyDashboard = None  # type: ignore


def install_intelligence_middleware(app, service=None):  # kept for mount compat
    """No-op: there is no intelligence middleware in the exact engine."""
    return app


class GateRequest(BaseModel):
    gate: str
    qubits: List[int] = Field(default_factory=list)
    eighth_turns: Optional[int] = None
    quarter_turns: Optional[int] = None


class PrepareRequest(BaseModel):
    num_qubits: int = 2
    max_amplitudes: Optional[int] = None


class MeasureRequest(BaseModel):
    shots: int = 1
    collapse: bool = False
    seed: Optional[int] = None


class ObserveRequest(BaseModel):
    assignments: List[Dict[str, int]]


class DeclareRequest(BaseModel):
    variables: Dict[str, List[int]] = Field(default_factory=dict)
    parents: Dict[str, List[str]] = Field(default_factory=dict)


class PredictRequest(BaseModel):
    target: str
    evidence: Dict[str, int] = Field(default_factory=dict)
    do: Dict[str, int] = Field(default_factory=dict)


class PostQuantumCivilizationAPI:
    """Router exposing the real PCI engines — kept under the legacy class
    name so the AGI optional mount resolves.  The surface it serves is the
    honest one: exact quantum ops + exact causal inference."""

    def __init__(self):
        self.router = APIRouter()
        self._quantum: Dict[str, ExactQuantumComputer] = {}
        self._causal: Dict[str, PredictiveCausalIntelligence] = {}
        self._dashboard = PCITransparencyDashboard() if PCITransparencyDashboard else None
        self._setup_routes()

    def get_router(self) -> APIRouter:
        return self.router

    def _qc(self, session: str) -> ExactQuantumComputer:
        try:
            return self._quantum[session]
        except KeyError:
            raise HTTPException(404, f"no such quantum session {session!r}")

    def _ce(self, session: str) -> PredictiveCausalIntelligence:
        try:
            return self._causal[session]
        except KeyError:
            raise HTTPException(404, f"no such causal session {session!r}")

    def _setup_routes(self) -> None:
        router = self.router

        @router.get("/api/health", tags=["System"])
        def health() -> Dict[str, Any]:
            return {
                "ok": True,
                "service": "pci-exact-engines",
                "provenance": ExactQuantumComputer.provenance(),
                "quantum_sessions": len(self._quantum),
                "causal_sessions": len(self._causal),
            }

        # -- exact quantum surface -------------------------------------
        @router.post("/api/pci/quantum/prepare", tags=["Quantum"])
        def prepare(req: PrepareRequest) -> Dict[str, Any]:
            sid = uuid.uuid4().hex[:12]
            try:
                self._quantum[sid] = ExactQuantumComputer(
                    req.num_qubits, max_amplitudes=req.max_amplitudes
                )
            except (ValueError, MemoryError) as exc:
                raise HTTPException(422, str(exc))
            return {
                "session": sid,
                "num_qubits": req.num_qubits,
                "provenance": ExactQuantumComputer.provenance(),
            }

        @router.post("/api/pci/quantum/{session}/gate", tags=["Quantum"])
        def apply_gate(session: str, req: GateRequest) -> Dict[str, Any]:
            qc = self._qc(session)
            name = req.gate.lower()
            try:
                if name in ("rz", "u1"):
                    if req.eighth_turns is None:
                        raise HTTPException(422, f"{name} requires eighth_turns")
                    qc.rz(req.qubits[0], req.eighth_turns)
                elif name in ("rx", "ry"):
                    if req.quarter_turns is None:
                        raise HTTPException(422, f"{name} requires quarter_turns")
                    getattr(qc, name)(req.qubits[0], req.quarter_turns)
                elif name in ("u2",):
                    qc.u2(req.qubits[0], req.eighth_turns or 0, req.quarter_turns or 0)
                elif name in ("u3",):
                    qc.u3(req.qubits[0], req.quarter_turns or 0, req.eighth_turns or 0, 0)
                elif name == "diffusion":
                    qc.diffusion(req.qubits or None)
                elif name in ("cnot", "cx", "cy", "cz", "swap"):
                    getattr(qc, name)(req.qubits[0], req.qubits[1])
                elif name == "ccx":
                    getattr(qc, name)(req.qubits[0], req.qubits[1], req.qubits[2])
                else:
                    fn = getattr(qc, name, None)
                    if fn is None or name.startswith("_"):
                        raise HTTPException(422, f"unknown gate {req.gate!r}")
                    fn(req.qubits[0])
            except GateNotExactlyRepresentable as exc:
                raise HTTPException(422, f"not exactly representable: {exc}")
            except (ValueError, IndexError) as exc:
                raise HTTPException(422, str(exc))
            return {"session": session, "applied": name, "state": qc.get_statevector_exact()}

        @router.get("/api/pci/quantum/{session}/state", tags=["Quantum"])
        def state(session: str) -> Dict[str, Any]:
            qc = self._qc(session)
            return {
                "session": session,
                "amplitudes": qc.get_statevector_exact(),
                "born_weights": qc.probabilities_exact(),
                "inspection": qc.introspect_quantum_state(),
            }

        @router.post("/api/pci/quantum/{session}/measure", tags=["Quantum"])
        def measure(session: str, req: MeasureRequest) -> Dict[str, Any]:
            qc = self._qc(session)
            if req.seed is not None:
                return {
                    "session": session,
                    "histogram": qc.sample(req.shots, req.seed),
                    "sampling": "seeded_over_exact_weights",
                }
            return {
                "session": session,
                "outcomes": qc.measure(req.shots, req.collapse),
                "born_weights": qc.probabilities_exact(),
                "sampling": "deterministic_exact",
            }

        @router.post("/api/pci/quantum/{session}/evolve", tags=["Quantum"])
        def evolve(session: str, hamiltonian: str, quarter_turns: int) -> Dict[str, Any]:
            qc = self._qc(session)
            try:
                qc.evolve_hamiltonian(hamiltonian, quarter_turns)
            except (ValueError, NotImplementedError) as exc:
                raise HTTPException(422, str(exc))
            return {"session": session, "born_weights": qc.probabilities_exact()}

        # -- exact causal surface ---------------------------------------
        @router.post("/api/pci/causal/session", tags=["Causal"])
        def causal_session(mode: CausalMode = CausalMode.CAUSAL_PREDICTION) -> Dict[str, Any]:
            sid = uuid.uuid4().hex[:12]
            self._causal[sid] = PredictiveCausalIntelligence(mode=mode)
            return {"session": sid, "mode": mode.value}

        @router.post("/api/pci/causal/{session}/declare", tags=["Causal"])
        def declare(session: str, req: DeclareRequest) -> Dict[str, Any]:
            ce = self._ce(session)
            for name, vals in req.variables.items():
                ce.declare_variable(name, vals)
            for var, parents in req.parents.items():
                ce.declare_parents(var, parents)
            return {"session": session, "variables": req.variables, "parents": req.parents}

        @router.post("/api/pci/causal/{session}/observe", tags=["Causal"])
        def observe(session: str, req: ObserveRequest) -> Dict[str, Any]:
            ce = self._ce(session)
            try:
                ce.observe_many(req.assignments)
            except InsufficientEvidence as exc:
                raise HTTPException(422, str(exc))
            return {"session": session, "total_observations": ce.total_observations()}

        @router.post("/api/pci/causal/{session}/predict", tags=["Causal"])
        def predict(session: str, req: PredictRequest) -> Dict[str, Any]:
            ce = self._ce(session)
            try:
                pred = ce.predict(req.target, evidence=req.evidence or None, do=req.do or None)
            except InsufficientEvidence as exc:
                raise HTTPException(422, str(exc))
            return {
                "session": session,
                "target": pred.target,
                "probabilities": {k: str(v) for k, v in pred.probabilities.items()},
                "evidence_samples": pred.evidence_samples,
                "mechanism": pred.mechanism,
                "provenance": pred.provenance,
            }

        @router.post("/api/pci/causal/{session}/relationship", tags=["Causal"])
        def relationship(session: str, cause: str, effect: str) -> Dict[str, Any]:
            ce = self._ce(session)
            try:
                rel = ce.analyze_relationship(cause, effect)
            except InsufficientEvidence as exc:
                raise HTTPException(422, str(exc))
            return {
                "cause": rel.cause,
                "effect": rel.effect,
                "strength": str(rel.strength),
                "conditional_given": str(rel.conditional_given),
                "conditional_without": str(rel.conditional_without),
                "evidence_samples": rel.evidence_samples,
                "direction": rel.direction,
            }

        # -- transparency dashboard --------------------------------------
        @router.post("/api/pci/causal-graph", tags=["Transparency Dashboard"])
        def causal_graph(session: str, cause: str, effect: str) -> Dict[str, Any]:
            if self._dashboard is None:
                raise HTTPException(503, "dashboard unavailable")
            ce = self._ce(session)
            try:
                rel = ce.analyze_relationship(cause, effect)
            except InsufficientEvidence as exc:
                raise HTTPException(422, str(exc))
            gid = self._dashboard.create_causal_graph([rel])
            return {"graph_id": gid, "data": self._dashboard.get_visualization_data(gid)}

        @router.get("/api/pci/visualization/{graph_id}", tags=["Transparency Dashboard"])
        def visualization(graph_id: str) -> Dict[str, Any]:
            if self._dashboard is None or graph_id not in self._dashboard._graphs:
                raise HTTPException(404, "no such graph")
            return self._dashboard.get_visualization_data(graph_id)
