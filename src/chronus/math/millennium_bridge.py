#!/usr/bin/env python3
"""One operator family across the seven Millennium problems.

This module is documentation that CITES the golden module: every exact
number here comes from ``chronus.math.unified_quantum_engine.GoldenArithmetic``,
the same arithmetic the engine's checkpoints run on. Delete that module and
this one stops importing.

Contract
--------
Each function returns the bottom of the spectrum of a curvature Laplacian
for one concrete, exactly-representable case, plus the label that says how
strong the link actually is:

    PROVED           settled, and settled by this structure
    SHARED_STRUCTURE same analytic skeleton, no implication
    ANALOGY          thematic only
    STATED           a number quoted, not computed here
    OPEN             the case is the problem

Nothing here solves anything. It makes the unification checkable and names
where it breaks. That is the whole point: a reviewer can run it.

Correction recorded
-------------------
An earlier draft claimed the figure-eight knot complement's shortest closed
geodesic is 2 ln(phi) ~ 0.9624, labelled PROVED. The arithmetic identity
arccosh(sqrt(5)/2) = ln(phi) is true, but the geometric claim is false: a
search over all words of length <= 8 in the standard generators of the
figure-eight group finds a shortest closed geodesic of ~1.08707 (matching
the known value) and nothing near 0.9624. The PROVED geodesic reading now
lives where it is actually a theorem: on the modular surface, where the
hyperbolic elements are integer matrices, traces are integers >= 3, and the
smallest trace, 3 = L(2) = trace(Q^2), is the square of the engine's fold.

This module is **internal mathematics / research documentation**. It is not
a customer-visible surface and must not be re-exported on API responses.
"""

from __future__ import annotations

import itertools
import logging
import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence

from chronus.math.unified_quantum_engine import GoldenArithmetic

LOG = logging.getLogger("chronus.math.bridge")

PHI = (1 + 5**0.5) / 2


@dataclass(frozen=True)
class Reading:
    """Bottom of a spectrum, and how much the link carries."""

    problem: str
    quantity: str
    value: float
    link: str
    note: str


def fold_spectrum() -> tuple[float, float]:
    """Exact roots of the Fibonacci transfer matrix. Radius phi, product -1."""
    disc = math.sqrt(5.0)
    return ((1 + disc) / 2, (1 - disc) / 2)


def fold_reading() -> Reading:
    top, bottom = fold_spectrum()
    if abs(top * bottom + 1.0) > 1e-15:
        raise AssertionError("det must be -1")
    if abs((top + bottom) - GoldenArithmetic.lucas(1)) > 1e-15:
        raise AssertionError("trace(Q) must be L(1)")
    if GoldenArithmetic.cassini(7) != -1 or GoldenArithmetic.cassini(8) != 1:
        raise AssertionError("Cassini sign is det(Q^n)")
    return Reading(
        problem="Poincare",
        quantity="spectral radius of Q",
        value=top,
        link="SHARED_STRUCTURE",
        note=(
            "det -1 is the unimodularity that makes the engine's fold lossless "
            "(GoldenArithmetic.cassini certifies it at every width used)"
        ),
    )


def arccosh_sqrt5_over_2_is_ln_phi() -> float:
    """arccosh(sqrt(5)/2) = ln(phi) exactly, because sqrt(5)/2 + 1/2 = phi."""
    return math.acosh(math.sqrt(5) / 2)


def modular_geodesic(k: int) -> float:
    """Length of the closed geodesic of the modular surface traced by Q^(2k)."""
    return 2 * math.acosh(GoldenArithmetic.lucas(2 * k) / 2)


def geodesic_reading() -> Reading:
    if abs(arccosh_sqrt5_over_2_is_ln_phi() - math.log(PHI)) > 1e-12:
        raise AssertionError("closed forms must agree")
    for k in range(1, 7):
        if abs(modular_geodesic(k) - 4 * k * math.log(PHI)) > 1e-9:
            raise AssertionError(f"L(2k) geodesic length identity fails at k={k}")
    return Reading(
        problem="Poincare / geometrization",
        quantity="systole of the modular surface (trace 3 = L(2) = trace(Q^2))",
        value=modular_geodesic(1),
        link="PROVED",
        note=(
            "hyperbolic elements of PSL(2,Z) have integer trace >= 3, so the "
            "smallest, 3, gives the shortest geodesic: 4 ln(phi) ~ 1.9248. The "
            "figure-eight complement's systole is ~1.08707, NOT 2 ln(phi); see "
            "the module docstring for the correction"
        ),
    )


def _rank(matrix: list[list[Fraction]]) -> int:
    rows = [row[:] for row in matrix if any(row)]
    if not rows:
        return 0
    width = len(rows[0])
    rank = 0
    for col in range(width):
        pivot = next((r for r in range(rank, len(rows)) if rows[r][col]), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        scale = rows[rank][col]
        rows[rank] = [value / scale for value in rows[rank]]
        for r in range(len(rows)):
            if r != rank and rows[r][col]:
                factor = rows[r][col]
                rows[r] = [a - factor * b for a, b in zip(rows[r], rows[rank])]
        rank += 1
    return rank


def betti_1(
    vertices: int,
    edges: Sequence[tuple[int, int]],
    faces: Sequence[tuple[int, int, int]],
) -> int:
    """dim ker(Delta_1) on a 2-complex, over Q. Betti_1 by the Hodge theorem."""
    index = {edge: i for i, edge in enumerate(edges)}
    d1 = [[Fraction(0)] * vertices for _ in edges]
    for i, (a, b) in enumerate(edges):
        d1[i][a] = Fraction(-1)
        d1[i][b] = Fraction(1)
    d2 = [[Fraction(0)] * len(edges) for _ in faces]
    for f, (a, b, c) in enumerate(faces):
        for u, v, sign in ((b, c, 1), (a, c, -1), (a, b, 1)):
            d2[f][index[(min(u, v), max(u, v))]] += Fraction(sign)
    lap = [
        [
            sum(d2[f][i] * d2[f][j] for f in range(len(faces)))
            + sum(d1[i][v] * d1[j][v] for v in range(vertices))
            for j in range(len(edges))
        ]
        for i in range(len(edges))
    ]
    return len(edges) - _rank(lap)


def hodge_reading() -> Reading:
    cycle = [(0, 1), (1, 2), (0, 2)]
    hollow = betti_1(3, cycle, [])
    filled = betti_1(3, cycle, [(0, 1, 2)])
    if hollow != 1:
        raise AssertionError("unfilled triangle carries one harmonic 1-form")
    if filled != 0:
        raise AssertionError("filled triangle has none: cycle is a boundary")
    return Reading(
        problem="Hodge",
        quantity="dim ker(Delta_1), hollow then filled",
        value=float(hollow),
        link="SHARED_STRUCTURE",
        note="conjecture asks when those classes are algebraic, not just closed",
    )


def wilson_gap(size: int, coupling: float = 1.0) -> float:
    """Bottom of the Hessian of the U(1) Wilson action on a size x size torus."""
    if size < 2:
        raise ValueError("lattice needs size >= 2")
    return 4 * math.sin(math.pi / size) ** 2 / coupling**2


def yang_mills_reading() -> Reading:
    sizes = (8, 16, 32, 64, 128)
    gaps = [wilson_gap(n) for n in sizes]
    if not all(g > 0 for g in gaps):
        raise AssertionError("finite lattice always has a gap")
    for small, large in zip(gaps, gaps[1:]):
        if large >= small:
            raise AssertionError("gap must shrink with volume")
    ratio = gaps[0] / gaps[-1]
    if abs(gaps[-2] / gaps[-1] - 4.0) > 0.01:
        raise AssertionError("decays as 1/L^2 in the large-L limit")
    return Reading(
        problem="Yang-Mills existence and mass gap",
        quantity="gap at L=128, g=1",
        value=gaps[-1],
        link="OPEN",
        note=f"1/L^2 decay, {ratio:.0f}x from L=8; a uniform gap is the problem",
    )


def navier_stokes_reading() -> Reading:
    """Same parabolic-energy-plus-singularity skeleton as Yang-Mills."""
    return Reading(
        problem="Navier-Stokes",
        quantity="vorticity growth vs nu*|k|^2",
        value=2.0,
        link="STATED",
        note=(
            "the exponent is quoted, not computed here; the shared skeleton "
            "is the claim, and it carries no implication"
        ),
    )


def riemann_reading() -> Reading:
    return Reading(
        problem="Riemann",
        quantity="critical line as spectral reality",
        value=0.5,
        link="ANALOGY",
        note="Hilbert-Polya: a self-adjoint operator whose spectrum is the zeros",
    )


def ising_ground(weights: Sequence[Sequence[float]]) -> float:
    """Exact ground state of a fully connected Ising model. NP-hard baseline."""
    n = len(weights)
    best = math.inf
    for spins in itertools.product((-1, 1), repeat=n):
        energy = sum(
            weights[i][j] * spins[i] * spins[j]
            for i in range(n)
            for j in range(i + 1, n)
        )
        best = min(best, energy)
    return best


def p_vs_np_reading() -> Reading:
    weights = [[0.0] * 12 for _ in range(12)]
    for i in range(12):
        for j in range(i + 1, 12):
            weights[i][j] = float((i * 7 + j * 13) % 11) - 5.0
    ground = ising_ground(weights)
    if ground >= 0.0:
        raise AssertionError("instance must be frustrated")
    return Reading(
        problem="P vs NP",
        quantity="exact Ising ground state, n=12",
        value=ground,
        link="OPEN",
        note=(
            "2^12 here; the engine's uniform-coupling solver is O(n log n), so "
            "the gap is tractability"
        ),
    )


def bridge() -> list[Reading]:
    return [
        fold_reading(),
        geodesic_reading(),
        hodge_reading(),
        yang_mills_reading(),
        navier_stokes_reading(),
        riemann_reading(),
        p_vs_np_reading(),
    ]


def self_test() -> None:
    for reading in bridge():
        if not (reading.quantity and reading.note):
            raise AssertionError("every reading carries its caveat")
    if betti_1(4, [(0, 1), (1, 2), (2, 3), (0, 3)], []) != 1:
        raise AssertionError("hollow square has betti_1 = 1")
    if betti_1(4, [(0, 1), (1, 2), (0, 2), (2, 3), (0, 3)], [(0, 1, 2), (0, 2, 3)]) != 0:
        raise AssertionError("fully filled square has betti_1 = 0")
    if (
        betti_1(
            5,
            [(0, 1), (1, 2), (0, 2), (2, 3), (3, 4), (2, 4)],
            [(0, 1, 2)],
        )
        != 1
    ):
        raise AssertionError("two cycles with one filled leaves betti_1 = 1")
    if not wilson_gap(2) > wilson_gap(4) > wilson_gap(8):
        raise AssertionError("gap shrinks with volume")
    if abs(arccosh_sqrt5_over_2_is_ln_phi() - 0.4812118250596035) > 1e-12:
        raise AssertionError("ln(phi) identity")
    if abs(modular_geodesic(1) - 4 * math.log(PHI)) > 1e-12:
        raise AssertionError("modular systole is 4 ln(phi)")
    LOG.info("bridge self test passed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    self_test()
    for item in bridge():
        print(f"{item.link:17} {item.problem}")
        print(f"  {item.quantity}: {item.value:.6f}")
        print(f"  {item.note}")
