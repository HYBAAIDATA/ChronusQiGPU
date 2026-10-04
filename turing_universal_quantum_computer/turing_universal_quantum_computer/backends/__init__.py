"""TURING VQC backend registry.

One place that answers the only question that matters to a caller: *given this
program, which engine runs it, and what kind of answer comes back?*

Selection is deterministic and fail-closed.  A program that no backend can
answer exactly is **refused**; it is never quietly downgraded to an approximate
or simulated answer.  The QPU backend is never selected automatically, because
selecting it would imply hardware that this package does not have.
"""

from __future__ import annotations

from typing import Any, Iterable

from .algebraic import ExactFieldBackend, SUPPORTED_GATES
from .base import (
    Admission,
    Capability,
    CLIFFORD_GATES,
    ExecutionClass,
    ExecutionResult,
    Operation,
    Program,
    QuantumBackend,
    TruthClass,
)
from .exact_algebra import Exact, Q2
from .native import ClosedFormBackend, SparseExactBackend, StabilizerBackend
from .qpu import (
    QPUBackend,
    QPUClaimError,
    QPUJob,
    QPUProvider,
    QPUUnavailableError,
    assert_measured_qpu,
    available_providers,
    register_provider,
    reset_providers,
)
from .reference import (
    DEFAULT_MAX_AMPLITUDES,
    DomainError,
    ExactStatevector,
    StatevectorTooLargeError,
    gate_names,
)

__all__ = [
    # contract
    "Admission",
    "Capability",
    "CLIFFORD_GATES",
    "ExecutionClass",
    "ExecutionResult",
    "Operation",
    "Program",
    "QuantumBackend",
    "TruthClass",
    # algebra
    "Exact",
    "Q2",
    "ExactStatevector",
    "DEFAULT_MAX_AMPLITUDES",
    "DomainError",
    "StatevectorTooLargeError",
    "gate_names",
    "SUPPORTED_GATES",
    # backends
    "ExactFieldBackend",
    "StabilizerBackend",
    "SparseExactBackend",
    "ClosedFormBackend",
    "QPUBackend",
    "QPUUnavailableError",
    "QPUClaimError",
    "QPUJob",
    "QPUProvider",
    "assert_measured_qpu",
    "available_providers",
    "register_provider",
    "reset_providers",
    # registry
    "default_backends",
    "backend_registry",
    "backend_matrix",
    "select_backend",
    "execute",
]


def default_backends(
    *, max_amplitudes: int = DEFAULT_MAX_AMPLITUDES
) -> tuple[QuantumBackend, ...]:
    """The shipped backend set, in no particular priority order."""
    return (
        ExactFieldBackend(max_amplitudes=max_amplitudes),
        StabilizerBackend(),
        SparseExactBackend(),
        ClosedFormBackend(),
        QPUBackend(),
    )


def backend_registry(
    *, max_amplitudes: int = DEFAULT_MAX_AMPLITUDES
) -> dict[str, QuantumBackend]:
    return {backend.name: backend for backend in default_backends(max_amplitudes=max_amplitudes)}


def backend_matrix(*, max_amplitudes: int = DEFAULT_MAX_AMPLITUDES) -> list[dict[str, Any]]:
    """The published capability matrix, with live availability."""
    rows = []
    for backend in default_backends(max_amplitudes=max_amplitudes):
        available, reason = backend.available()
        row = backend.capability().as_dict()
        row["available"] = available
        row["availability"] = reason
        rows.append(row)
    return rows


def _selection_order(
    program: Program, *, max_amplitudes: int
) -> Iterable[QuantumBackend]:
    """Deterministic preference order for a program.

    The exact algebraic backend is preferred while the state fits, because it
    is universal and returns a full state vector.  Beyond that budget the
    Clifford/stabilizer backend takes over — that is the honest 10,000-qubit
    path.  Hardware is never auto-selected.
    """
    registry = backend_registry(max_amplitudes=max_amplitudes)
    fits_budget = (1 << program.n_qubits) <= max_amplitudes
    if fits_budget:
        yield registry["exact_algebraic"]
        yield registry["stabilizer"]
        yield registry["sparse"]
        return
    if program.is_clifford():
        yield registry["stabilizer"]
        # The sparse engine stays a fallback for Clifford programs: bounded
        # support is enforced by the register at run time (fail-closed), so a
        # state that densifies raises instead of fabricating an answer.
        yield registry["sparse"]
    # Non-Clifford programs beyond the dense budget get no candidate: the
    # sparse backend cannot prove bounded support statically, so admitting it
    # here would be an unverifiable selection.  It remains reachable only by
    # an explicit prefer="sparse" from a caller that knows its state is
    # bounded; automatic selection refuses rather than approximates.


def select_backend(
    program: Program,
    *,
    prefer: str | None = None,
    max_amplitudes: int = DEFAULT_MAX_AMPLITUDES,
) -> tuple[QuantumBackend | None, Admission]:
    """Choose a backend for ``program``.

    Returns ``(backend, admission)``.  ``backend`` is None exactly when no
    backend admits the program, in which case ``admission.reason`` says why.
    """
    registry = backend_registry(max_amplitudes=max_amplitudes)
    if prefer is not None:
        if prefer not in registry:
            raise ValueError(
                f"unknown backend {prefer!r}; available: {sorted(registry)}"
            )
        backend = registry[prefer]
        return backend, backend.admit(program)
    last: Admission | None = None
    for backend in _selection_order(program, max_amplitudes=max_amplitudes):
        admission = backend.admit(program)
        if admission.admitted:
            return backend, admission
        last = admission
    if last is None:
        last = Admission(
            False,
            "none",
            "no backend admits this program",
            ExecutionClass.EXACT_ALGEBRAIC,
        )
    return None, last


def execute(
    program: Program,
    *,
    prefer: str | None = None,
    max_amplitudes: int = DEFAULT_MAX_AMPLITUDES,
    **options: Any,
) -> ExecutionResult:
    """Select a backend and run the program, or refuse.

    Raises ``StatevectorTooLargeError`` (a ``MemoryError``) when no backend can
    answer the program exactly.  Refusal is the correct outcome there: the
    package will not return a number it cannot stand behind.
    """
    backend, admission = select_backend(
        program, prefer=prefer, max_amplitudes=max_amplitudes
    )
    if backend is None:
        raise StatevectorTooLargeError(
            "no backend can answer this program exactly: " + admission.reason
        )
    return backend.execute(program, **options)
