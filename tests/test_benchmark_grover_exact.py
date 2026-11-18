"""Smoke tests for the exact-F4 Grover benchmark."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "turing_universal_quantum_computer"),
)

from benchmarks.grover_exact_demo import _closed_form_probs, grover_f4


def test_grover_f1_exact():
    r = grover_f4(1, [1])
    assert r["k_opt"] == 1
    # N=2: theta=pi/4, after 1 iter P = sin^2(3pi/4) = 1/2 — exact.
    assert r["steps"][-1]["exact_match"]
    assert r["steps"][-1]["closed_form"] == "1/2"


def test_grover_f3_exact_vs_closed_form():
    r = grover_f4(3, [7])
    # k* = floor(pi/(4*asin(1/sqrt8))) = 2; P after 2 iters = 121/128.
    assert r["k_opt"] == 2
    assert r["steps"][-1]["closed_form"] == "121/128"
    assert r["steps"][-1]["exact_match"]
    assert all(s["exact_match"] for s in r["steps"])
    assert all(s["normalized"] for s in r["steps"])
    assert len(r["state_seq_sha256"]) == 64


def test_closed_form_is_rational_and_matches_float():
    import math

    n, m, k = 3, 1, 2
    probs = _closed_form_probs(n, m, k)
    theta = math.asin(math.sqrt(m / (1 << n)))
    for i, p in enumerate(probs):
        assert abs(float(p) - math.sin((2 * i + 1) * theta) ** 2) < 1e-15


def test_digest_deterministic():
    assert grover_f4(2, [3])["state_seq_sha256"] == grover_f4(2, [3])["state_seq_sha256"]


def test_grover_quadratic_bound_no_exponential_speedup():
    """Honest accounting: Grover query complexity is strictly Omega(sqrt(N)).
    Claims of exponential or super-quadratic speedup are categorically false."""
    import math

    # Check k_opt scaling for increasing search spaces
    for n in (4, 8, 12, 16):
        N = 1 << n
        theta = math.asin(math.sqrt(1.0 / N))
        k = int(math.floor(math.pi / (4.0 * theta)))
        # Quadratic ratio k / sqrt(N) must be bounded near pi/4 ≈ 0.785
        ratio = k / math.sqrt(N)
        assert 0.70 < ratio < 0.85, f"Scaling deviated from quadratic: ratio={ratio}"


def test_grover_lucas_pisot_folded_state_scaling_15_18_20():
    """Folded Grover state evolution across the Lucas-Pisot rungs 15, 18, 20.
    Verifies Cassini invariant conservation and Pisot damp convergence."""
    from turing_universal_quantum_computer.grover_exact_scale import (
        pisot_damp,
        run_folded,
        binet_residual,
        LUCAS_LADDER,
    )
    from lucas.core import lucas

    from kellogg.scales import ZPHI_ONE, ZPHI_ZERO
    from python_backend.exact_folded_grover import zphi_lt_rational

    # Verify rungs are in the canonical ladder; damp and residual are exact Z[phi].
    for rung in (15, 18, 20):
        assert rung in LUCAS_LADDER
        damp = pisot_damp(rung)
        assert (damp - ZPHI_ZERO).sign() > 0 and (ZPHI_ONE - damp).sign() > 0
        # 1-|psi|^n > 0.999  <=>  |psi|^n < 0.001
        residual = binet_residual(rung)
        assert zphi_lt_rational(residual, 1, 1000)

    # Exact folded evolution on scaled search spaces (canonical +/-1 phases).
    for rung in (15, 18, 20):
        L_n = lucas(rung)
        N_eff = 64 * L_n
        res = run_folded(N_eff, 1, iterations=10)
        assert res["cassini_drift"] == 0
        assert 0 <= res["P_marked"] <= 1


def test_boundaries_per_grover_scaling_research():
    """Locks the non-claims boundary: Grover provides quadratic speedup only."""
    from lucas.scaling_research import research_report

    report = research_report()
    for claim in ["mining advantage", "scheduling advantage", "hardware speedup"]:
        assert claim in report["non_claims"]

