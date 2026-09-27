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
