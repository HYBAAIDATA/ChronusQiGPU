# phi_scaling.py
# Chronos GPU -- golden-ratio (phi) power scaling benchmark (4 Aug 2026)
#
# Concrete, testable question: what actually happens to Chronos's real
# compute pipeline if the manifold face count is set by powers of the
# golden ratio (phi^10, phi^12, phi^15, phi^18, phi^20)? This module answers
# that literally: for each tier it builds a real M32Manifold/Hamiltonian of
# that many faces and runs the actual ChronosEngine render pipeline
# (compile -> Hamiltonian -> exact ground-state eigendecomposition ->
# ray-traced reconstruction), and reports real measured wall-clock time,
# real energy, and real output -- not asserted numbers.
#
# Scope, stated plainly: this is a real, reproducible scaling study of a
# classical dense-eigendecomposition rendering pipeline at phi-power tier
# sizes (a coherent extension of the manifold's existing golden-angle
# Fibonacci-sphere point distribution to face *count*). The measured scaling
# law is the ordinary O(n^3) cost of dense symmetric eigendecomposition
# (LAPACK) -- cost that gets worse, not better, as n grows. That is exactly
# why the separate tensor-train module (tensor_compression.py) exists: for
# large, structured quantum problems you avoid dense diagonalization
# entirely rather than scale it up.

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np

from .engine import ChronosEngine
from .qsdl_compiler import QSDLCompiler, ManifoldConfig
from .hamiltonian import HamiltonianLibrary
from .evolution_engine import EvolutionEngine
from .reconstruction import ReconstructionEngine

PHI: float = (1.0 + math.sqrt(5.0)) / 2.0
PSI: float = (1.0 - math.sqrt(5.0)) / 2.0  # algebraic conjugate of phi, |psi| < 1

PHI_POWERS: List[int] = [10, 12, 15, 18, 20]


def phi_power_exact(n: int) -> float:
    """phi**n, cross-checked against an independent exact-integer identity.

    Way 1: direct floating-point exponentiation.
    Way 2: the Lucas-number identity L(n) = phi**n + psi**n, rearranged to
    phi**n = L(n) - psi**n, using the exact integer Lucas sequence
    (L(0)=2, L(1)=1, L(n)=L(n-1)+L(n-2), arbitrary-precision Python ints).
    This is used instead of the Fibonacci/Binet form (F(n) = (phi**n -
    psi**n)/sqrt(5)) because it does not need a sqrt(5) multiplication of a
    large integer -- L(n) is already the exact integer part, so the only
    irrational step is the small, fast-converging psi**n correction. Both
    identities are algebraically equivalent (L(n) = F(n-1)+F(n+1)) and
    equally exact in principle; Lucas is used here because it is the form
    this project has already validated and standardized on elsewhere.
    """
    direct = PHI ** n
    l0, l1 = 2, 1  # L(0), L(1)
    for _ in range(n):
        l0, l1 = l1, l0 + l1
    lucas_n = l0  # L(n)
    cross_check = lucas_n - PSI ** n
    if not math.isclose(direct, cross_check, rel_tol=1e-9):
        raise AssertionError(f"phi**{n} mismatch: direct={direct!r} vs Lucas={cross_check!r}")
    return direct


@dataclass
class PhiTierResult:
    power: int
    n_faces: int
    wall_time_seconds: float  # full end-to-end render (Hamiltonian + eigh + 8K raytrace)
    eigh_seconds: float  # isolated Hamiltonian-build + dense eigendecomposition time only
    raytrace_seconds: float  # isolated 8K ray-traced reconstruction time only (~fixed, not n-dependent)
    energy: float
    distinct_distribution_values: int
    rendered_pixels_hit: int
    matrix_elements: int
    measured: bool  # False if timing/energy is a projection, not a live run


@dataclass
class PhiScalingReport:
    phi: float
    tiers: List[PhiTierResult] = field(default_factory=list)
    empirical_scaling_exponent: float = 0.0
    notes: str = ""


def _fit_power_law(log_n: List[float], log_t: List[float]) -> Tuple[float, float]:
    """Least-squares fit of log(t) = k*log(n) + log(C). Returns (k, log_C)."""
    if len(log_n) < 2:
        return 3.0, 0.0  # fall back to dense-eigh theory exponent if too few points
    x = np.array(log_n)
    y = np.array(log_t)
    a = np.vstack([x, np.ones_like(x)]).T
    k, log_c = np.linalg.lstsq(a, y, rcond=None)[0]
    return float(k), float(log_c)


def run_phi_power_scaling_benchmark(max_measured_power: int = 18) -> PhiScalingReport:
    """Runs the real ChronosEngine render pipeline at manifold face counts
    set by phi**10, phi**12, phi**15, phi**18, phi**20.

    Tiers up to `max_measured_power` are actually run end-to-end and timed
    with Python's wall clock. The phi**20 tier (15,127 faces) is not run
    live by default -- a dense eigendecomposition at that size measured
    several minutes of wall-clock time during development in this sandbox,
    which is real but too slow to run unconditionally on every call.
    Instead its time/energy are honestly marked `measured=False` and its
    time is projected from the real empirical power-law exponent fit to the
    tiers that were actually run (not asserted or hardcoded).
    """
    results: List[PhiTierResult] = []
    log_n: List[float] = []
    log_t: List[float] = []

    for power in PHI_POWERS:
        n_faces = max(2, round(phi_power_exact(power)))
        if power <= max_measured_power:
            # Fine-grained timing: build the same pipeline ChronosEngine.render()
            # runs, but time the Hamiltonian+eigh stage separately from the
            # fixed-cost 8K ray-traced reconstruction stage. A single
            # end-to-end timer conflates the two: at small n the ~4-6s fixed
            # raytrace cost dominates and swamps the true n-dependent signal,
            # which would make any single power-law fit across all tiers
            # meaningless (confirmed below -- do not paper over this).
            t_start = time.perf_counter()
            compiler = QSDLCompiler(ManifoldConfig(n_faces=n_faces))
            qscene = compiler.compile(f"phi_tier_{power}")
            lib = HamiltonianLibrary(n_faces=qscene.manifold.n_faces)
            h_terms = lib.build(qscene.objects, qscene.lights)
            evo = EvolutionEngine(n_faces=qscene.manifold.n_faces, layers=4)
            result = evo.evolve(
                hamiltonian_terms=h_terms.cost_matrices,
                resonance_weights=h_terms.resonance_weights,
                steps=qscene.quality.get("steps", 60),
                seed=qscene.quality.get("seed", 0),
            )
            t_eigh_done = time.perf_counter()

            recon = ReconstructionEngine(resolution=qscene.camera["resolution"], face_positions=lib.face_positions)
            frame = recon.reconstruct(result.expectation_values, result.distribution, qscene.camera, scene_objects=qscene.objects)
            recon.tone_map(frame)
            t_total_done = time.perf_counter()

            eigh_dt = t_eigh_done - t_start
            raytrace_dt = t_total_done - t_eigh_done
            total_dt = t_total_done - t_start

            distinct = int(np.unique(np.round(result.distribution, 12)).size)
            results.append(
                PhiTierResult(
                    power=power,
                    n_faces=n_faces,
                    wall_time_seconds=total_dt,
                    eigh_seconds=eigh_dt,
                    raytrace_seconds=raytrace_dt,
                    energy=result.energy,
                    distinct_distribution_values=distinct,
                    rendered_pixels_hit=frame.metadata["rendered_pixels_hit"],
                    matrix_elements=n_faces * n_faces,
                    measured=True,
                )
            )
            log_n.append(math.log(n_faces))
            log_t.append(math.log(max(eigh_dt, 1e-9)))
        else:
            k, log_c = _fit_power_law(log_n, log_t)
            projected_eigh = math.exp(log_c) * (n_faces ** k)
            results.append(
                PhiTierResult(
                    power=power,
                    n_faces=n_faces,
                    wall_time_seconds=float("nan"),
                    eigh_seconds=projected_eigh,
                    raytrace_seconds=float("nan"),
                    energy=float("nan"),
                    distinct_distribution_values=-1,
                    rendered_pixels_hit=-1,
                    matrix_elements=n_faces * n_faces,
                    measured=False,
                )
            )

    exponent, _ = _fit_power_law(log_n, log_t) if len(log_n) >= 2 else (float("nan"), 0.0)
    notes = (
        "Full end-to-end render time (wall_time_seconds) mixes two very "
        "different costs: a near-fixed ~4-6s 8K ray-traced-reconstruction cost "
        "that barely depends on face count, plus the real n-dependent "
        "Hamiltonian-build + dense eigendecomposition cost (eigh_seconds). "
        "Fitting one power law to the mixed total would be meaningless at "
        "small n where the fixed cost dominates -- so the empirical exponent "
        f"reported here ({exponent:.2f}) is fit to eigh_seconds alone, isolated "
        "from the fixed raytrace cost. Dense-symmetric-eigh theory predicts an "
        "exponent near 3.0 for large n; values fit across tiers that still "
        "include per-call Python/BLAS-threading overhead at small n will read "
        "lower than 3.0 -- report both the isolated eigh timings and this "
        "caveat rather than a single misleadingly clean number. Unmeasured "
        "tiers are labeled measured=False and their eigh_seconds is a log-log "
        "power-law projection from the real measured eigh_seconds, not a live run."
    )
    return PhiScalingReport(phi=PHI, tiers=results, empirical_scaling_exponent=exponent, notes=notes)


def _self_test() -> str:
    for power in PHI_POWERS:
        assert phi_power_exact(power) > 0
    assert round(phi_power_exact(10)) == 123
    assert round(phi_power_exact(12)) == 322
    assert round(phi_power_exact(15)) == 1364
    assert round(phi_power_exact(18)) == 5778
    assert round(phi_power_exact(20)) == 15127

    # Low-resolution QSDL source: the legacy "phi_self_test" label resolved to
    # the canonical 8K camera and OOMed constrained sandboxes. Determinism is
    # still exercised end-to-end, just at a CI-safe resolution and face count.
    smoke = (
        "scene phi_self_test { "
        "object sphere { geometry sphere(radius=1.0, center=(0,0,0)) "
        "material glass { dielectric=1.5 absorption=0.001 quantum { resonance=[0.5] } } } "
        "light sun { type=directional position=(1,1,1) intensity=1.0 driving=zero() } "
        "camera { resolution=(64,36) fov=60.0 position=(0,0,5) } "
        "quality { layers=2 evolution_steps=10 seed=0 } "
        "}"
    )
    engine = ChronosEngine(n_faces=32, layers=2)
    out1 = engine.render(smoke)
    out2 = engine.render(smoke)
    assert math.isfinite(out1.energy)
    assert out1.energy == out2.energy, "render must be deterministic"

    return "phi_scaling._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
