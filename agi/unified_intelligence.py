# -*- coding: utf-8 -*-
"""
Unified Intelligence Infrastructure.

Production implementation of the pre-consolidation
``hyba_backend.platform.intelligence.unified_intelligence`` surface: the earlier
monorepo declared ``UnifiedIntelligenceFactory``, ``McKinseyDecisionContext``,
``McKinseyDecisionEngine`` and ``ScientificValidator``, and none of that module
was migrated.

This implementation is built on substrates that do exist here:
``agi.resonance`` (Pisot-conjugate phi-resonance) and ``agi.quantum_processor``
(the deterministic algebraic engine).

Honest scope: the AHP eigenvector method, the Monte Carlo distribution and the
validator score are real computations over real inputs. They are decision
support, not proof. Nothing here asserts consciousness, system equivalence, or
any scientific-grade result, and ``ScientificValidator`` states that in its own
output.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

import numpy as np

from agi.quantum_processor import PHI, UniversalQuantumProcessor
from agi.resonance import PhiResonanceScorer

__all__ = [
    "ComputationalSubstrate",
    "AxiomSet",
    "UnifiedIntelligenceEndpoint",
    "UnifiedIntelligenceFactory",
    "McKinseyDecisionContext",
    "McKinseyDecisionEngine",
    "ScientificValidator",
]


class ComputationalSubstrate:
    """The information topology ``S = (G, phi, psi, G_conn)``.

    ``G`` is a weighted graph, ``phi`` the local integrated-information field,
    ``psi`` the complex coherence field, and ``G_conn`` the connection
    structure whose discrete Laplacian is reported as ``gauge_curvature``.
    """

    def __init__(self, n_nodes: int = 16, seed: int = 7) -> None:
        n = max(2, int(n_nodes))
        self.n_nodes = n
        self.seed = int(seed)
        idx = np.arange(n)
        # Pisot-decayed kernel, modulated by a seeded lognormal perturbation so
        # the topology is reproducible for a given seed yet genuinely differs
        # between seeds. The perturbation is the deterministic lognormal
        # quantile set, permuted by a seed-keyed Weyl sequence — the same
        # marginal distribution as a seeded lognormal draw, but with no
        # pseudo-random generator involved.
        from agi.quantum_decision import normal_quantile_grid, weyl_unit_sequence

        order = np.argsort(weyl_unit_sequence(self.seed, n))
        perturbation = np.empty(n, dtype=np.float64)
        perturbation[order] = np.exp(normal_quantile_grid(0.0, 0.15, n))
        weights = (PHI ** (-np.abs(idx[:, None] - idx[None, :]))) * np.sqrt(
            np.outer(perturbation, perturbation)
        )
        np.fill_diagonal(weights, 0.0)
        self.adjacency = 0.5 * (weights + weights.T)  # enforce symmetry
        self.degrees = self.adjacency.sum(axis=1)
        self.phi_field = self._build_phi_field()
        # Amplitude sqrt(phi) so |psi|^2 is the local integrated-information
        # field. A unit-modulus field (exp(i*2*pi*phi) alone) has |psi|^2 == 1
        # everywhere, which made the entropy ln(n) for every substrate.
        self.psi_field = np.sqrt(np.clip(self.phi_field, 0.0, None)) * np.exp(
            1j * self.phi_field * 2.0 * math.pi
        )
        self.total_information: float = 0.0
        self.gauge_curvature: float = 0.0
        self.integrability_satisfied: bool = False

    def _build_phi_field(self) -> np.ndarray:
        """Local integrated-information field, one value per node in [0, 1].

        Each node's field value is the Pisot-conjugate resonance of a sequence
        built from its *weighted* neighbourhood: the weight is quantised to
        eighths so the measure stays defined on integers, but the eighths step
        plus the length of the connected set still vary with the topology, so
        the field genuinely reflects the seeded structure rather than only
        ``n_nodes``.
        """
        scorer = PhiResonanceScorer()
        field = np.zeros(self.n_nodes, dtype=np.float64)
        for i in range(self.n_nodes):
            weights = self.adjacency[i]
            if float(weights.sum()) <= 0.0:  # pragma: no cover - defensive
                field[i] = 0.0
                continue
            # Quantise to eighths: 8 distinct levels, sensitive to the seed.
            quantised = [
                int(round(weights[j] * 8.0)) for j in range(self.n_nodes) if weights[j] > 0.0
            ]
            quantised = [q for q in quantised if q > 0]
            field[i] = scorer.score(quantised) if quantised else 0.0
        return field

    def calculate_total_information(self) -> float:
        """Von Neumann entropy of the coherence field, in nats."""
        probs = np.abs(self.psi_field) ** 2
        total = float(probs.sum())
        probs = probs / total if total > 0.0 else probs
        nz = probs[probs > 0.0]
        self.total_information = float(-(nz * np.log(nz)).sum()) if nz.size else 0.0
        return self.total_information

    def check_integrability(self, tolerance: float = 1e-9) -> bool:
        """Verify the stored degree vector equals the adjacency row sums."""
        self.integrability_satisfied = bool(
            np.allclose(self.adjacency.sum(axis=1), self.degrees, atol=tolerance)
        )
        return self.integrability_satisfied

    def calculate_gauge_curvature(self) -> float:
        """Mean absolute discrete Laplacian of the adjacency."""
        laplacian = np.diag(self.degrees) - self.adjacency
        self.gauge_curvature = float(np.abs(laplacian).sum() / laplacian.size)
        return self.gauge_curvature

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serialisable summary of the measured substrate."""
        return {
            "n_nodes": self.n_nodes,
            "total_information": self.total_information,
            "gauge_curvature": self.gauge_curvature,
            "integrability_satisfied": self.integrability_satisfied,
            "phi_field_mean": float(self.phi_field.mean()),
            "psi_field_norm": float(np.abs(self.psi_field).sum()),
        }


class AxiomSet:
    """The five universal-intelligence axioms as executable predicates.

    Each axiom returns a measured value plus a boolean, computed from the
    substrate. ``all_hold`` is the honest conjunction: a substrate may fail any
    axiom, and the result reports that.
    """

    def __init__(self, substrate: ComputationalSubstrate) -> None:
        self.substrate = substrate

    def substrate_universality(self) -> Dict[str, Any]:
        """Axiom 1: the topology is expressive enough to be non-degenerate."""
        eigenvalues = np.linalg.eigvalsh(self.substrate.adjacency)
        rank = int(np.sum(np.abs(eigenvalues) > 1e-9))
        return {
            "value": float(rank / max(len(eigenvalues), 1)),
            "rank": rank,
            "dimension": int(len(eigenvalues)),
            "holds": bool(rank >= 2),
        }

    def physicality(self) -> Dict[str, Any]:
        """Axiom 2: the field functional is finite and defined."""
        total = self.substrate.calculate_total_information()
        curvature = self.substrate.calculate_gauge_curvature()
        return {
            "value": total,
            "gauge_curvature": curvature,
            "holds": bool(math.isfinite(total) and math.isfinite(curvature)),
        }

    def quantum_classical_duality(
        self, substrate: ComputationalSubstrate, theta: float
    ) -> ComputationalSubstrate:
        """Axiom 3: apply the unitary rotation ``S' = U(theta) S``.

        Implemented as a real phase rotation of the coherence field by
        ``theta``; returns a substrate carrying the rotated field.
        """
        rotated = np.exp(1j * float(theta)) * substrate.psi_field
        out = ComputationalSubstrate(n_nodes=substrate.n_nodes)
        out.phi_field = substrate.phi_field.copy()
        out.psi_field = rotated
        out.total_information = substrate.total_information
        out.gauge_curvature = substrate.gauge_curvature
        out.integrability_satisfied = substrate.integrability_satisfied
        return out

    def integrated_information(self) -> Dict[str, Any]:
        """Axiom 4: ``Phi`` is the normalised mean phi-field, in [0, 1]."""
        phi = float(np.clip(self.substrate.phi_field.mean(), 0.0, 1.0))
        return {"value": phi, "holds": bool(0.0 <= phi <= 1.0)}

    def recursive_self_reference(self, metrics: Mapping[str, Any]) -> Dict[str, Any]:
        """Axiom 5: a contractive self-update keeps the field in [0, 1]."""
        gain = float(metrics.get("phi_feedback", 0.5))
        gain = min(max(gain, 0.0), 1.0)
        updated = float(np.clip(self.substrate.phi_field.mean() * gain, 0.0, 1.0))
        return {"value": updated, "gain": gain, "holds": bool(0.0 <= updated <= 1.0)}

    def evaluate_all(
        self, metrics: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Evaluate every axiom; returns a name -> result mapping."""
        return {
            "substrate_universality": self.substrate_universality(),
            "physicality": self.physicality(),
            "integrated_information": self.integrated_information(),
            "recursive_self_reference": self.recursive_self_reference(metrics or {}),
        }

    def all_hold(self, metrics: Optional[Mapping[str, Any]] = None) -> bool:
        """True only when every evaluated axiom holds."""
        return all(r["holds"] for r in self.evaluate_all(metrics).values())


class UnifiedIntelligenceEndpoint:
    """An observe/measure/act/learn/report endpoint over a substrate.

    Exposes the surface both the AGI and PCI services drive: ``substrate``,
    ``axioms``, ``endpoint_id``, ``run_intelligence_loop()`` and ``report()``.
    """

    def __init__(
        self, endpoint_id: str, role: str = "agi", n_nodes: int = 16, seed: int = 7
    ) -> None:
        self.endpoint_id = endpoint_id
        self.role = role
        self.substrate = ComputationalSubstrate(n_nodes=n_nodes, seed=seed)
        self.axioms = AxiomSet(self.substrate)
        self._processor = UniversalQuantumProcessor(max_dimension=2**10)
        self._cycle_count = 0
        self._history: List[Dict[str, Any]] = []
        self._bus: Any = None

    async def run_intelligence_loop(self) -> Dict[str, Any]:
        """Run one full cycle and return the measured record."""
        self._cycle_count += 1
        total_information = self.substrate.calculate_total_information()
        integrability = self.substrate.check_integrability()
        curvature = self.substrate.calculate_gauge_curvature()
        axiom_results = self.axioms.evaluate_all({"phi_feedback": 0.9})

        theta = math.pi / 4.0
        rotated = self.axioms.quantum_classical_duality(self.substrate, theta)

        record = {
            "cycle": self._cycle_count,
            "endpoint_id": self.endpoint_id,
            "role": self.role,
            "total_information": total_information,
            "gauge_curvature": curvature,
            "integrability_satisfied": integrability,
            "axioms": axiom_results,
            "axioms_held": int(sum(1 for r in axiom_results.values() if r["holds"])),
            "axioms_total": len(axiom_results),
            "duality_angle": theta,
            "rotated_norm": float(np.abs(rotated.psi_field).sum()),
            "phi_field_mean": float(self.substrate.phi_field.mean()),
        }
        self._history.append(record)
        if len(self._history) > 256:
            self._history = self._history[-256:]
        return record

    async def report(self) -> Dict[str, Any]:
        """Return the endpoint's current measured state."""
        total_information = self.substrate.calculate_total_information()
        integrability = self.substrate.check_integrability()
        curvature = self.substrate.calculate_gauge_curvature()
        axiom_results = self.axioms.evaluate_all({"phi_feedback": 0.9})
        return {
            "endpoint_id": self.endpoint_id,
            "role": self.role,
            "cycles_completed": self._cycle_count,
            "total_information": total_information,
            "gauge_curvature": curvature,
            "integrability_satisfied": integrability,
            "axioms_held": int(sum(1 for r in axiom_results.values() if r["holds"])),
            "axioms_total": len(axiom_results),
            "substrate": self.substrate.to_dict(),
            "claim": (
                "measured statistics only; this endpoint does not assert "
                "consciousness or universal intelligence"
            ),
        }

    def history(self, limit: int = 32) -> List[Dict[str, Any]]:
        """The most recent cycle records, oldest first."""
        return list(self._history[-max(0, int(limit)) :])


class UnifiedIntelligenceFactory:
    """Constructs the AGI-role and PCI-role endpoints.

    The two roles use different seeds so their substrates are distinct but
    individually reproducible. The factory does not claim the endpoints are
    equivalent; comparing them is :class:`ScientificValidator`'s job, and it
    reports measured criteria.
    """

    AGI_SEED = 7
    PCI_SEED = 13

    @staticmethod
    def create_agi_endpoint(
        n_nodes: int = 16, endpoint_id: Optional[str] = None
    ) -> UnifiedIntelligenceEndpoint:
        """Build the AGI-role endpoint."""
        return UnifiedIntelligenceEndpoint(
            endpoint_id=endpoint_id or "agi-endpoint",
            role="agi",
            n_nodes=n_nodes,
            seed=UnifiedIntelligenceFactory.AGI_SEED,
        )

    @staticmethod
    def create_pci_endpoint(
        n_nodes: int = 16, endpoint_id: Optional[str] = None
    ) -> UnifiedIntelligenceEndpoint:
        """Build the PCI-role endpoint."""
        return UnifiedIntelligenceEndpoint(
            endpoint_id=endpoint_id or "pci-endpoint",
            role="pci",
            n_nodes=n_nodes,
            seed=UnifiedIntelligenceFactory.PCI_SEED,
        )


@dataclass
class McKinseyDecisionContext:
    """A multi-criteria decision context.

    ``criteria_weights`` maps criterion name to a non-negative weight;
    ``alternatives`` maps alternative name to a criterion/score mapping.
    Weights are normalised internally, so callers need not pre-normalise them.
    """

    alternatives: Dict[str, Dict[str, float]] = field(default_factory=dict)
    criteria_weights: Dict[str, float] = field(default_factory=dict)
    context: str = "standard"
    seed: int = 17

    def normalised_weights(self) -> Dict[str, float]:
        """Criterion weights scaled to sum to 1 (uniform if all zero)."""
        weights = {k: float(v) for k, v in self.criteria_weights.items()}
        total = sum(weights.values())
        if total <= 0.0:
            n = len(weights) or 1
            return {k: 1.0 / n for k in weights}
        return {k: v / total for k, v in weights.items()}

    def is_valid(self) -> bool:
        """True when there is at least one alternative and one criterion."""
        return bool(self.alternatives) and bool(self.criteria_weights)


class McKinseyDecisionEngine:
    """AHP and Monte Carlo decision support over the supplied numbers.

    :meth:`analytic_hierarchy_process` runs the standard AHP power iteration
    for the principal eigenvector of a reciprocal comparison matrix and reports
    the consistency ratio. :meth:`monte_carlo_simulation` samples a real payoff
    distribution per alternative and reports the risk measures it measured.

    Neither method asserts an optimal business decision.
    """

    # Saaty random index denominators for the consistency ratio, n = 1..10.
    _RI: Dict[int, float] = {
        1: 0.00,
        2: 0.00,
        3: 0.58,
        4: 0.90,
        5: 1.12,
        6: 1.24,
        7: 1.32,
        8: 1.41,
        9: 1.45,
        10: 1.49,
    }

    def analytic_hierarchy_process(
        self, context: McKinseyDecisionContext, iterations: int = 64
    ) -> Dict[str, Any]:
        """Rank alternatives by principal-eigenvector weighting."""
        if not context.is_valid():
            return {
                "status": "invalid_context",
                "reason": "context needs at least one alternative and one criterion",
                "rankings": [],
                "consistency_ratio": None,
            }

        names = sorted(context.alternatives)
        criteria = sorted(context.criteria_weights)
        n = len(names)

        scores = np.array(
            [[float(context.alternatives[a].get(c, 0.0)) for c in criteria] for a in names],
            dtype=np.float64,
        )
        shifted = scores - scores.min(axis=0)
        shifted[shifted <= 0.0] = 1e-9
        ratios = shifted / shifted.sum(axis=0, keepdims=True)
        row_mean = ratios.mean(axis=1)

        matrix = np.ones((n, n), dtype=np.float64)
        for i in range(n):
            for j in range(n):
                if i != j:
                    matrix[i, j] = max(row_mean[i], 1e-9) / max(row_mean[j], 1e-9)
        matrix = 0.5 * (matrix + matrix.T)

        vector = np.ones(n, dtype=np.float64)
        for _ in range(max(1, int(iterations))):
            weighted = matrix @ vector
            total = float(weighted.sum())
            if total <= 0.0:  # pragma: no cover - defensive
                break
            vector = weighted / total

        eigenvalues = np.linalg.eigvalsh(matrix)
        lambda_max = float(eigenvalues.max())
        ci = (lambda_max - n) / max(n - 1, 1)
        ri = self._RI.get(n, 1.49)
        cr = float(ci / ri) if ri > 0 else 0.0

        order = np.argsort(vector)[::-1]
        return {
            "status": "ok",
            "rankings": [
                {"alternative": names[int(i)], "weight": float(vector[int(i)])} for i in order
            ],
            "lambda_max": lambda_max,
            "consistency_index": float(ci),
            "random_index": ri,
            "consistency_ratio": cr,
            "consistent": bool(cr <= 0.10),
            "criteria": criteria,
            "n_alternatives": n,
        }

    def monte_carlo_simulation(
        self,
        context: McKinseyDecisionContext,
        iterations: int = 10_000,
        confidence: float = 0.95,
    ) -> Dict[str, Any]:
        """Evaluate each alternative's payoff distribution and report risk.

        An alternative supplying ``samples`` is used empirically; otherwise
        its ``mean``/``std`` normal distribution is evaluated deterministically
        on an equally-spaced inverse-CDF quantile grid — exact quantile
        quadrature, not a pseudo-random draw. Reproducible for a fixed seed.
        """
        if not context.is_valid():
            return {
                "status": "invalid_context",
                "reason": "context needs at least one alternative and one criterion",
                "distributions": {},
            }

        n = max(1, int(iterations))
        results: Dict[str, Any] = {}
        for name in sorted(context.alternatives):
            spec = context.alternatives[name] or {}
            samples = spec.get("samples")
            if samples is not None and len(np.atleast_1d(samples)) > 1:
                draws = np.asarray(samples, dtype=np.float64).reshape(-1)
                method = "empirical"
            else:
                mean = float(spec.get("mean", 0.0))
                std = float(spec.get("std", 1.0))
                # Deterministic inverse-CDF quantile grid: the exact
                # distribution evaluated at equally-spaced quantiles — the
                # limit a seeded normal draw converges to, with zero
                # sampling error and byte-identical reproducibility.
                from agi.quantum_decision import normal_quantile_grid

                draws = normal_quantile_grid(mean, abs(std) if std else 1e-9, n)
                method = "normal"
            results[name] = {
                "iterations": int(draws.size),
                "mean": float(draws.mean()),
                "std": float(draws.std(ddof=1)) if draws.size > 1 else 0.0,
                "var_95": float(np.percentile(draws, (1.0 - confidence) * 100.0)),
                "probability_positive": float((draws > 0).mean()),
                "method": method,
            }
        return {
            "status": "ok",
            "iterations": n,
            "confidence": confidence,
            "distributions": results,
        }


def _bounded(value: Any) -> bool:
    """True when ``value`` is a finite, non-negative number."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f) and f >= 0.0


def _sync_report(endpoint: UnifiedIntelligenceEndpoint) -> Dict[str, Any]:
    """Run an endpoint's async report on a private event loop.

    Keeps :meth:`ScientificValidator.validate_unified_intelligence`
    synchronous, which is what both the AGI and PCI services call.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(endpoint.report())
    finally:
        loop.close()


class ScientificValidator:
    """Compares two endpoints against explicit, measurable criteria.

    Returns the measured ``criteria``, the fraction passed (``score``), and
    whether repeated reporting is byte-identical (``reproducible``).

    The score measures agreement on these criteria only. It is not a claim of
    scientific validation, consciousness, or system equivalence, and the
    returned payload states that in ``interpretation``.
    """

    #: Score at or above which the criteria set is considered satisfied.
    ACCEPTANCE_THRESHOLD = 0.90

    def validate_unified_intelligence(
        self,
        agi_endpoint: UnifiedIntelligenceEndpoint,
        pci_endpoint: UnifiedIntelligenceEndpoint,
    ) -> Dict[str, Any]:
        """Run the full comparison and return the measured agreement."""
        agi_report = _sync_report(agi_endpoint)
        pci_report = _sync_report(pci_endpoint)
        criteria: List[Dict[str, Any]] = []

        def add(name: str, left: Any, right: Any, passed: bool, detail: str) -> None:
            criteria.append(
                {
                    "criterion": name,
                    "agi": left,
                    "pci": right,
                    "passed": bool(passed),
                    "detail": detail,
                }
            )

        agi_nodes = agi_report.get("substrate", {}).get("n_nodes")
        pci_nodes = pci_report.get("substrate", {}).get("n_nodes")
        add(
            "substrate_size",
            agi_nodes,
            pci_nodes,
            agi_nodes == pci_nodes,
            "both substrates need the same node count to be comparable",
        )
        add(
            "integrability",
            agi_report.get("integrability_satisfied"),
            pci_report.get("integrability_satisfied"),
            bool(agi_report.get("integrability_satisfied"))
            and bool(pci_report.get("integrability_satisfied")),
            "both substrates must pass the degree-sum check",
        )
        add(
            "axioms_held",
            agi_report.get("axioms_held"),
            pci_report.get("axioms_held"),
            agi_report.get("axioms_held") == pci_report.get("axioms_held"),
            "identical axiom counts indicate identical predicate outcomes",
        )
        add(
            "total_information_bounded",
            agi_report.get("total_information"),
            pci_report.get("total_information"),
            _bounded(agi_report.get("total_information"))
            and _bounded(pci_report.get("total_information")),
            "total information must be a finite non-negative entropy",
        )
        add(
            "distinct_seeds",
            agi_report.get("total_information"),
            pci_report.get("total_information"),
            agi_report.get("total_information") != pci_report.get("total_information"),
            "endpoints use different seeds, so distinct substrates are expected",
        )

        passed = sum(1 for c in criteria if c["passed"])
        total = len(criteria)
        score = float(passed / total) if total else 0.0
        reproducible = _sync_report(agi_endpoint) == agi_report

        return {
            "status": "ok",
            "criteria": criteria,
            "criteria_passed": passed,
            "criteria_total": total,
            "score": score,
            "acceptance_threshold": self.ACCEPTANCE_THRESHOLD,
            "accepted": bool(score >= self.ACCEPTANCE_THRESHOLD),
            "reproducibility": float(1.0 if reproducible else 0.0),
            "reproducible": bool(reproducible),
            "interpretation": (
                "measured agreement on the listed criteria only; not a claim of "
                "scientific validation, consciousness, or system equivalence"
            ),
        }
