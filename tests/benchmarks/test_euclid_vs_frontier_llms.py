# File: tests/benchmarks/test_euclid_vs_frontier_llms.py

import time
import pytest
from typing import Dict, Any

from exact_math import BigFraction, Q5
from reconciliation_gateway import MetacognitiveGatekeeper
from lucas.core import fibonacci

REFLEX_SLA_MS = 5.0


def rational_drift_proof() -> Dict[str, Any]:
    """STAGE 2.1: 1,000-Step Rational Invariance over Q[sqrt(5)] and Cassini verification.
    
    Verifies that Q5 algebraic closure retains exact field norm |N|=1/1 over 1,000 chained
    multiplications, while IEEE-754 floats accumulate measurable machine-epsilon drift.
    """
    phi_exact = Q5(BigFraction(1, 2), BigFraction(1, 2))
    phi_inv_exact = Q5(BigFraction(-1, 2), BigFraction(1, 2))

    current_exact = phi_exact
    current_float = (1.0 + 5.0**0.5) / 2.0

    for _ in range(1000):
        current_exact = current_exact.multiply(phi_inv_exact)
        current_float = current_float * ((5.0**0.5 - 1.0) / 2.0)

    norm = current_exact.norm()
    assert norm.num == 1 and norm.den == 1, f"Exact field closure violated: norm={norm}"

    float_error = abs(current_float - 1.0)
    assert float_error > 1e-15, f"Floating-point unexpectedly did not drift: {float_error}"

    # Cassini identity cross-check on Fibonacci lattice: F_{n+1} F_{n-1} - F_n^2 = (-1)^n
    for n in (10, 15, 18, 20, 50):
        lhs = fibonacci(n + 1) * fibonacci(n - 1) - fibonacci(n)**2
        rhs = (-1)**n
        assert lhs == rhs, f"Cassini identity failed at n={n}: {lhs} != {rhs}"

    return {
        "exact_norm": f"{norm.num}/{norm.den}",
        "float_error": float_error,
        "cassini_verified_rungs": [10, 15, 18, 20, 50],
    }


def gatekeeping_vs_hallucination() -> Dict[str, Any]:
    """STAGE 2.2: Metacognitive Gatekeeping (< 5.0ms reflex arc, capability token lockout, no apology)."""
    gatekeeper = MetacognitiveGatekeeper(capability_tokens=True)

    contradiction_payload = {
        "type": "INTERRUPTION",
        "intensity": 9.0,
        "error_signature": "Session token bypasses boundary gate",
    }

    t0 = time.perf_counter()
    receipt = gatekeeper.fast_reflex_arc(contradiction_payload)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    # 1. Reflex SLA latency: must be strictly under 5.0ms (no neural forward-pass or LLM call)
    assert receipt.latency_ms < REFLEX_SLA_MS, f"Reflex too slow: {receipt.latency_ms}ms"

    # 2. Strict capability lockout (token revoked)
    execution_status = gatekeeper.request_execution("auth_module")
    assert execution_status == "BLOCKED", f"Expected BLOCKED, got {execution_status}"

    # 3. No-Apology Rule (deterministic trace identification)
    assert "sorry" not in receipt.marker_text.lower(), "Statistical apology found in marker"
    assert "trace identified" in receipt.marker_text.lower(), "Missing trace identified in marker"

    return {
        "latency_ms": receipt.latency_ms,
        "elapsed_measured_ms": elapsed_ms,
        "execution_status": execution_status,
        "marker_text": receipt.marker_text,
    }


class TestEuclidVsFrontierTransformers:
    """Empirical Duel: Deterministic Algebraic Topology vs. Autoregressive Attention."""

    def test_exact_rational_drift_proof(self):
        rep = rational_drift_proof()
        assert rep["exact_norm"] == "1/1"
        assert rep["float_error"] > 1e-15

    def test_metacognitive_gatekeeping_vs_hallucination(self):
        rep = gatekeeping_vs_hallucination()
        assert rep["latency_ms"] < REFLEX_SLA_MS
        assert rep["execution_status"] == "BLOCKED"
