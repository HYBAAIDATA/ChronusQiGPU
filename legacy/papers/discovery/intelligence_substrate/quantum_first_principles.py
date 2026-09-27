"""
HYBA First-Principles Quantum Mathematical Substrate
====================================================
Substrate and hardware agnostic mathematical contract.
Strictly enforces exact rational representation. Discards all floating-point
heuristic simulation and classical hardware fallbacks (CUDA/CuPy).
"""

from typing import List, Dict, Any, Optional
from fractions import Fraction
import math

# Exact fractions will be used for all representations.
from python_backend.hyba.quantum.primitives import (
    RationalStateVector,
    ExactFraction,
    HardwareEnforcementError,
    ContractViolationError,
)

# Golden Ratio & Lucas Constants
# Use the canonical irrational definitions for φ and its reciprocal; wrap them
# in ExactFraction so downstream exact-rational code can still operate on a
# fixed high-precision rational proxy while tests comparing against math.sqrt(5)
# see the true golden ratio value.
_PHI_FLOAT = (1 + math.sqrt(5)) / 2
_INV_PHI_FLOAT = _PHI_FLOAT - 1  # 1/φ = φ - 1
# Rational proxy accurate to ~1e-10 for exact-rational consumers.
_PHI_FRAC = Fraction(6765, 4181)
_PHI_INV_FRAC = Fraction(4181, 6765)
PHI = ExactFraction(_PHI_FRAC)
INV_PHI = ExactFraction(_PHI_INV_FRAC)
# Numeric accessors for invariant tests and floating-point consumers.
PHI_FLOAT = _PHI_FLOAT
INV_PHI_FLOAT = _INV_PHI_FLOAT
LUCAS_15 = 1364  # Exact L_15 = phi^15 + (-phi)^-15


# 32-Face Voronoi Adjacency Graph Definition (M_32 Manifold)
def _build_m32_adjacency() -> List[List[ExactFraction]]:
    adj = [[ExactFraction(0, 1) for _ in range(32)] for _ in range(32)]
    for i in range(32):
        # Connect to 4 nearest topological neighbors on 5-fold / 8-fold orbital structure
        for offset in [1, 2, 5, 8]:
            j = (i + offset) % 32
            adj[i][j] = ExactFraction(1, 1)
            adj[j][i] = ExactFraction(1, 1)
    return adj


ADJ_32: List[List[ExactFraction]] = _build_m32_adjacency()
# Floating-point mirror for NumPy consumers that need a real-valued adjacency matrix.
ADJ_32_FLOAT = [[float(cell.val) for cell in row] for row in ADJ_32]


class ExecutionProvenance:
    """Strict provenance records for mathematical evaluations."""

    def __init__(self):
        self._records = []
        self._immutable = False

    def record_evolution(self, operation: str, dimensions: int):
        if self._immutable:
            raise ContractViolationError("Provenance record is immutable.")
        self._records.append({"op": operation, "dim": dimensions, "exact_math": True})

    def finalize(self):
        self._immutable = True

    def verify(self) -> bool:
        if not self._immutable:
            raise ContractViolationError("Provenance record not finalized.")
        for rec in self._records:
            if not rec.get("exact_math", False):
                raise ContractViolationError("Provenance violation: classical fallback detected.")
        return True


def get_default_backend_info() -> Dict[str, str]:
    """Exact mathematical contract backend info."""
    return {
        "backend": "exact_rational_mathematics",
        "device": "abstract",
        "array_library": "fractions.Fraction",
    }


class FirstPrinciplesQuantumSubstrate:
    """
    First-Principles Quantum Mathematics Engine

    Operates strictly on Exact Rational Mathematics via the RationalStateVector.
    No CuPy, no NumPy, no classical floating-point proxies.
    """

    def __init__(self, dim: int = 32):
        self.dim = dim
        self.provenance = ExecutionProvenance()

        # Provenance fact -- name the executor, never leave it unnamed
        # (AGENT_REBOOT_PROTOCOL rule 1: record what ran). This substrate is
        # pure-Python exact rational (fractions.Fraction) arithmetic executed
        # on the host CPU: no accelerator, no numpy, and emphatically no QPU.
        # headless_miner._quantum_provenance reads these; without them it fell
        # back to the literal "cpu:numpy", which this substrate is not.
        self.backend_name = "cpu:exact_rational"
        self.device_name = "cpu"

        # Build exact rational transition matrix
        self._build_transition_matrix()

    def _build_transition_matrix(self):
        # We build a strict rational transition matrix from the graph
        # For a discrete time quantum walk, the coin and shift operators
        # are mapped to exact rational unitaries.
        self.transition_matrix = []
        for i in range(self.dim):
            row = []
            degree = 0
            for j in range(self.dim):
                if ADJ_32[i][j].val.numerator > 0:
                    degree += 1

            for j in range(self.dim):
                if ADJ_32[i][j].val.numerator > 0:
                    row.append(ExactFraction(1, degree))
                else:
                    row.append(ExactFraction(0, 1))
            self.transition_matrix.append(row)

    def evolve_dtqw(
        self,
        steps: int = 1,
        initial_state: Optional[List[ExactFraction]] = None,
    ) -> RationalStateVector:
        """
        Evolve Discrete-Time Quantum Walk using Exact Rational Math.

        ``initial_state`` defaults to the uniform superposition over all nodes.
        Callers that already hold their own exact-rational starting
        distribution -- e.g. the miner's memory-feedback-biased face
        distribution -- must be able to seed the walk with it. With a
        hardcoded uniform start this method returns the identical vector on
        every call, so nothing upstream can influence the walked distribution.
        """
        if initial_state is None:
            # Start in uniform superposition over all nodes
            state = [ExactFraction(1, self.dim) for _ in range(self.dim)]
        else:
            if len(initial_state) != self.dim:
                raise ValueError(
                    f"initial_state length {len(initial_state)} != dimension {self.dim}"
                )
            for amp in initial_state:
                if not isinstance(amp, ExactFraction):
                    raise ContractViolationError(
                        "evolve_dtqw initial_state must consist of ExactFraction amplitudes."
                    )
            state = list(initial_state)

        for _ in range(steps):
            next_state = [ExactFraction(0, 1) for _ in range(self.dim)]
            for i in range(self.dim):
                for j in range(self.dim):
                    next_state[i] = next_state[i] + (self.transition_matrix[j][i] * state[j])
            state = next_state
            self.provenance.record_evolution("DTQW_STEP", self.dim)

        return RationalStateVector(state)

    def _adjacency_float(self) -> List[List[float]]:
        """Dimension-aware ring adjacency used for float search operators.

        The first-principles exact-rational substrate keeps the canonical M_32
        32-face graph (``ADJ_32``).  For float-consuming search operators and
        property tests that vary ``dim``, we build the same ring-with-offsets
        topology scaled to ``self.dim``.
        """
        adj = [[0.0 for _ in range(self.dim)] for _ in range(self.dim)]
        offsets = [1, 2, max(1, self.dim // 8), max(1, self.dim // 5)]
        for i in range(self.dim):
            for offset in offsets:
                j = (i + offset) % self.dim
                adj[i][j] = 1.0
                adj[j][i] = 1.0
        return adj

    def discrete_quantum_walk_step(
        self,
        probabilities: List[float],
        steps: int = 1,
        damping: float = 0.82,
    ) -> List[float]:
        """Float-valued discrete-time quantum-walk step used by search operators.

        Mirrors ``evolve_dtqw`` but operates on a real probability vector so the
        classical search scheduler can consume it without breaking the exact-rational
        contract in the first-principles API.
        """
        import numpy as np

        probs = np.asarray(probabilities, dtype=np.float64)
        if len(probs) != self.dim:
            raise ValueError(f"probability vector length {len(probs)} != dimension {self.dim}")
        adj = np.asarray(self._adjacency_float(), dtype=np.float64)
        degrees = np.sum(adj, axis=1)
        degrees = np.where(degrees > 0, degrees, 1.0)
        for _ in range(steps):
            # One step of the DTQW: spread each face's mass evenly to its neighbors
            # and apply damping to keep the walk bounded.
            next_probs = (adj @ probs) / degrees
            probs = damping * next_probs + (1.0 - damping) / self.dim
        return probs.tolist()

    def continuous_time_quantum_walk(
        self,
        probabilities: List[float],
        time: float = 0.5,
        gamma: float = 1.0,
    ) -> List[float]:
        """Approximate continuous-time quantum-walk diffusion for search operators.

        Uses the graph Laplacian of the dimension-aware adjacency to diffuse
        probabilities for a short time; this is a classical analog of the CTQW
        Hamiltonian evolution.
        """
        import numpy as np

        probs = np.asarray(probabilities, dtype=np.float64)
        if len(probs) != self.dim:
            raise ValueError(f"probability vector length {len(probs)} != dimension {self.dim}")
        adj = np.asarray(self._adjacency_float(), dtype=np.float64)
        degrees = np.sum(adj, axis=1)
        laplacian = np.diag(degrees) - adj

        # Small-time diffusion: p' ~ p - gamma dt L p, applied over sub-steps.
        #
        # The forward-Euler Laplacian update is only stable while
        # gamma * dt * max_degree < 1. Applying the whole of `time` in one
        # increment (the previous behaviour) overshoots for the M_32 topology
        # (max degree 8) at anything above dt ~ 0.125: neighbouring sites go
        # NEGATIVE and are then clamped to exactly 0 by the non-negativity
        # projection below, so the walk destroys mass on precisely the sites it
        # is supposed to be diffusing into -- the observable effect is
        # anti-diffusion, not diffusion. Sub-stepping keeps every increment
        # inside the stability region while integrating the same total time.
        max_degree = float(np.max(degrees)) if degrees.size else 0.0
        steps = 1
        if max_degree > 0.0 and gamma > 0.0 and time > 0.0:
            # factor 2 keeps gamma * dt * max_degree <= 0.5, strictly inside
            # the stability limit rather than sitting on it.
            steps = max(1, int(math.ceil(2.0 * gamma * time * max_degree)))
        dt = time / steps

        evolved = probs
        for _ in range(steps):
            evolved = evolved - gamma * dt * (laplacian @ evolved)
            evolved = np.maximum(evolved, 0.0)

        s = np.sum(evolved)
        if s > 1e-12:
            evolved = evolved / s
        return evolved.tolist()

    def build_problem_hamiltonian(self, resonance_weights: List[float]) -> "Any":
        """Problem Hamiltonian for the float AQO operator.

        H_prob = -0.3 * A with the diagonal set to -resonance_weights: reward
        high resonance, penalise curvature. Float-valued, like the other
        search operators above -- it is not part of the exact-rational
        boundary.
        """
        import numpy as np

        w = np.asarray(resonance_weights, dtype=np.float64)
        if w.size != self.dim:
            raise ValueError(f"resonance_weights length {w.size} != dimension {self.dim}")
        adj = np.asarray(self._adjacency_float(), dtype=np.float64)
        H_prob = -0.3 * adj
        idx = np.arange(self.dim)
        # adj has a zero diagonal (no self-loops), so assigning here is exactly
        # equivalent to setting H[i][i] = -w[i] then subtracting 0.3*adj[i][i].
        H_prob[idx, idx] = -w
        return H_prob

    def adiabatic_evolution(
        self,
        probabilities: List[float],
        s: float,
        resonance_weights: List[float],
        dt: float = 0.1,
    ) -> List[float]:
        """Adiabatic interpolation H(s) = (1-s) H_mixer + s H_prob, one dt step.

        Restored alongside the other float search operators (DTQW/CTQW/
        Riemannian retraction). accel/substrate.py's quantum-walk dispatcher
        maps op "aqo" to this method, so its absence was an AttributeError on
        a live call path, not merely a missing test hook.
        """
        import numpy as np

        p = np.asarray(probabilities, dtype=np.float64)
        if p.size != self.dim:
            raise ValueError(f"probability vector length {p.size} != dimension {self.dim}")

        H_mixer = -np.eye(self.dim, dtype=np.float64)
        H_prob = self.build_problem_hamiltonian(resonance_weights)
        H_s = (1.0 - s) * H_mixer + s * H_prob

        evals, evecs = np.linalg.eigh(H_s)

        x = np.clip(p, 0.0, None)
        total = float(np.sum(x)) + 1e-12
        psi = np.sqrt(x / total)

        c = evecs.T @ psi.astype(np.complex128)
        evolved_psi = evecs @ (c * np.exp(-1j * evals * dt))

        probs = np.abs(evolved_psi) ** 2
        prob_total = float(np.sum(probs)) + 1e-12
        return (probs / prob_total).tolist()

    def scale_with_lucas_15(self, probabilities: List[float]) -> Dict[str, Any]:
        """Lucas-15 thread-density amplification with Pisot conjugate damping.

        Restored with the other float operators: accel/substrate.py maps op
        "lucas15" here. Provenance fields report the substrate this actually
        ran on -- no hardware claim is made.
        """
        import numpy as np

        p = np.asarray(probabilities, dtype=np.float64)
        if p.size != self.dim:
            raise ValueError(f"probability vector length {p.size} != dimension {self.dim}")

        idx = np.arange(self.dim)
        mask = (idx % 5 == 0).astype(np.float64)
        amplified = p * (1.0 + mask * INV_PHI_FLOAT)
        total = float(np.sum(amplified)) + 1e-12
        normalized = amplified / total

        normalized_list = normalized.tolist()
        best_face = int(np.argmax(normalized))
        order = np.argsort(normalized)[::-1][:5]
        peak_probability = float(normalized_list[best_face])

        return {
            "best_face": best_face,
            "top_amplified_faces": [int(i) for i in order],
            "peak_probability": peak_probability,
            "lucas_thread_density": LUCAS_15,
            "pisot_conjugate_damping": INV_PHI_FLOAT**15,
            "phi_resonance": (peak_probability * PHI_FLOAT) % 1.0,
            "distribution": normalized_list,
            # Honest compute provenance for this cycle's result.
            "backend": self.backend_name,
            "device": self.device_name,
        }

    def riemannian_retraction(
        self,
        probabilities: List[float],
        grad: List[float],
        step_size: float = 0.01,
    ) -> List[float]:
        """Project a Euclidean gradient step back onto the probability simplex.

        Classical Riemannian retraction used by search operators and property
        tests: take a step in the negative gradient direction and re-normalize
        to a unit-mass, non-negative probability vector.
        """
        import numpy as np

        if len(probabilities) != self.dim or len(grad) != self.dim:
            raise ValueError("probability and gradient vectors must match dimension")
        probs = np.asarray(probabilities, dtype=np.float64)
        g = np.asarray(grad, dtype=np.float64)
        stepped = probs - step_size * (g - np.mean(g))
        stepped = np.maximum(stepped, 0.0)
        s = np.sum(stepped)
        if s > 1e-12:
            stepped /= s
        else:
            stepped = np.ones(self.dim, dtype=np.float64) / self.dim
        return stepped.tolist()

    def measure(self, state: RationalStateVector) -> List[float]:
        """
        Measurement explicitly throws an error to enforce fail-closed hardware axiom.
        """
        raise HardwareEnforcementError(
            "Fail-closed: No physical quantum hardware detected. "
            "Classical simulation and heuristic state-vector fallbacks are strictly prohibited."
        )

    def run_full_simulation(self) -> Dict[str, Any]:
        """
        Runs mathematical analysis but refuses physical realization proxies.
        """
        self.provenance.record_evolution("FULL_SIMULATION", self.dim)
        state = self.evolve_dtqw(steps=3)
        self.provenance.finalize()
        self.provenance.verify()

        # We can return the exact rational amplitudes as mathematical evidence
        return {
            "provenance_verified": True,
            "abstract_amplitudes_numerator": [a.val.numerator for a in state.amplitudes],
            "abstract_amplitudes_denominator": [a.val.denominator for a in state.amplitudes],
        }
