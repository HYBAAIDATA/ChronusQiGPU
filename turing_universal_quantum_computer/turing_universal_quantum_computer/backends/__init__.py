"""TURING VQC backend registry.

One place that answers the only question that matters to a caller: *given this
program, which engine runs it, and what kind of answer comes back?*

Selection is deterministic and fail-closed.  A program that no backend can
answer exactly is **refused**; it is never quietly downgraded to an approximate
or simulated answer.  The QPU backend is never selected automatically, because
selecting it would imply hardware that this package does not have.
"""

from __future__ import annotations

from dataclasses import dataclass
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
from .mps import MPSExactBackend, schmidt_bound
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
    "MPSExactBackend",
    "schmidt_bound",
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
    "CertifiedExecution",
    "execute_certified",
    "execute",
]


@dataclass(frozen=True)
class CertifiedExecution:
    """One public execution with its certificate and bound run witness."""

    result: ExecutionResult
    certificate: Any
    witness: Any


def default_backends(
    *, max_amplitudes: int = DEFAULT_MAX_AMPLITUDES
) -> tuple[QuantumBackend, ...]:
    """The shipped backend set, in no particular priority order."""
    return (
        ExactFieldBackend(max_amplitudes=max_amplitudes),
        StabilizerBackend(),
        SparseExactBackend(),
        ClosedFormBackend(),
        MPSExactBackend(),
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
    # Clifford+T programs beyond the dense budget go to the exact MPS
    # backend, which admits them only when a static Schmidt bound stays
    # within chi_max at every cut — decided before execution, never
    # truncated. The sparse backend cannot prove bounded support statically,
    # so it remains reachable only by an explicit prefer="sparse".
    yield registry["mps_exact"]


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
    return execute_certified(
        program,
        prefer=prefer,
        max_amplitudes=max_amplitudes,
        **options,
    ).result


def execute_certified(
    program: Program,
    *,
    prefer: str | None = None,
    max_amplitudes: int = DEFAULT_MAX_AMPLITUDES,
    **options: Any,
) -> CertifiedExecution:
    """Execute through the public boundary and certify the computation.

    Sampling without an explicit seed is normalized to seed zero.  This is a
    deliberate public-boundary contract: every emitted certificate must replay.
    Low-level backend methods remain available for backend implementation tests.
    """
    # Imported here to avoid a registry/certificate import cycle.
    from ..certificates import (
        issue_computation_certificate,
        issue_witness,
        validate_certificate_inputs,
        verify_computation_certificate,
        verify_witness,
    )

    backend, admission = select_backend(
        program, prefer=prefer, max_amplitudes=max_amplitudes
    )
    if backend is None:
        raise StatevectorTooLargeError(
            "no backend can answer this program exactly: " + admission.reason
        )
    execution_options = dict(options)
    if (
        execution_options.get("shots") is not None
        and execution_options.get("seed") is None
    ):
        execution_options["seed"] = 0
    # Certificate-first: refuse inputs that can never be certified before the
    # backend runs.  On a hardware provider this is the difference between a
    # rejected call and an irreversible, billable submission.
    validate_certificate_inputs(program, execution_options)
    result = backend.execute(program, **execution_options)

    certificate = issue_computation_certificate(
        program,
        result,
        options=execution_options,
    )
    result.certificate = certificate.to_dict()
    verify_computation_certificate(
        program,
        result,
        certificate,
        options=execution_options,
    )
    provider_job = None
    if result.measured_qpu:
        provider_job = QPUJob(
            provider=str(result.payload.get("provider", "")),
            job_id=str(result.payload.get("job_id", "")),
            completed_at=str(result.payload.get("completed_at", "")),
            result_digest=str(result.payload.get("result_digest", "")),
        )
    witness = issue_witness(program, result, provider_job=provider_job)
    verify_witness(witness)
    return CertifiedExecution(result=result, certificate=certificate, witness=witness)
