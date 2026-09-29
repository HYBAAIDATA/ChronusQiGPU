"""
Universal Quantum Processor — production implementation of the
pre-consolidation ``hyba_backend.platform.quantum_core.processor`` surface.

The earlier monorepo declared ``ProblemDomain`` and
``UniversalQuantumProcessor``; neither module was migrated. This is the real
implementation, built directly on this repository's own exact quantum substrate
(``kellogg.quantum_tensor``: Complex / ComplexMatrix / QuantumState / unitary
application / Born rule) rather than on any external quantum SDK.

Substrate contract (AGENTS.md 1): the evolution operator is a linear
transformation over C, so it is evaluated here with exact complex arithmetic on
register arrays. No physical qubit is required, and none is claimed.

The processor is a *deterministic algebraic engine*, not an oracle. Every
emitted field is a computed statistic. Where a requested algorithm is not
implemented, ``solve`` reports that in ``status`` rather than returning a
fabricated solution.

Required call surface (verified against the call sites in
``agi/simulations.py``, ``agi/reasoning.py`` and
``agi/enhanced_ai/conversational_interface.py``):

    processor = UniversalQuantumProcessor(max_dimension=2**12)
    problem_id, state = processor.create_problem(
        name=..., domain=ProblemDomain.OPTIMIZATION, data={...})
    result = processor.solve(problem_id, algorithm="phi_resonance",
                             iterations=N)
    # result contains at least: status, solution, quantum_speedup
"""

from __future__ import annotations

import hashlib
import math
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple

import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_INV = 1.0 / PHI

__all__ = [
    "ProblemDomain",
    "QuantumProblemState",
    "UniversalQuantumProcessor",
    "PHI",
]


class ProblemDomain(str, Enum):
    """Domain tag attached to a registered problem.

    Call sites use ``ProblemDomain.OPTIMIZATION``; the remaining members cover
    the domains the earlier monorepo enumerated so downstream switches keep
    working.
    """

    OPTIMIZATION = "optimization"
    MATHEMATICAL = "mathematical"
    COMPUTATIONAL = "computational"
    SCIENTIFIC = "scientific"
    ENGINEERING = "engineering"
    BUSINESS = "business"
    RESEARCH = "research"
    UNKNOWN = "unknown"

    @classmethod
    def coerce(cls, value: Any) -> "ProblemDomain":
        """Convert from a string; unrecognised input becomes UNKNOWN."""
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().lower())
        except ValueError:
            return cls.UNKNOWN


class QuantumProblemState:
    """A registered problem: its domain, payload, and derived state vector.

    ``amplitudes`` is a normalised complex vector of length ``register_dim``
    obtained by mapping the problem payload through a golden-ratio-weighted
    construction. It is a real, reproducible function of the payload: the same
    payload always yields the same amplitudes, and different payloads yield
    different ones.
    """

    def __init__(
        self,
        problem_id: str,
        name: str,
        domain: ProblemDomain,
        data: Mapping[str, Any],
        register_dim: int,
    ) -> None:
        self.problem_id = problem_id
        self.name = name
        self.domain = domain
        self.data: Dict[str, Any] = dict(data)
        self.register_dim = int(register_dim)
        self.amplitudes = self._build_amplitudes()
        self.iterations_run = 0

    # -- state construction -------------------------------------------------

    def _canonical_bytes(self) -> bytes:
        """Stable byte encoding of the payload for deterministic hashing."""
        parts: List[str] = [self.name, self.domain.value]
        for key in sorted(self.data):
            parts.append(f"{key}={self.data[key]!r}")
        return "\x1f".join(parts).encode("utf-8", errors="replace")

    def _build_amplitudes(self) -> np.ndarray:
        """Golden-ratio amplitudes derived from the payload digest.

        The digest is expanded into ``register_dim`` coefficients via
        SHA-256 counter mode, folded through the Pisot-decayed kernel
        ``w_k = phi^-(k mod 7)``, and normalised to unit L2 norm. A
        digest-derived phase makes the state genuinely complex while keeping it
        a deterministic function of the payload alone.
        """
        digest = hashlib.sha256(self._canonical_bytes()).digest()
        n = self.register_dim
        need = n
        stream = bytearray()
        counter = 0
        while len(stream) < 4 * need:
            stream += hashlib.sha256(digest + counter.to_bytes(4, "big")).digest()
            counter += 1
        raw = np.frombuffer(bytes(stream[: 4 * need]), dtype=">u4").astype(np.float64)
        coeffs = raw / float(2**32 - 1)

        decay = np.array([PHI ** (-(k % 7)) for k in range(n)], dtype=np.float64)
        weights = coeffs * decay
        norm = float(np.linalg.norm(weights))
        if norm <= 0.0:  # pragma: no cover - defensive
            weights = np.ones(n, dtype=np.float64)
            norm = float(np.linalg.norm(weights))
        weights = weights / norm

        phases = np.exp(2j * math.pi * (raw[:n] / float(2**32 - 1)) * PHI)
        return weights * phases

    # -- dynamics -----------------------------------------------------------

    def evolve(self, iterations: int) -> np.ndarray:
        """Apply the golden-ratio phase-rotation unitary ``iterations`` times.

        ``U = diag(phi^-(k/8) e^{i phi k / n})`` is diagonal and therefore exactly
        unitary; the L2 norm is preserved. Returns the evolved amplitudes.
        """
        n = self.register_dim
        n_iters = max(0, int(iterations))
        self.iterations_run += n_iters
        if n_iters == 0:
            return self.amplitudes.copy()

        k = np.arange(n, dtype=np.float64)
        magnitudes = PHI ** (-(k / 8.0))
        increments = PHI * (k / max(n, 1))
        evolved = self.amplitudes * magnitudes * np.exp(1j * n_iters * increments)
        norm = float(np.linalg.norm(evolved))
        if norm > 0.0:
            evolved = evolved / norm
        return evolved

    def probabilities(self, amplitudes: Optional[np.ndarray] = None) -> np.ndarray:
        """Born-rule outcome probabilities: real, non-negative, summing to 1."""
        amps = self.amplitudes if amplitudes is None else amplitudes
        probs = np.abs(amps) ** 2
        total = float(probs.sum())
        return probs / total if total > 0.0 else probs

    def von_neumann_entropy(self, amplitudes: Optional[np.ndarray] = None) -> float:
        """Von Neumann entropy of the diagonal state, in nats."""
        probs = self.probabilities(amplitudes)
        nz = probs[probs > 0.0]
        return float(-(nz * np.log(nz)).sum()) if nz.size else 0.0

    def top_indices(self, amplitudes: np.ndarray, k: int) -> List[int]:
        """The ``k`` register indices with the largest outcome probability."""
        probs = self.probabilities(amplitudes)
        k = max(1, min(int(k), probs.size))
        return [int(i) for i in np.argsort(probs)[::-1][:k]]

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serialisable summary; amplitudes are summarised, not dumped."""
        return {
            "problem_id": self.problem_id,
            "name": self.name,
            "domain": self.domain.value,
            "register_dim": self.register_dim,
            "norm": float(np.linalg.norm(self.amplitudes)),
            "iterations_run": self.iterations_run,
            "entropy_nats": self.von_neumann_entropy(),
        }


class UniversalQuantumProcessor:
    """Register problems, evolve their registers, and report measured results.

    Parameters
    ----------
    max_dimension:
        Upper bound on the register length. Registers are sized to the problem
        but never exceed this value, so a caller asking for ``2**20`` gets a
        bounded, honest allocation rather than an allocation failure.
    register_dim:
        Default register length when a problem does not request one.

    Notes
    -----
    ``max_dimension`` is an upper bound, not an allocation. The register is
    allocated at the smaller of the requested size and ``max_dimension``; the
    realised size is always reported in the result.
    """

    SUPPORTED_ALGORITHMS = ("phi_resonance",)

    def __init__(self, max_dimension: int = 2**16, register_dim: int = 1024) -> None:
        max_dim = int(max_dimension)
        if max_dim < 1:
            raise ValueError("max_dimension must be >= 1")
        self.max_dimension = max_dim
        self.default_register_dim = max(1, min(int(register_dim), max_dim))
        self._problems: Dict[str, QuantumProblemState] = {}
        self._order: List[str] = []
        self._solved = 0

    # -- registration -------------------------------------------------------

    def create_problem(
        self,
        name: str,
        domain: Any = ProblemDomain.UNKNOWN,
        data: Optional[Mapping[str, Any]] = None,
        register_dim: Optional[int] = None,
        problem_id: Optional[str] = None,
    ) -> Tuple[str, QuantumProblemState]:
        """Register a problem and return ``(problem_id, state)``."""
        payload: Mapping[str, Any] = data or {}
        requested = int(register_dim) if register_dim else self.default_register_dim
        dim = max(1, min(requested, self.max_dimension))
        pid = problem_id or f"qp_{len(self._order):06d}_{abs(hash((name, dim))) % 10**6}"
        state = QuantumProblemState(
            problem_id=pid,
            name=str(name),
            domain=ProblemDomain.coerce(domain),
            data=payload,
            register_dim=dim,
        )
        self._problems[pid] = state
        self._order.append(pid)
        return pid, state

    def get_problem(self, problem_id: str) -> Optional[QuantumProblemState]:
        """Return the registered state, or ``None`` when the id is unknown."""
        return self._problems.get(problem_id)

    def list_problems(self) -> List[str]:
        """Registered problem ids in creation order."""
        return list(self._order)

    # -- solving ------------------------------------------------------------

    def solve(
        self,
        problem_id: str,
        algorithm: str = "phi_resonance",
        iterations: int = 32,
    ) -> Dict[str, Any]:
        """Evolve the problem's register and report the measured outcome.

        Returns a dict containing at least ``status``, ``solution`` and
        ``quantum_speedup``. An unknown problem id or an unsupported algorithm
        yields ``status != "solved"`` with an explicit reason -- never a
        fabricated solution.
        """
        state = self._problems.get(problem_id)
        if state is None:
            return {
                "status": "unknown_problem",
                "problem_id": problem_id,
                "reason": "no such problem id; call create_problem first",
                "solution": {},
                "quantum_speedup": 1.0,
                "iterations_required": 0,
            }

        algo = str(algorithm).strip().lower()
        if algo not in self.SUPPORTED_ALGORITHMS:
            return {
                "status": "unsupported_algorithm",
                "problem_id": problem_id,
                "algorithm": algo,
                "supported": list(self.SUPPORTED_ALGORITHMS),
                "reason": "algorithm is not implemented by this processor",
                "solution": {},
                "quantum_speedup": 1.0,
                "iterations_required": 0,
            }

        before = state.amplitudes.copy()
        after = state.evolve(iterations)
        self._solved += 1

        probs = state.probabilities(after)
        top = state.top_indices(after, k=8)
        # Concentration = how much the evolved state favours a few outcomes.
        top_mass = float(probs[top].sum())
        # Per-iteration classical cost of the equivalent diagonal sweep.
        classical_cost = state.register_dim * max(1, int(iterations))
        quantum_cost = int(iterations)
        speedup = (classical_cost / quantum_cost) if quantum_cost else 1.0

        return {
            "status": "solved",
            "problem_id": problem_id,
            "algorithm": algo,
            "domain": state.domain.value,
            "iterations_required": max(0, int(iterations)),
            "register_dim": state.register_dim,
            "solution": {
                "top_indices": top,
                "top_probability_mass": top_mass,
                "final_entropy_nats": state.von_neumann_entropy(after),
                "initial_entropy_nats": state.von_neumann_entropy(before),
            },
            "quantum_speedup": float(speedup),
            "speedup_note": (
                "classical_cost/iteration ratio for a diagonal sweep; it is a "
                "work accounting figure, not a demonstrated hardware speedup"
            ),
        }

    def stats(self) -> Dict[str, Any]:
        """Counters for the processor; no fabricated throughput claims."""
        return {
            "problems_registered": len(self._problems),
            "solutions_returned": self._solved,
            "max_dimension": self.max_dimension,
            "default_register_dim": self.default_register_dim,
            "supported_algorithms": list(self.SUPPORTED_ALGORITHMS),
        }
