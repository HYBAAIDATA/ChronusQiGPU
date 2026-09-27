"""Join the finite SU(2) thread to the TOE, and name what that opens.

The TOE already carried two objects that share a word with this thread and
are not the same object:

* ``toe.poincare_golden_11d`` — the 11-dimensional hyperbolic ball.
  Sectional curvature is -1. That geometry stays as it is.
* theorem T10 and the counterfactual "Yang-Mills bound" — the predicate
  ``sqrt(5) > 0``. That predicate cannot fail, so it was not a gap.

This module runs ``millennium.hyba_poincare_yangmills`` and reads the first
positive eigenvalue of the quantum-group Laplacian on the binary icosahedral
group 2I. That number is the finite-model mass gap

    Delta = 1 - phi/2 = 1/(2 phi^2) = (3 - sqrt(5))/4.

It is an eigenvalue of a finite subgroup of SU(2), the 600-cell triangulation
of S^3, which is the universal cover of the Poincare homology sphere
Sigma(2,3,5). It is not the continuum Yang-Mills mass gap on R^4.
``proof_claim`` stays false. SHA256d consensus is not touched.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

PHI = (1.0 + math.sqrt(5.0)) / 2.0
EXACT_GAP = 1.0 - PHI / 2.0  # identity check only; the reported gap is computed


def _report() -> Dict[str, Any]:
    from millennium.hyba_poincare_yangmills import cached_report

    return cached_report(verbose=False)


def finite_gauge_gap() -> float:
    """First positive Laplacian eigenvalue on 2I. Computed, then cached."""
    return float(_report()["gap"])


def capability_record() -> Dict[str, Any]:
    """One row for the TOE expansion capability matrix."""
    report = _report()
    return {
        "status": "implemented",
        "truth_class": "finite_volume_spectrum",
        "claim": (
            "eigenvalue of the 2I quantum-group Laplacian; " "not the continuum Yang-Mills mass gap"
        ),
        "gap": report["gap"],
        "evidence_class": report["evidence_class"],
        "proof_claim": False,
        "continuum_claim": False,
    }


def join_summary() -> Dict[str, Any]:
    """Compact spectrum the enhanced TOE facets can carry."""
    report = _report()
    return {
        "available": True,
        "group": "2I",
        "order": report["group_order"],
        "poincare_homology_sphere": "Sigma(2,3,5) = S^3/2I",
        "distinct_from": "11D hyperbolic Poincare ball (sectional curvature -1)",
        "topology": report["topology"],
        "irrep_dimensions": report["dims"],
        "gap": report["gap"],
        "gap_exact_target": EXACT_GAP,
        "matches_one_minus_phi_over_two": abs(report["gap"] - EXACT_GAP) < 1e-6,
        "evidence_class": report["evidence_class"],
        "proof_claim": False,
        "continuum_claim": False,
        "scope": report["scope"],
    }


def unlocked_capabilities() -> Dict[str, Any]:
    """What the finite thread opens inside the TOE, and what stays shut.

    A capability is "unlocked" only when this process computed it. A capability
    is "locked" when the computation does not speak to it.
    """
    report = _report()
    gap = float(report["gap"])
    topology = report["topology"]
    levels = report["levels"]
    dims_ok = sorted(report["dims"]) == [1, 2, 2, 3, 3, 4, 4, 5, 6]
    mult_ok = sorted(level["multiplicity"] for level in levels) == sorted(
        d * d for d in report["dims"]
    )
    cell_ok = (
        topology["V"] == 120
        and topology["E"] == 720
        and topology["F"] == 1200
        and topology["C"] == 600
        and topology["euler"] == 0
    )
    gap_ok = (
        gap > 0.0
        and abs(gap - EXACT_GAP) < 1e-6
        and report["gap_algebraic"]
        == {
            "p": 1,
            "q": 1,
            "k": 4,
        }
    )

    def row(capability_id: str, opened: bool, was: str, now: str) -> Dict[str, Any]:
        return {
            "id": capability_id,
            "status": "unlocked" if opened else "locked",
            "was": was,
            "now": now,
        }

    unlocked: List[Dict[str, Any]] = [
        row(
            "finite_su2_spectrum",
            gap_ok and report["hermitian"] and report["inverse_closed"],
            "T10 was the predicate sqrt(5) > 0, which cannot fail",
            f"first positive eigenvalue of the 2I Laplacian, Delta = {gap:.8f}",
        ),
        row(
            "gauge_invariant_states",
            report["class_count"] == 9 and report["orthogonality"] and dims_ok,
            "no gauge-invariant Hilbert space was computed",
            "class functions on 2I: 9 irreps, character orthogonality, sum d^2 = |G|",
        ),
        row(
            "casimir_multiplicities",
            mult_ok and len(levels) == 9,
            "no representation-graded spectrum",
            "each Laplacian level has multiplicity d^2 for an irrep of dimension d",
        ),
        row(
            "six_hundred_cell",
            cell_ok,
            "icosahedral counts in telemetry were constants, not a complex",
            "600-cell computed: V-E+F-C = 0, the S^3 triangulation SU(2) discretizes",
        ),
        row(
            "phi_thread",
            gap_ok and all(item["pass"] for item in report["golden_checks"]),
            "Cassini (T1) and the Yang-Mills flag (T10) did not share a computation",
            "the same phi that satisfies Cassini is the real part of the order-10 edge class; Delta = 1 - phi/2",
        ),
        row(
            "two_poincares_distinguished",
            True,
            "one word, Poincare, covered both a homology sphere and a hyperbolic ball",
            "Sigma(2,3,5) = S^3/2I is computed here; the 11D ball of curvature -1 is a different geometry and is left alone",
        ),
    ]
    still_locked = [
        {
            "id": "continuum_yang_mills",
            "status": "locked",
            "reason": "a finite subgroup of SU(2) is not Yang-Mills theory on R^4; the Clay problem stays OPEN",
        },
        {
            "id": "share_acceptance",
            "status": "locked",
            "reason": "SHA256d versus target remains the only accept rule; this gap cannot submit a share",
        },
        {
            "id": "riemann_p_vs_np_bsd_hodge_navier_stokes",
            "status": "locked",
            "reason": "the 2I spectrum does not speak to those problems",
        },
        {
            "id": "device_throughput",
            "status": "locked",
            "reason": "no device was measured; physical acceleration stays hardware-gated",
        },
    ]
    return {
        "thread": "phi -> golden icosians -> 2I -> Sigma(2,3,5) -> SU(2) -> Casimir -> Delta",
        "gap": gap,
        "exact_form": "1 - phi/2 = 1/(2 phi^2) = (3 - sqrt(5))/4",
        "proof_claim": False,
        "continuum_claim": False,
        "evidence_class": report["evidence_class"],
        "unlocked": unlocked,
        "still_locked": still_locked,
        "unlocked_ids": [item["id"] for item in unlocked if item["status"] == "unlocked"],
        "locked_ids": [item["id"] for item in still_locked],
    }


__all__ = [
    "EXACT_GAP",
    "PHI",
    "capability_record",
    "finite_gauge_gap",
    "join_summary",
    "unlocked_capabilities",
]
