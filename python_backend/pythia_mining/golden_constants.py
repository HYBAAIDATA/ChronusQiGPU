# python_backend/pythia_mining/golden_constants.py
# Universal Constant Interface (UCI) — honest form.
#
# The spec's Phase 6 describes treating physical constants as mutable kernel
# variables to "manifest results". That is not an implementable claim and is
# NOT what this module does. What the architecture actually needs — and what
# this module provides — is a SINGLE, versioned, typed source of the
# mathematical constants the runtime genuinely uses, so that scaling
# assumptions cannot drift between modules. Constants here are immutable
# (frozen dataclass); a "kernel variable" version bump is explicit, recorded,
# and never silently rewrites a constant mid-run.

from __future__ import annotations

import math
from dataclasses import dataclass

UCI_VERSION = "uci-1.0"


@dataclass(frozen=True)
class GoldenConstants:
    """The mathematical constants of the golden/phi/Lucas runtime.

    Frozen: a constant required by a definition must be named, sourced,
    typed, and versioned. Mutating one is a version change, not a write.
    """

    version: str = UCI_VERSION

    # Golden ratio family — algebraic definitions, computed once.
    PHI: float = (1.0 + math.sqrt(5.0)) / 2.0
    INV_PHI: float = (math.sqrt(5.0) - 1.0) / 2.0  # 1/phi, exact definition
    PHI_15: float = ((1.0 + math.sqrt(5.0)) / 2.0) ** 15

    # Lucas numbers — exact integers, not floats.
    LUCAS_10: int = 123
    LUCAS_12: int = 322
    LUCAS_15: int = 1364
    LUCAS_18: int = 5778
    LUCAS_20: int = 15127

    # Pisot drift |phi^15 - L_15| — the irrational-rotation gap that keeps
    # the discrete dynamics ergodic (documented in AGENTS.md §1.8.3).
    PISOT_DRIFT_15: float = abs(((1.0 + math.sqrt(5.0)) / 2.0) ** 15 - 1364)

    # M32 topology.
    M32_FACES: int = 32
    M32_DODECAHEDRAL: int = 12
    M32_ICOSAHEDRAL: int = 20

    # Collapse/action thresholds used by the phi-grover machinery.
    PHI_COLLAPSE_THRESHOLD: float = (math.sqrt(5.0) - 1.0) / 2.0
    ACTION_THRESHOLD: float = 3.0 - ((1.0 + math.sqrt(5.0)) / 2.0)

    # Effective-rate ceiling (configured safety bound, NOT a physical rate).
    EFFECTIVE_RATE_CAP_EHS: float = 20.0

    def lucas(self, n: int) -> int:
        """Exact Lucas number L_n (integer arithmetic, no float drift)."""
        a, b = 2, 1
        if n == 0:
            return a
        for _ in range(n):
            a, b = b, a + b
        return a

    def as_dict(self) -> dict:
        return {
            "version": self.version,
            "PHI": self.PHI,
            "INV_PHI": self.INV_PHI,
            "PHI_15": self.PHI_15,
            "LUCAS_10": self.LUCAS_10,
            "LUCAS_12": self.LUCAS_12,
            "LUCAS_15": self.LUCAS_15,
            "LUCAS_18": self.LUCAS_18,
            "LUCAS_20": self.LUCAS_20,
            "PISOT_DRIFT_15": self.PISOT_DRIFT_15,
            "M32_FACES": self.M32_FACES,
            "M32_DODECAHEDRAL": self.M32_DODECAHEDRAL,
            "M32_ICOSAHEDRAL": self.M32_ICOSAHEDRAL,
            "PHI_COLLAPSE_THRESHOLD": self.PHI_COLLAPSE_THRESHOLD,
            "ACTION_THRESHOLD": self.ACTION_THRESHOLD,
            "EFFECTIVE_RATE_CAP_EHS": self.EFFECTIVE_RATE_CAP_EHS,
        }


GOLDEN_CONSTANTS = GoldenConstants()
