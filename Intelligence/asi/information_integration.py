# pythagoras/asi/information_integration.py — NEW

import math
from dataclasses import dataclass, field
from itertools import combinations
from typing import Optional, Sequence

import numpy as np

from . import manifold_bridge as mb


@dataclass
class ManifoldPhiResult:
    """Dual-mode result of a manifold MIP measurement.

    `phi` is the minimum-information-partition integrated information in
    nats; `partition` is the bipartition that attained it; `state` carries
    the measured manifold/covariance payload for downstream consumers.
    """

    phi: float
    partition: Optional[tuple]
    method: str
    state: np.ndarray
    n_sites: int
    partitions_evaluated: int = 0
    subsystem_phi: dict = field(default_factory=dict)

    @property
    def phi_scalar(self) -> float:
        """Scalar projection for backward compatibility with 1-D callers."""
        return float(self.phi)

    def to_scalar(self) -> float:
        return float(self.phi)


class InformationIntegrationMeasurer:
    """Measures integrated information (Φ) across PYTHAGORAS subsystems.

    Φ = Total information of system - Sum of information of independent parts
    High Φ = the system is more than the sum of its parts.

    Manifold mode: a genuine bipartite Minimum Information Partition over
    the D-dimensional Poincaré state or a supplied covariance/density
    matrix, Φ = min_{A,B} D(rho || rho_A (x) rho_B).  The divergence D is
    the relative entropy: Gaussian relative entropy for covariance inputs
    (Barrett & Seth 2011 — the standard integrated-information measure for
    continuous linear systems) and quantum relative entropy for density
    matrices (exact partial trace + von Neumann entropy).  Both are chosen
    because they are the canonical D for the respective state space and
    reduce to mutual information, which vanishes exactly on product states.
    """

    def __init__(self, subsystems: dict[str, callable]):
        self.subsystems = subsystems
        self.last_manifold_result: Optional[ManifoldPhiResult] = None

    def measure_phi(self, inputs: list) -> dict:
        """Compute integrated information for a given input."""
        # Total system information
        total_output = self._run_full_system(inputs)
        total_info = self._entropy(total_output)

        # Sum of independent part information
        parts_info = 0.0
        for name, fn in self.subsystems.items():
            part_output = fn(inputs)
            parts_info += self._entropy(part_output)

        phi = total_info - parts_info

        return {
            "total_system_information": round(total_info, 4),
            "sum_of_parts_information": round(parts_info, 4),
            "integrated_information_phi": round(phi, 4),
            "integration_ratio": round(total_info / max(parts_info, 1e-10), 4),
            "is_integrated": phi > 0,
        }

    def _run_full_system(self, inputs):
        outputs = []
        for fn in self.subsystems.values():
            out = fn(inputs)
            outputs.extend(out if isinstance(out, list) else [out])
        return outputs

    def _entropy(self, values: list) -> float:
        if not values:
            return 0.0
        from collections import Counter

        counts = Counter(values)
        total = len(values)
        return -sum((c / total) * math.log2(c / total) for c in counts.values())

    def find_minimum_information_partition(self, inputs: list) -> dict:
        """Find the bipartition that minimises integrated information."""
        names = list(self.subsystems.keys())
        min_phi = float("inf")
        best_partition = None

        for i in range(1, len(names)):
            for combo in combinations(names, i):
                part_a = {n: self.subsystems[n] for n in combo}
                part_b = {n: self.subsystems[n] for n in names if n not in combo}
                info_a = sum(self._entropy(fn(inputs)) for fn in part_a.values())
                info_b = sum(self._entropy(fn(inputs)) for fn in part_b.values())
                total = self._entropy(self._run_full_system(inputs))
                phi = total - info_a - info_b
                if phi < min_phi:
                    min_phi = phi
                    best_partition = (list(combo), [n for n in names if n not in combo])

        return {"minimum_phi": round(min_phi, 4), "partition": best_partition}

    # ------------------------------------------------------------------
    # Manifold operators (S-3 elevation): genuine bipartite MIP over
    # the 11-D Poincaré-Golden state or an explicit covariance/density.
    # ------------------------------------------------------------------

    def measure_phi_manifold(
        self, state: np.ndarray, regularization: float = 1e-9
    ) -> ManifoldPhiResult:
        """Φ of an 11-D Poincaré state via Gaussian relative entropy.

        The state's golden-geometry covariance (bridge.state_to_covariance)
        supplies the joint second-moment structure; Φ is the minimum over
        all 2^{10}-1 coordinate bipartitions of the Gaussian mutual
        information I(A;B) = D_KL(joint || product of marginals).
        """
        ball = mb.as_ball_vector(state)
        cov = mb.state_to_covariance(ball, regularization=regularization)
        return self.measure_phi_covariance(cov)

    def measure_phi_covariance(self, cov: np.ndarray) -> ManifoldPhiResult:
        """MIP over coordinate bipartitions of a covariance matrix.

        Φ = min_{A,B} 1/2 ln( det Σ_AA det Σ_BB / det Σ )
        Exact for Gaussian statistics; zero on product (block-diagonal) states.
        """
        cov = np.asarray(cov, dtype=np.float64)
        n = cov.shape[0]
        best_phi = float("inf")
        best_partition = None
        evaluated = 0
        for a, b in mb.iter_bipartitions(n):
            mi = mb.gaussian_mutual_information(cov, a, b)
            evaluated += 1
            if mi < best_phi:
                best_phi = mi
                best_partition = (a, b)
        result = ManifoldPhiResult(
            phi=float(best_phi),
            partition=best_partition,
            method="gaussian_relative_entropy",
            state=cov,
            n_sites=n,
            partitions_evaluated=evaluated,
        )
        self.last_manifold_result = result
        return result

    def measure_phi_density(self, rho: np.ndarray, site_dims: Sequence[int]) -> ManifoldPhiResult:
        """MIP over site bipartitions of a multipartite density matrix.

        Φ = min_{A,B} D(ρ || ρ_A ⊗ ρ_B)
          = min_{A,B} S(ρ_A) + S(ρ_B) - S(ρ)
        with quantum relative entropy as D — exact partial trace and
        von Neumann entropy, no approximation.  Zero on product states,
        positive on entangled or classically correlated states.
        """
        rho = np.asarray(rho, dtype=np.complex128)
        site_dims = [int(d) for d in site_dims]
        n = len(site_dims)
        best_phi = float("inf")
        best_partition = None
        evaluated = 0
        for a, _b in mb.iter_bipartitions(n):
            mi = mb.mutual_information_density(rho, site_dims, a)
            evaluated += 1
            if mi < best_phi:
                best_phi = mi
                best_partition = (a, tuple(i for i in range(n) if i not in a))
        result = ManifoldPhiResult(
            phi=float(best_phi),
            partition=best_partition,
            method="quantum_relative_entropy",
            state=rho,
            n_sites=n,
            partitions_evaluated=evaluated,
        )
        self.last_manifold_result = result
        return result

    @property
    def phi_scalar(self) -> float:
        """Scalar projection of the most recent manifold measurement."""
        if self.last_manifold_result is None:
            return 0.0
        return self.last_manifold_result.phi_scalar
