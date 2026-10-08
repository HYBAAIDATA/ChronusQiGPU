# evolution_engine.py
# Chronos GPU -- Evolution Engine v2.0 (audit fix, 3 Aug 2026)
#
# Fixes vs the original v1.0 (both the top-level evolution_engine.py, which
# said outright "# Synthetic final state for now", and src/chronos's own
# stub, which just returned np.random.randn(32) with no Hamiltonian input at
# all):
#   - Both prior versions returned a value with no relationship to the
#     Hamiltonian, so "energy" was meaningless and non-deterministic.
#   - v2.0 computes the EXACT ground state of the supplied Hamiltonian via
#     dense eigendecomposition. This is tractable and exact because n
#     (number of manifold faces) is small (tens to a few hundred) -- there is
#     no need for a heuristic variational loop at this scale.
#   - loss_curve is now a real, seeded power-iteration convergence trace
#     toward that exact ground state, not a placeholder list of zeros.
#   - Does NOT vendor the real quantum/variational.py QAOAOptimizer or
#     quantum/deep_variational.py classes from HYBA_Pythia_Prod (their
#     internal APIs were not reproduced here). See AUDIT_NOTES.md.
#   - v2.1 (PR #140): the ground state is now CERTIFIED exact via
#     igpu.exact_dense.certified_dense_ground_state -- the FP64 eigendecompo-
#     sition only proposes an eigenpair; exact rational arithmetic issues a
#     Weinstein residual interval plus a Sylvester-inertia isolation count
#     proving it contains exactly the ground eigenvalue. Degenerate or
#     unverifiable inputs fail closed (ArithmeticError); there is no silent
#     numerical fallback. `parameters` is now empty: this pipeline has no
#     variational parameters (previously it returned meaningless rng noise).

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np


@dataclass
class RenderResult:
    final_state: np.ndarray
    distribution: np.ndarray
    energy: float
    parameters: np.ndarray
    loss_curve: List[float]
    expectation_values: Dict[str, float]


class EvolutionEngine:
    def __init__(self, n_faces: int = 32, layers: int = 4, adjacency: Optional[np.ndarray] = None):
        self.n = n_faces
        self.layers = layers
        self.adjacency = adjacency if adjacency is not None else np.eye(n_faces)

    def evolve(
        self,
        hamiltonian_terms: List[np.ndarray],
        resonance_weights: Optional[np.ndarray],
        steps: int = 60,
        seed: int = 0,
    ) -> RenderResult:
        objective = sum(hamiltonian_terms) if hamiltonian_terms else np.zeros((self.n, self.n))
        if resonance_weights is not None:
            objective = objective - np.diag(resonance_weights)
        objective = (objective + objective.T) / 2.0  # enforce Hermitian/symmetric

        # Certified exact ground state. FP64 eigh only proposes the
        # eigenpair; the certificate (Weinstein residual interval +
        # Sylvester-inertia isolation count) proves it is the ground state.
        # Raises ArithmeticError on degenerate/unverifiable inputs -- the
        # render pipeline fails closed rather than emit an uncertified state.
        # Local import: `igpu/__init__` transitively re-enters `engine`,
        # so a top-level import would create a circular-import failure.
        from .igpu.exact_dense import certified_dense_ground_state
        ground_state_vec, cert = certified_dense_ground_state(objective)
        ground_energy = float(cert["eigenvalue"])
        ground_state = ground_state_vec.astype(complex)
        peak = int(np.argmax(np.abs(ground_state)))
        if ground_state[peak].real < 0:
            ground_state = -ground_state  # deterministic global phase

        # No variational parameters exist in this pipeline; the field is
        # kept only for the RenderResult contract.
        theta = np.zeros((0,), dtype=float)

        eigvals = np.linalg.eigvalsh(objective)
        shift = float(np.max(np.abs(eigvals))) + 1.0
        shifted = shift * np.eye(self.n) - objective
        rng = np.random.default_rng(seed)
        v = rng.standard_normal(self.n)
        v = v / np.linalg.norm(v)
        loss_curve: List[float] = []
        for _ in range(steps):
            v = shifted @ v
            v = v / np.linalg.norm(v)
            loss_curve.append(float(v @ objective @ v))

        distribution = np.abs(ground_state) ** 2
        distribution = distribution / distribution.sum()
        # NOTE (audit fix): v1.0 used the raw Hamiltonian energy eigenvalue
        # (which can be, and here usually is, negative) directly as pixel
        # "intensity". Downstream tone-mapping clips negative brightness to
        # 0, so that conflation made every rendered pixel collapse to black.
        # Energy and rendering intensity are now reported separately:
        # `energy` keeps its real (possibly negative) physical value;
        # `intensity` is a neutral, non-negative exposure baseline, and
        # actual per-pixel brightness variation comes from the (always
        # non-negative) per-face `distribution` in reconstruction.py.
        expectations = {
            "energy": ground_energy,
            "energy_residual_bound": float(cert["residual_bound"]),
            "energy_gap_bound": float(cert["gap_bound"]),
            "intensity": 1.0,
            "depth": float(np.mean(distribution)),
            "normal": float(np.std(distribution)),
        }
        return RenderResult(
            final_state=ground_state,
            distribution=distribution,
            energy=ground_energy,
            parameters=theta,
            loss_curve=loss_curve,
            expectation_values=expectations,
        )
