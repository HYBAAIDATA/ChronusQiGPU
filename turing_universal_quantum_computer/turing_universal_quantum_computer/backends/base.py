"""Backend contract for the TURING VQC product boundary.

The VQC is a *virtual* quantum computer: an exact-algebra substrate on
classical hardware.  A backend is therefore not just a code path — it is a
**claim** about what kind of answer the caller will receive.  This module makes
that claim a first-class, checkable object so no backend can quietly return an
approximate answer labelled exact, or a simulated answer labelled measured.

Three ideas carry the boundary:

``ExecutionClass``
    *how* the answer is produced — exact algebra, exact closed form, a declared
    approximation, or real hardware.

``TruthClass``
    *what the caller may believe* about a specific returned result.

``Admission``
    whether a backend accepts a program at all, and the precise reason when it
    does not.  Admission is decided *before* execution, so an out-of-domain
    program is refused rather than truncated.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, Sequence, runtime_checkable

__all__ = [
    "ExecutionClass",
    "TruthClass",
    "Operation",
    "Program",
    "Capability",
    "Admission",
    "ExecutionResult",
    "QuantumBackend",
    "CLIFFORD_GATES",
    "TWO_QUBIT_GATES",
    "SWAP_GATES",
]

#: Gates that keep a state inside the stabilizer formalism (Gottesman-Knill).
CLIFFORD_GATES = frozenset({"i", "x", "y", "z", "h", "s", "sdg", "cx", "cnot", "cz", "swap"})
TWO_QUBIT_GATES = frozenset({"cx", "cnot", "cz", "swap"})
SWAP_GATES = frozenset({"swap"})


class ExecutionClass(str, Enum):
    """How a backend produces its answer."""

    #: Exact arithmetic in a closed algebraic field; state materialised.
    EXACT_ALGEBRAIC = "exact_algebraic"
    #: Exact symbolic formula; state never materialised.
    EXACT_SYMBOLIC = "exact_symbolic"
    #: Exact for a restricted state class, bounded by an explicit envelope.
    BOUNDED_EXACT = "bounded_exact"
    #: Declared approximation that must carry an error bound.
    APPROXIMATE = "approximate"
    #: A real provider-backed physical device.
    HARDWARE = "hardware"


class TruthClass(str, Enum):
    """What a caller may believe about one returned result."""

    EXACT = "exact"
    APPROXIMATE = "approximate"
    REFUSED = "refused"
    UNEXECUTED = "unexecuted"


@dataclass(frozen=True)
class Operation:
    """One gate application: ``gate`` on ``qubits``."""

    gate: str
    qubits: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.gate, str) or not self.gate:
            raise ValueError("operation requires a non-empty gate name")
        if any(not isinstance(q, int) or q < 0 for q in self.qubits):
            raise ValueError(f"operation {self.gate!r} has an invalid qubit index")


@dataclass(frozen=True)
class Program:
    """An immutable gate program: a register width plus an ordered operation list."""

    n_qubits: int
    operations: tuple[Operation, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.n_qubits, int) or self.n_qubits < 1:
            raise ValueError("n_qubits must be a positive integer")
        for operation in self.operations:
            for qubit in operation.qubits:
                if qubit >= self.n_qubits:
                    raise ValueError(
                        f"operation {operation.gate!r} addresses qubit {qubit}, "
                        f"outside a {self.n_qubits}-qubit register"
                    )

    # -- construction helpers ----------------------------------------------
    def then(self, gate: str, *qubits: int) -> "Program":
        """Return a new program with one more operation appended."""
        return Program(self.n_qubits, self.operations + (Operation(gate.lower(), tuple(qubits)),))

    # -- inspection ---------------------------------------------------------
    def gate_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for operation in self.operations:
            counts[operation.gate] = counts.get(operation.gate, 0) + 1
        return counts

    def gates(self) -> frozenset[str]:
        return frozenset(self.gate_counts())

    def is_clifford(self) -> bool:
        return self.gates() <= CLIFFORD_GATES

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_qubits": self.n_qubits,
            "operations": [{"gate": o.gate, "qubits": list(o.qubits)} for o in self.operations],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Program":
        return cls(
            int(payload["n_qubits"]),
            tuple(Operation(o["gate"], tuple(o["qubits"])) for o in payload.get("operations", [])),
        )

    def digest(self) -> str:
        """Stable SHA-256 over the canonical program form.

        Used by run witnesses so a certificate names the exact circuit that
        produced it, independent of formatting or key order.
        """
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def __str__(self) -> str:
        body = ", ".join(
            f"{o.gate} {' '.join(str(q) for q in o.qubits)}" for o in self.operations
        )
        return f"Program(n={self.n_qubits}; {body})"


@dataclass(frozen=True)
class Capability:
    """A backend's declared envelope.  This is what the product publishes."""

    name: str
    execution_class: ExecutionClass
    materialises_state: bool
    gate_set: str
    state_classes: tuple[str, ...]
    max_qubits: int | None
    requires: tuple[str, ...] = ()
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "backend": self.name,
            "execution_class": self.execution_class.value,
            "materialises_state": self.materialises_state,
            "gate_set": self.gate_set,
            "state_classes": list(self.state_classes),
            "max_qubits": self.max_qubits,
            "requires": list(self.requires),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class Admission:
    """The pre-execution verdict for one (backend, program) pair."""

    admitted: bool
    backend: str
    reason: str
    execution_class: ExecutionClass

    def as_dict(self) -> dict[str, Any]:
        return {
            "admitted": self.admitted,
            "backend": self.backend,
            "reason": self.reason,
            "execution_class": self.execution_class.value,
        }


@dataclass
class ExecutionResult:
    """The outcome of one admitted execution."""

    backend: str
    execution_class: ExecutionClass
    truth_class: TruthClass
    n_qubits: int
    program_digest: str
    materialised: bool
    payload: dict[str, Any] = field(default_factory=dict)
    refusals: tuple[str, ...] = ()
    #: True only when a real, non-simulator provider job completed.
    measured_qpu: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "execution_class": self.execution_class.value,
            "truth_class": self.truth_class.value,
            "n_qubits": self.n_qubits,
            "program_digest": self.program_digest,
            "materialised": self.materialised,
            "refusals": list(self.refusals),
            "measured_qpu": self.measured_qpu,
            "payload": self.payload,
        }


@runtime_checkable
class QuantumBackend(Protocol):
    """What the registry requires of every backend."""

    name: str

    def capability(self) -> Capability: ...

    def available(self) -> tuple[bool, str]:
        """``(is_available, reason_if_not)``.  Absent must stay absent."""

    def admit(self, program: Program) -> Admission: ...

    def execute(self, program: Program, **options: Any) -> ExecutionResult: ...
