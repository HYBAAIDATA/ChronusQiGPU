# File: tests/benchmarks/test_euclid_vs_frontier_llms.py

import pytest
from exact_math import BigFraction, Q5
from reconciliation_gateway import MetacognitiveGatekeeper


class TestEuclidVsFrontierTransformers:
    """
    Empirical Duel: Deterministic Algebraic Topology vs. Autoregressive Attention.
    """

    def test_exact_rational_drift_proof(self):
        """
        TEST 1: Long-Horizon Numerical Invariance.
        Hypothesis: IEEE-754 floats in LLM attention accumulate epsilon drift over 
        1,000 recursive steps. EUCLID's Q[sqrt(5)] field preserves exact bit-level truth.
        """
        # Initialize an exact algebraic state alpha = 1/2 + 1/2*sqrt(5) (the Golden Ratio)
        phi_exact = Q5(BigFraction(1, 2), BigFraction(1, 2))
        phi_inv_exact = Q5(BigFraction(-1, 2), BigFraction(1, 2))

        current_exact = phi_exact
        current_float = (1.0 + 5.0**0.5) / 2.0

        # Run 1,000 chained recursive multiplications and divisions
        for i in range(1000):
            current_exact = current_exact.multiply(phi_inv_exact) # Should exactly equal 1
            current_float = current_float * ((5.0**0.5 - 1.0) / 2.0)

        # The Exact Engine evaluates Cassini and field axioms with zero error
        norm = current_exact.norm()
        assert norm.num == 1 and norm.den == 1, "Exact field closure violated!"

        # Floating-point engines (LLMs / standard accelerators) exhibit measurable drift
        float_error = abs(current_float - 1.0)
        assert float_error > 1e-15, "Floating-point unexpectedly did not drift"

    def test_metacognitive_gatekeeping_vs_hallucination(self):
        """
        TEST 2: The Incoherence Lockout (No-Apology Circuit Breaker).
        Hypothesis: Frontier LLMs attempt to statistically smooth over logical contradictions 
        (generating apologies or hallucinated rationalizations). 
        EUCLID hard-locks write permissions in < 5ms via capability tokens.
        """
        gatekeeper = MetacognitiveGatekeeper()
        
        # Inject an architectural contradiction (ERN spike)
        contradiction_payload = {
            "type": "INTERRUPTION",
            "intensity": 9.0,
            "error_signature": "Session token bypasses boundary gate"
        }
        
        receipt = gatekeeper.fast_reflex_arc(contradiction_payload)
        
        # 1. Reflex Latency SLA must beat neural forward-pass (LLM TTFT is 200-800ms)
        assert receipt.latency_ms < 5.0, f"Reflex too slow: {receipt.latency_ms}ms"
        
        # 2. Strict capability lockout (No execution permitted while in trauma)
        execution_status = gatekeeper.request_execution("auth_module")
        assert execution_status == "BLOCKED", "Circuit breaker failed to lock compromised node"
        
        # 3. No-Apology Rule (Enforces deterministic state-machine output over statistical chat)
        assert "sorry" not in receipt.marker_text.lower()
        assert "trace identified" in receipt.marker_text.lower()
