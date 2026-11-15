"""PCI Directive Integration Test: Predictive Engine & Architectural Purity.

Verifies:
1. Strict separation between classical telemetry (is_quantum=False) and exact quantum substrate.
2. Decision margin (|2p - 1|) without artificial re-sigmoiding.
3. Feature importances keyed by index f0..fN.
4. Exact Born-rule bridge gated strictly on caller-provided normalized amplitudes:
   - aggregation="born_rule" without amplitudes raises RuntimeError (no synthetic quantum state).
   - unnormalized amplitudes raise ValueError.
   - valid amplitudes yield exact Born measurement P = |<i|psi>|^2 with is_quantum=True.
"""

from __future__ import annotations

import unittest

from chronus.intelligence.predictive_engine import (
    TestPredictiveEngine as TestPCIPredictiveEngineSuite,
)

__all__ = ["TestPCIPredictiveEngineSuite"]

if __name__ == "__main__":
    unittest.main()
