"""Exact Lucas/Pisot scaling contracts for quantum and iGPU execution.

Canonical Lucas-substrate home of the scale contracts, the Hendrix
coprime-stride schedule, the Hilbert coverage plan, and the physical
execution-scale gate.  This module is pure algebra: it depends only on
``lucas.core`` and the standard library.  The ``src.euclid`` research
surface re-exports these names so there is exactly one source of truth.

Lucas values are exact integers from ``lucas.core``. Pisot is represented as
an algebraic convergence contract rather than a floating-point multiplier.
Scaling changes deterministic budgets, partitions, and audit metadata; it
never changes a unitary into a non-unitary operator and never fabricates
hash-rate or quantum speedup.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import gcd
from typing import Dict, Iterator, Optional, Tuple

from .turing_core import lucas

THEOREM_PROVEN = False

SUPPORTED_SCALE_INDICES: Tuple[int, ...] = (7, 10, 12, 15, 18, 20, 31, 50, 76)
DOMAIN_SCALE_INDEX: Dict[str, int] = {
    "qubit_gate": 12,
    "qft": 15,
    "grover": 18,
    "ctqw": 20,
    "aqo": 31,
    "memory": 50,
    "structured_search": 76,
}


@dataclass(frozen=True)
class LucasPisotScale:
    domain: str
    index: int
    lucas_value: int
    pisot_conjugate: str = "(1-sqrt(5))/2"

    @property
    def drift_expression(self) -> str:
        return f"abs({self.pisot_conjugate})^{self.index}"

    def budget(self, base: int) -> int:
        if base < 0:
            raise ValueError("base budget must be non-negative")
        return int(Fraction(base * self.lucas_value, lucas(7)))

    def as_dict(self) -> dict:
        return {
            "domain": self.domain,
            "index": self.index,
            "lucas_value": self.lucas_value,
            "pisot_conjugate": self.pisot_conjugate,
            "drift_expression": self.drift_expression,
        }


def resolve_scale(domain: str, index: Optional[int] = None) -> LucasPisotScale:
    chosen = DOMAIN_SCALE_INDEX.get(domain, 7) if index is None else int(index)
    if chosen not in SUPPORTED_SCALE_INDICES:
        raise ValueError(f"unsupported Lucas/Pisot scale index: {chosen}")
    return LucasPisotScale(domain, chosen, lucas(chosen))


def scaled_budget(domain: str, base: int, index: Optional[int] = None) -> int:
    return resolve_scale(domain, index).budget(base)


def operation_record(
    domain: str, operation: str, logical_work: int, index: Optional[int] = None
) -> dict:
    if logical_work < 0:
        raise ValueError("logical_work must be non-negative")
    scale = resolve_scale(domain, index)
    return {
        "operation": operation,
        "logical_work": logical_work,
        "scaled_budget": scale.budget(logical_work),
        "scale": scale.as_dict(),
        "execution_truth": "exact_operator_or_deterministic_schedule",
    }


# ---------------------------------------------------------------------------
# Physical execution ladder: the rungs hardware dispatch may admit.  Index 7
# is an algebraic-only rung; it is deliberately excluded here — identical to
# the MLA1517 platform gate in ``mla1517.mining.pow``.

LUCAS_EXECUTION_SCALE_INDICES: Tuple[int, ...] = (10, 12, 15, 18, 20, 31, 50, 76)


class LucasScaleError(ValueError):
    """A work allocation requested a scale index outside the Lucas ladder."""


def require_lucas_execution_scale(index: int) -> int:
    """Hardware gate: reject any allocation whose scale index deviates from
    the declared Lucas ladder. Returns the validated index."""
    if isinstance(index, bool) or not isinstance(index, int):
        raise LucasScaleError("Lucas execution scale index must be an integer")
    if index not in LUCAS_EXECUTION_SCALE_INDICES:
        raise LucasScaleError(
            f"scale index {index} deviates from the Lucas execution ladder "
            f"{LUCAS_EXECUTION_SCALE_INDICES}"
        )
    return index


# ---------------------------------------------------------------------------
# Hendrix structured-search schedule: coprime-stride permutation, verified
# bijective over the nonce window.


def _coprime_stride(count: int, preferred: int) -> int:
    if count <= 1:
        return 1
    stride = preferred % count or 1
    while gcd(stride, count) != 1:
        stride = (stride + 1) % count or 1
    return stride


@dataclass(frozen=True)
class HendrixSchedule:
    nonce_count: int
    workers: int
    stride: int
    scale: LucasPisotScale

    @property
    def coverage(self) -> int:
        return self.nonce_count

    def nonce_at(self, permutation_position: int) -> int:
        if not 0 <= permutation_position < self.nonce_count:
            raise IndexError("permutation position outside nonce space")
        return (permutation_position * self.stride) % self.nonce_count

    def worker_positions(self, worker_id: int) -> Iterator[int]:
        if not 0 <= worker_id < self.workers:
            raise IndexError("worker outside schedule")
        return iter(range(worker_id, self.nonce_count, self.workers))

    def worker_nonces(self, worker_id: int) -> Iterator[int]:
        return (self.nonce_at(position) for position in self.worker_positions(worker_id))

    def verify(self) -> bool:
        return (
            self.nonce_count > 0
            and 1 <= self.workers <= self.nonce_count
            and gcd(self.stride, self.nonce_count) == 1
            and sum(1 for _ in self.worker_positions(0)) >= 1
        )

    def manifest(self) -> dict:
        return {
            "nonce_count": self.nonce_count,
            "workers": self.workers,
            "stride": self.stride,
            "coverage": self.coverage,
            "disjointness_proof": f"gcd({self.stride},{self.nonce_count})=1; worker position classes partition [0,{self.nonce_count})",
            "scale": self.scale.as_dict(),
        }


class HendrixStructuredSearch:
    """Lucas/Pisot-scaled deterministic scheduler for the iGPU search path."""

    def __init__(self, workers: int = 1, scale_index: Optional[int] = None):
        if workers < 1:
            raise ValueError("workers must be positive")
        self.workers = int(workers)
        self.scale = resolve_scale("structured_search", scale_index)

    def plan(self, nonce_count: int) -> HendrixSchedule:
        if nonce_count < 1:
            raise ValueError("nonce_count must be positive")
        workers = min(self.workers, nonce_count)
        stride = _coprime_stride(nonce_count, self.scale.lucas_value)
        schedule = HendrixSchedule(nonce_count, workers, stride, self.scale)
        if not schedule.verify():
            raise RuntimeError("Hendrix schedule invariant failure")
        return schedule

    def search(self, nonce_count: int, evaluate) -> dict:
        schedule = self.plan(nonce_count)
        evaluated = 0
        winner = None
        for worker_id in range(schedule.workers):
            for nonce in schedule.worker_nonces(worker_id):
                evaluated += 1
                if evaluate(nonce):
                    winner = nonce
                    break
            if winner is not None:
                break
        return {
            "winner": winner,
            "evaluated": evaluated,
            "schedule": schedule.manifest(),
            "consensus_authority": "callback",
            "quantum_claim": False,
        }


# ---------------------------------------------------------------------------
# Hilbert coverage planning for the platform virtual quantum computer.

VIRTUAL_QUANTUM_QUBITS = 11
VIRTUAL_QUANTUM_DIMENSION = 1 << VIRTUAL_QUANTUM_QUBITS


@dataclass(frozen=True)
class HilbertCoveragePlan:
    n_qubits: int
    dimension: int
    bytes_per_amplitude: int
    state_bytes: int
    data_bytes: int
    total_bytes: int
    available_memory_bytes: Optional[int]
    fits: bool


def plan_hilbert_coverage(
    n_qubits: int = VIRTUAL_QUANTUM_QUBITS,
    *,
    available_memory_bytes: Optional[int] = None,
    data_bytes: int = 0,
    bytes_per_amplitude: int = 16,
) -> HilbertCoveragePlan:
    """Plan full-rank Hilbert coverage without truncation or hidden allocation.

    A complex128 amplitude consumes 16 bytes. ``data_bytes`` is an explicit
    reserve for the caller's payload/metadata and is counted separately from
    the state tensor. The plan is a proof obligation, not a promise to
    allocate memory.
    """
    if n_qubits < 1 or data_bytes < 0 or bytes_per_amplitude < 1:
        raise ValueError("invalid Hilbert coverage parameters")
    dimension = 1 << n_qubits
    state_bytes = dimension * bytes_per_amplitude
    total = state_bytes + data_bytes
    fits = available_memory_bytes is None or total <= available_memory_bytes
    return HilbertCoveragePlan(
        n_qubits,
        dimension,
        bytes_per_amplitude,
        state_bytes,
        data_bytes,
        total,
        available_memory_bytes,
        fits,
    )


class QuantumTensorManifest:
    """Control-plane contract of the canonical virtual quantum tensor.

    Production execution needs the tensor's scale manifest and coverage
    plan — pure closed-form quantities — not a materialised exact register
    (the register lives on the ``src.euclid``/``mtheory`` research surface).
    This value object carries exactly what the execution plane consumes:
    qubit-width validation, the ``qubit_gate`` scale manifest, and the
    Hilbert coverage plan.  It allocates no state memory.
    """

    def __init__(
        self,
        n_qubits: int = VIRTUAL_QUANTUM_QUBITS,
        *,
        require_platform_width: bool = False,
        scale_index: Optional[int] = None,
    ) -> None:
        if n_qubits < 1:
            raise ValueError("n_qubits must be positive")
        if require_platform_width and n_qubits != VIRTUAL_QUANTUM_QUBITS:
            raise ValueError(f"production virtual quantum width is {VIRTUAL_QUANTUM_QUBITS}")
        self.scale_index = scale_index
        self._n_qubits = int(n_qubits)
        self.operation_audit: list = []
        self.assert_invariants()

    @property
    def n_qubits(self) -> int:
        return self._n_qubits

    @property
    def dimension(self) -> int:
        return 1 << self._n_qubits

    def assert_invariants(self) -> bool:
        if self.dimension != 1 << self._n_qubits:
            raise ValueError("state dimension is not 2**n_qubits")
        return True

    def coverage(
        self,
        *,
        available_memory_bytes: Optional[int] = None,
        data_bytes: int = 0,
        bytes_per_amplitude: int = 16,
    ) -> HilbertCoveragePlan:
        return plan_hilbert_coverage(
            self._n_qubits,
            available_memory_bytes=available_memory_bytes,
            data_bytes=data_bytes,
            bytes_per_amplitude=bytes_per_amplitude,
        )

    def scale_manifest(self) -> dict:
        return {
            "default": resolve_scale("qubit_gate", self.scale_index).as_dict(),
            "operations": list(self.operation_audit),
        }


__all__ = [
    "SUPPORTED_SCALE_INDICES",
    "DOMAIN_SCALE_INDEX",
    "LucasPisotScale",
    "resolve_scale",
    "scaled_budget",
    "operation_record",
    "LUCAS_EXECUTION_SCALE_INDICES",
    "LucasScaleError",
    "require_lucas_execution_scale",
    "HendrixSchedule",
    "HendrixStructuredSearch",
    "VIRTUAL_QUANTUM_QUBITS",
    "VIRTUAL_QUANTUM_DIMENSION",
    "HilbertCoveragePlan",
    "plan_hilbert_coverage",
    "QuantumTensorManifest",
]
