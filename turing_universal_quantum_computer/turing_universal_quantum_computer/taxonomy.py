"""Canonical execution-kind and evidence-state taxonomy for the TURING VQC.

The canonical manual's execution-truth rule: every result must distinguish

* mathematical quantum formalism;
* classical exact/reference computation;
* classical quantum simulation;
* Turing VQC execution;
* quantum-inspired method;
* hardware-accelerated classical/VQC execution;
* physical quantum/QPU execution.

Those categories must never be collapsed.  A quantum name, Grover-style
formalism, logical-qubit count, simulator output, or GPU dispatch is not
evidence of physical QPU execution.  This module makes the distinction a
first-class, checkable value on every result the production pipeline emits,
exactly as ``ExecutionClass``/``TruthClass`` already make the per-backend
claim checkable.

``classify_execution`` is deliberately conservative: it returns the weakest
kind the evidence supports.  ``PHYSICAL_QPU`` is reachable only through
``assert_measured_qpu`` — a completed provider job verified against the
result — and never through naming, backend selection, or device presence.
A device present is not a device used; device-bound acceleration evidence is
required before ``HARDWARE_ACCELERATED`` may be reported.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .backends.base import ExecutionClass, ExecutionResult, TruthClass

__all__ = [
    "ExecutionKind",
    "EvidenceState",
    "ExecutionKindReport",
    "classify_execution",
    "evidence_states",
]


class ExecutionKind(str, Enum):
    """What kind of computation actually produced a result (canonical order)."""

    #: The mathematics of quantum mechanics expressed symbolically; no state
    #: evolution ran (closed forms, identities, formal claims).
    MATHEMATICAL_FORMALISM = "mathematical_quantum_formalism"
    #: Exact classical arithmetic used as a reference answer (e.g. dense
    #: statevector algebra over Q(sqrt(2)) + i*Q(sqrt(2))).
    CLASSICAL_REFERENCE = "classical_exact_reference"
    #: A classical simulation of quantum dynamics whose output is a
    #: simulation result, not a hardware measurement.
    CLASSICAL_SIMULATION = "classical_quantum_simulation"
    #: Execution through the Turing VQC composition path on an admitted
    #: Turing backend (exact state classes on classical hardware).
    TURING_VQC = "turing_vqc_execution"
    #: A quantum-*inspired* classical method (schedules, rankers, anneal-like
    #: heuristics); not a circuit execution at all.
    QUANTUM_INSPIRED = "quantum_inspired_method"
    #: A Turing VQC or classical workload executed on bound physical
    #: acceleration hardware (Chronus iGPU/GPU/other) with device evidence.
    HARDWARE_ACCELERATED = "hardware_accelerated_execution"
    #: A completed physical-QPU provider job, verified by ``assert_measured_qpu``.
    PHYSICAL_QPU = "physical_qpu_execution"


class EvidenceState(str, Enum):
    """The shared evidence doctrine: optimistic values are never substituted."""

    PASS = "PASS"
    FAIL = "FAIL"
    MEASURED = "MEASURED"
    GATED = "GATED"
    UNAVAILABLE = "UNAVAILABLE"
    MISSING = "MISSING"
    REFUTED = "REFUTED"


def evidence_states() -> tuple[str, ...]:
    """The permitted evidence states, in canonical order."""
    return tuple(state.value for state in EvidenceState)


@dataclass(frozen=True)
class ExecutionKindReport:
    """The classified truth of one result — what a caller may claim."""

    kind: str
    backend: str
    execution_class: str
    truth_class: str
    measured_qpu: bool
    hardware_evidence: str
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "backend": self.backend,
            "execution_class": self.execution_class,
            "truth_class": self.truth_class,
            "measured_qpu": self.measured_qpu,
            "hardware_evidence": self.hardware_evidence,
            "rationale": self.rationale,
        }


def classify_execution(
    result: ExecutionResult,
    *,
    device_bound: bool = False,
    via_pipeline: bool = True,
) -> ExecutionKindReport:
    """Classify one ``ExecutionResult`` into the canonical execution kind.

    Parameters
    ----------
    result:
        The backend's result object.
    device_bound:
        True only when the execution was actually dispatched to a bound
        physical accelerator for this run (device identity + dispatch record),
        not merely that a device exists on the host.
    via_pipeline:
        True when the result came through the Turing production composition
        path (capability analysis -> admission -> execution -> verification),
        which is what makes it *Turing VQC execution* rather than a bare
        classical evaluation of the same algebra.
    """
    exec_class = result.execution_class
    backend = result.backend

    if result.measured_qpu:
        # reachable only after assert_measured_qpu verified a provider job
        return ExecutionKindReport(
            kind=ExecutionKind.PHYSICAL_QPU.value,
            backend=backend,
            execution_class=exec_class.value,
            truth_class=result.truth_class.value,
            measured_qpu=True,
            hardware_evidence="provider_job_verified",
            rationale="completed provider job bound to this result by assert_measured_qpu",
        )
    if exec_class is ExecutionClass.HARDWARE:
        # A hardware-class result that is not measured_qpu is not a QPU claim;
        # it is a bound-accelerator claim and needs device-bound evidence.
        if device_bound:
            return ExecutionKindReport(
                kind=ExecutionKind.HARDWARE_ACCELERATED.value,
                backend=backend,
                execution_class=exec_class.value,
                truth_class=result.truth_class.value,
                measured_qpu=False,
                hardware_evidence="device_bound_dispatch",
                rationale="workload dispatched to a bound physical accelerator",
            )
        return ExecutionKindReport(
            kind=ExecutionKind.TURING_VQC.value,
            backend=backend,
            execution_class=exec_class.value,
            truth_class=result.truth_class.value,
            measured_qpu=False,
            hardware_evidence="unverified_device_binding",
            rationale="hardware-class result without device-bound dispatch evidence; "
            "reported as unaccelerated",
        )
    if result.truth_class in (TruthClass.REFUSED, TruthClass.UNEXECUTED):
        kind = ExecutionKind.TURING_VQC if via_pipeline else ExecutionKind.CLASSICAL_SIMULATION
        return ExecutionKindReport(
            kind=kind.value,
            backend=backend,
            execution_class=exec_class.value,
            truth_class=result.truth_class.value,
            measured_qpu=False,
            hardware_evidence="none",
            rationale="no execution result to classify; refusal/unexecuted is itself the truth",
        )
    if exec_class is ExecutionClass.APPROXIMATE:
        return ExecutionKindReport(
            kind=ExecutionKind.CLASSICAL_SIMULATION.value,
            backend=backend,
            execution_class=exec_class.value,
            truth_class=result.truth_class.value,
            measured_qpu=False,
            hardware_evidence="none",
            rationale="declared approximate backend: classical simulation output",
        )
    if via_pipeline:
        return ExecutionKindReport(
            kind=ExecutionKind.TURING_VQC.value,
            backend=backend,
            execution_class=exec_class.value,
            truth_class=result.truth_class.value,
            measured_qpu=False,
            hardware_evidence="none",
            rationale="executed through the Turing VQC composition path on an "
            "admitted Turing backend (exact state class on classical hardware)",
        )
    return ExecutionKindReport(
        kind=ExecutionKind.CLASSICAL_REFERENCE.value,
        backend=backend,
        execution_class=exec_class.value,
        truth_class=result.truth_class.value,
        measured_qpu=False,
        hardware_evidence="none",
        rationale="exact classical evaluation outside the Turing composition path",
    )
