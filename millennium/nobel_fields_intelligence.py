"""
Nobel/Fields Intelligence System
================================

Operational implementation integrating Nobel Prize and Fields Medal level
mathematical intelligence frameworks.

This system explores:
- Riemann Hypothesis (Nobel-equivalent in mathematics)
- P vs NP (Millennium Prize)
- Birch and Swinnerton-Dyer Conjecture (Millennium Prize)
- Hodge Conjecture (Millennium Prize)
- Yang-Mills Existence (Millennium Prize)
- Navier-Stokes Smoothness (Millennium Prize)

Every explorer delegates to the real deterministic probes shipped in
:mod:`millennium.millennium_suite` — exact prime counts vs li(x)/R(x),
measured DPLL cost on seeded 3-SAT, the finite-volume SU(2) covariant
Laplacian spectrum, the de-aliased pseudo-spectral Navier-Stokes truncation,
exact Hasse-bound verification plus the BSD product law, and Hodge-diamond
arithmetic.  Each result carries the probe's evidence class; nothing here
claims a proof of any Clay problem.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: amplitude

import math
import numpy as np
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import logging

try:
    from . import millennium_suite as _suite
except ImportError:  # pragma: no cover - direct script use
    import millennium_suite as _suite

logger = logging.getLogger("hyba.nobel_fields")

PHI = (1 + math.sqrt(5)) / 2
PSI = (1 - math.sqrt(5)) / 2


class MathematicalDomain(Enum):
    """Mathematical domains for Nobel/Fields level intelligence."""

    NUMBER_THEORY = "number_theory"
    ALGEBRAIC_GEOMETRY = "algebraic_geometry"
    TOPOLOGY = "topology"
    MATHEMATICAL_PHYSICS = "mathematical_physics"
    ANALYSIS = "analysis"
    COMPLEXITY = "complexity"


@dataclass
class MathematicalInsight:
    """Mathematical insight from exploration."""

    domain: MathematicalDomain
    conjecture: str
    evidence: float
    geometric_structure: str
    phi_correlation: float


def _fit_loglog(xs: List[float], ys: List[float]) -> Dict[str, float]:
    """Least-squares slope of y vs x on the supplied (already transformed) axes."""
    if len(xs) < 3:
        return {"slope": 0.0, "r_squared": 0.0, "points": len(xs)}
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    predicted = slope * x + intercept
    ss_res = float(np.sum((y - predicted) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 1e-18 else 1.0
    return {"slope": float(slope), "r_squared": float(r_squared), "points": len(xs)}


class NobelFieldsIntelligence:
    """
    Nobel/Fields Intelligence System for mathematical exploration.

    Every explorer runs the shipped deterministic computation for its
    problem and reports the measured quantity with its honest evidence
    class.  Results are observations on declared finite scopes — they do
    not prove, disprove, or partially prove any Clay problem.
    """

    def __init__(self):
        self.insights: List[MathematicalInsight] = []
        self.exploration_history: List[Dict[str, Any]] = []
        self.phi_scales = {
            "φ¹⁵": PHI**15,  # 1364.0007
            "φ²⁰": PHI**20,  # 15126.9999
            "φ³¹": PHI**31,  # 3010349.9
            "φ⁷⁶": PHI**76,  # 3.416e16
        }

    def explore_riemann_hypothesis(self, interval: Dict[str, Any]) -> Dict[str, Any]:
        """
        Riemann Hypothesis: exact prime counts against li(x) and R(x).

        Sieves the interval exactly, compares pi(x) to the real logarithmic
        integral (dt/log t) and the Gram-series Riemann R(x), and reports the
        RH-equivalent normalised residual |pi(x) - R(x)| / (sqrt(x) log x).
        Tabulated first zeta zeros are inputs, not results.
        """
        start = max(2, int(interval.get("start", 2)))
        end = max(start + 1, int(interval.get("end", 100)))
        prime_limit = max(end, int(interval.get("prime_limit", end)))

        primes = _suite._sieve(prime_limit)
        pi_start = int(np.searchsorted(primes, start, side="left"))
        pi_end = int(np.searchsorted(primes, end, side="right"))
        observed = pi_end - pi_start

        expected = _suite._log_integral(end) - _suite._log_integral(start)
        r_deviation = pi_end - _suite._riemann_R(float(end))
        bound = math.sqrt(end) * math.log(end)
        normalised_residual = abs(r_deviation) / bound if bound > 0 else 0.0

        result = {
            "domain": MathematicalDomain.NUMBER_THEORY.value,
            "conjecture": "Riemann Hypothesis",
            "interval": [start, end],
            "observed_primes": observed,
            "expected_primes_li": expected,
            "li_deviation": observed - expected,
            "pi_minus_R_at_end": float(r_deviation),
            "rh_bound_normalised_residual": normalised_residual,
            "error_bound": bound,
            "zeta_zeros": [complex(0.5, g) for g in _suite.ZETA_ZERO_GAMMAS[:3]],
            "evidence_class": _suite.FINITE_RANGE_OBSERVATION,
            "hypothesis_status": _suite.FINITE_RANGE_OBSERVATION,
            "proof_claim": False,
            "evidence": (
                f"pi({end}) - R({end}) = {r_deviation:.3f} against the "
                f"RH-equivalent bound sqrt(x) log x = {bound:.3f} "
                f"(normalised {normalised_residual:.4f}). A finite window "
                "cannot witness the asymptotic bound."
            ),
            "phi_scale": "φ²⁰",
        }

        insight = MathematicalInsight(
            domain=MathematicalDomain.NUMBER_THEORY,
            conjecture="Riemann Hypothesis",
            evidence=normalised_residual,
            geometric_structure="Critical line Re(s)=1/2",
            phi_correlation=normalised_residual,
        )

        self.insights.append(insight)
        self.exploration_history.append(result)

        return result

    def explore_bsd_conjecture(self, elliptic_curve: Dict[str, Any]) -> Dict[str, Any]:
        """
        Birch and Swinnerton-Dyer: exact a_p and the classical product law.

        For y^2 = x^3 + a x + b, computes a_p = p + 1 - #E(F_p) exactly via
        Legendre sums over every good prime up to ``prime_limit``, verifies
        the Hasse bound |a_p| <= 2 sqrt(p), and measures the growth exponent
        of prod_{p<=X} N_p/p — the empirical BSD rank law on a finite window.
        """
        a = int(elliptic_curve.get("a", 0))
        b = int(elliptic_curve.get("b", 1))
        prime_limit = max(8, int(elliptic_curve.get("prime_limit", 400)))

        discriminant = -16 * (4 * (a**3) + 27 * (b**2))
        is_degenerate = discriminant == 0

        ap_values: List[int] = []
        hasse_violations = 0
        fit = {"slope": 0.0, "r_squared": 0.0, "points": 0}
        if not is_degenerate:
            bad_divisor = 4 * a**3 + 27 * b**2
            xs: List[float] = []
            ys: List[float] = []
            running = 0.0
            for p in (int(p) for p in _suite._sieve(prime_limit) if int(p) > 2):
                if bad_divisor % p == 0:
                    continue
                ap = _suite._elliptic_a_p(a, b, p)
                ap_values.append(ap)
                if abs(ap) > 2.0 * math.sqrt(p) + 1e-9:
                    hasse_violations += 1
                running += math.log((p + 1 + ap) / p)
                xs.append(math.log(math.log(p)))
                ys.append(running)
            fit = _fit_loglog(xs, ys)

        result = {
            "domain": MathematicalDomain.ALGEBRAIC_GEOMETRY.value,
            "conjecture": "Birch and Swinnerton-Dyer",
            "elliptic_curve": {"a": a, "b": b},
            "discriminant": discriminant,
            "is_degenerate": is_degenerate,
            "prime_limit": prime_limit,
            "primes_used": len(ap_values),
            "hasse_violations": hasse_violations,
            "hasse_bound_verified": hasse_violations == 0,
            "bsd_growth_exponent": fit["slope"],
            "bsd_fit_r_squared": fit["r_squared"],
            "mean_abs_ap": float(np.mean(np.abs(ap_values))) if ap_values else 0.0,
            "evidence_class": _suite.KNOWN_THEOREM_SCOPE,
            "hypothesis_status": (
                "DEGENERATE" if is_degenerate else _suite.KNOWN_THEOREM_SCOPE
            ),
            "proof_claim": False,
            "evidence": (
                "Curve is singular"
                if is_degenerate
                else (
                    f"Hasse bound verified on {len(ap_values)} primes; "
                    f"prod(N_p/p) growth exponent {fit['slope']:.3f} "
                    f"(R^2={fit['r_squared']:.3f}). The exponent is the "
                    "classical BSD numerical observation on a finite prime "
                    "window; the rank conjecture is open."
                )
            ),
        }

        insight = MathematicalInsight(
            domain=MathematicalDomain.ALGEBRAIC_GEOMETRY,
            conjecture="BSD Conjecture",
            evidence=abs(fit["slope"]),
            geometric_structure="Elliptic curve group",
            phi_correlation=abs(fit["slope"]),
        )

        self.insights.append(insight)
        self.exploration_history.append(result)

        return result

    def explore_hodge_conjecture(self, manifold: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hodge Conjecture: exact Hodge-diamond arithmetic for a complex torus.

        Computes the real diamond h^{p,q} = C(n,p) C(n,q), the Betti numbers
        and Euler characteristic, and counts the (p,p) classes in codimension
        strictly between 1 and n-1 that neither the Lefschetz (1,1) theorem
        nor its Poincare dual reaches.
        """
        dimension = max(1, int(manifold.get("dimension", 4)))

        diamond = _suite._hodge_diamond_abelian(dimension)
        betti = [
            int(sum(diamond[p][k - p] for p in range(dimension + 1) if 0 <= k - p <= dimension))
            for k in range(2 * dimension + 1)
        ]
        euler = int(sum((-1) ** k * b for k, b in enumerate(betti)))
        uncovered = sum(int(diamond[p][p]) for p in range(2, dimension))

        result = {
            "domain": MathematicalDomain.TOPOLOGY.value,
            "conjecture": "Hodge Conjecture",
            "dimension": dimension,
            "hodge_diamond": diamond.tolist(),
            "betti_numbers": betti,
            "euler_characteristic": euler,
            "diamond_symmetric": bool((diamond == diamond.T).all()),
            "lefschetz_11_divisor_classes": int(diamond[1][1]),
            "point_class_codim_n": int(diamond[dimension][dimension]),
            "hodge_classes_not_reached_by_classical_theorems": uncovered,
            "evidence_class": (
                _suite.KNOWN_THEOREM_SCOPE if uncovered == 0 else _suite.OPEN
            ),
            "hypothesis_status": (
                _suite.KNOWN_THEOREM_SCOPE if uncovered == 0 else _suite.OPEN
            ),
            "proof_claim": False,
            "evidence": (
                f"{uncovered} Hodge classes lie in codimension strictly "
                "between 1 and n-1, beyond Lefschetz (1,1) and its Poincare "
                "dual. Counting them is not constructing them; the general "
                "conjecture is open."
            ),
        }

        insight = MathematicalInsight(
            domain=MathematicalDomain.TOPOLOGY,
            conjecture="Hodge Conjecture",
            evidence=float(uncovered),
            geometric_structure="Complex projective variety",
            phi_correlation=float(uncovered),
        )

        self.insights.append(insight)
        self.exploration_history.append(result)

        return result

    def explore_yang_mills(self, field_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Yang-Mills: exact spectrum of the finite-volume covariant Laplacian.

        Builds the 4D hypercubic covariant Laplacian with deterministic SU(2)
        link variables, verifies Hermiticity and link unitarity/det = 1, and
        reports the smallest eigenvalue against the free-field reference
        4 sin^2(pi/L).  A positive finite-volume gap is a box artefact; the
        continuum mass gap is open.
        """
        lattice_size = max(2, int(field_state.get("lattice_size", 3)))
        gauge_group = field_state.get("gauge_group", "SU(2)")
        coupling = float(field_state.get("coupling", 0.5))

        operator, links = _suite._covariant_laplacian(lattice_size, seed=0x4D15 + lattice_size)
        eigenvalues = np.linalg.eigvalsh(operator)
        gap = float(eigenvalues[0])
        sample = links[0][:16]
        determinants = np.array([np.linalg.det(link) for link in sample])
        unitarity = np.array(
            [np.max(np.abs(link.conj().T @ link - np.eye(2))) for link in sample]
        )
        hermiticity = float(np.max(np.abs(operator - operator.conj().T)))
        free_field = 4.0 * math.sin(math.pi / lattice_size) ** 2

        result = {
            "domain": MathematicalDomain.MATHEMATICAL_PHYSICS.value,
            "conjecture": "Yang-Mills Existence and Mass Gap",
            "gauge_group": gauge_group,
            "coupling": coupling,
            "lattice_size": lattice_size,
            "sites": lattice_size**4,
            "operator_dimension": 2 * lattice_size**4,
            "smallest_eigenvalue": gap,
            "spectral_radius": float(np.max(np.abs(eigenvalues))),
            "hermiticity_residual": hermiticity,
            "link_determinant_max_deviation": float(np.max(np.abs(determinants - 1.0))),
            "link_unitarity_max_deviation": float(np.max(unitarity)),
            "free_field_reference_gap": free_field,
            "gap_vs_free_field": gap / free_field if free_field > 0 else 0.0,
            "evidence_class": _suite.FINITE_VOLUME_VERIFIED,
            "hypothesis_status": _suite.FINITE_VOLUME_VERIFIED,
            "continuum_mass_gap": _suite.OPEN,
            "proof_claim": False,
            "evidence": (
                f"Covariant Laplacian Hermitian to {hermiticity:.2e}, links "
                f"SU(2)-exact; smallest eigenvalue {gap:.4f} vs free-field "
                f"{free_field:.4f}. The gap follows the box, not a mass "
                "scale; the continuum limit is open (clay_checklist G1-G6)."
            ),
        }

        insight = MathematicalInsight(
            domain=MathematicalDomain.MATHEMATICAL_PHYSICS,
            conjecture="Yang-Mills Mass Gap",
            evidence=gap,
            geometric_structure="Gauge theory bundle",
            phi_correlation=gap / free_field if free_field > 0 else 0.0,
        )

        self.insights.append(insight)
        self.exploration_history.append(result)

        return result

    def explore_navier_stokes(self, fluid_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Navier-Stokes: de-aliased pseudo-spectral Galerkin truncation.

        Integrates the truncated 3D incompressible system (Taylor-Green
        initial data, 2/3 de-aliasing, RK4) and reports max vorticity, the
        Beale-Kato-Majda integral, and energy decay.  Truncation behaviour is
        not PDE behaviour; existence-and-smoothness is untouched.
        """
        grid = max(8, int(fluid_state.get("ns_grid", 8)))
        steps = int(fluid_state.get("ns_steps", 60))
        nu = float(fluid_state.get("viscosity", 0.05))
        dt = 0.02 if grid <= 8 else 0.01

        run = _suite._ns_run(grid, steps, nu=nu, dt=dt)

        result = {
            "domain": MathematicalDomain.ANALYSIS.value,
            "conjecture": "Navier-Stokes Smoothness",
            "grid": run["grid"],
            "viscosity": run["viscosity"],
            "steps": run["steps"],
            "kmax_resolved": run["kmax_resolved"],
            "max_vorticity_initial": run["max_vorticity_initial"],
            "max_vorticity_final": run["max_vorticity_final"],
            "vorticity_growth_fit": run["vorticity_growth_fit"],
            "bkm_integral": run["bkm_integral"],
            "energy_decay_ratio": run["energy_decay_ratio"],
            "kolmogorov_wavenumber_estimate": run["kolmogorov_wavenumber_estimate"],
            "resolves_dissipation_scale": run["resolves_dissipation_scale"],
            "evidence_class": _suite.TRUNCATED_MODEL,
            "hypothesis_status": _suite.TRUNCATED_MODEL,
            "proof_claim": False,
            "evidence": (
                f"Vorticity bounded ({run['max_vorticity_initial']:.3f} -> "
                f"{run['max_vorticity_final']:.3f}), BKM integral "
                f"{run['bkm_integral']:.3f} finite on the truncation. BKM is "
                "a criterion for the un-truncated PDE; a truncation that "
                "under-resolves the dissipation scale cannot witness it."
            ),
        }

        insight = MathematicalInsight(
            domain=MathematicalDomain.ANALYSIS,
            conjecture="Navier-Stokes Smoothness",
            evidence=float(run["bkm_integral"]),
            geometric_structure="Fluid manifold",
            phi_correlation=float(run["energy_decay_ratio"]),
        )

        self.insights.append(insight)
        self.exploration_history.append(result)

        return result

    def explore_p_vs_np(self, workload: Dict[str, Any]) -> Dict[str, Any]:
        """
        P vs NP: measured DPLL node counts on deterministic seeded 3-SAT.

        Generates seeded instances at the 4.26 clause/variable phase ratio
        and counts DPLL nodes (with unit propagation) under a declared cap.
        ``size`` is clamped to the deep-scale SAT window: measured cost on a
        finite window separates nothing.
        """
        requested = int(workload.get("size", 8))
        n_vars = max(4, min(requested, 19))
        n_clauses = int(round(4.26 * n_vars))
        instances = max(1, int(workload.get("instances", 5)))
        sat_cap = int(workload.get("sat_cap", 4_000))

        nodes: List[int] = []
        sat_flags: List[bool] = []
        for k in range(instances):
            clauses = _suite._random_3sat(n_vars, n_clauses, seed=1000 * n_vars + k)
            sat, node_count = _suite._dpll_nodes(clauses, n_vars, sat_cap)
            nodes.append(node_count)
            sat_flags.append(sat)
        median_nodes = float(np.median(nodes))

        result = {
            "domain": MathematicalDomain.COMPLEXITY.value,
            "conjecture": "P vs NP",
            "workload_size": requested,
            "n_vars_used": n_vars,
            "n_clauses": n_clauses,
            "clause_ratio": 4.26,
            "instances": instances,
            "measured_median_dpll_nodes": median_nodes,
            "node_counts": [int(n) for n in nodes],
            "satisfiable_fraction": float(np.mean(sat_flags)),
            "exponential_baseline_2^n": float(2.0**n_vars),
            "capped_fraction": float(np.mean([n >= sat_cap for n in nodes])),
            "evidence_class": _suite.FINITE_RANGE_OBSERVATION,
            "hypothesis_status": _suite.FINITE_RANGE_OBSERVATION,
            "proof_claim": False,
            "evidence": (
                f"Median {median_nodes:.0f} DPLL nodes at n={n_vars} "
                f"clauses={n_clauses} vs 2^n = {2.0**n_vars:.3g}. A finite "
                "cost window is neither evidence for P != NP nor for P = NP."
            ),
        }

        insight = MathematicalInsight(
            domain=MathematicalDomain.COMPLEXITY,
            conjecture="P vs NP",
            evidence=median_nodes / max(1.0, 2.0**n_vars),
            geometric_structure="Complexity class",
            phi_correlation=median_nodes / max(1.0, 2.0**n_vars),
        )

        self.insights.append(insight)
        self.exploration_history.append(result)

        return result

    def get_exploration_summary(self) -> Dict[str, Any]:
        """Get summary of all explorations."""
        if not self.exploration_history:
            return {"status": "no_explorations"}

        domain_counts = {}
        for exploration in self.exploration_history:
            domain = exploration.get("domain", "unknown")
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        avg_phi_correlation = (
            np.mean([i.phi_correlation for i in self.insights]) if self.insights else 0.0
        )

        return {
            "total_explorations": len(self.exploration_history),
            "total_insights": len(self.insights),
            "domains_explored": domain_counts,
            "average_phi_correlation": avg_phi_correlation,
            "phi_scales_used": list(self.phi_scales.keys()),
        }


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (amplitude_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("amplitude_kernel")([1.0, 1.0], n)
    result["module"] = __name__
    return result
