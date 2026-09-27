"""HYBA unified punch host — re-export of the classical GPU compute substrate.

The implementation lives in :mod:`Intelligence.unified_punch` (LUCAS
WIRING purity: algorithm modules must not import siblings). This module
only re-exports it so ``hyba`` is the one import site for operators.
"""

from __future__ import annotations

from Intelligence.unified_punch import (
    UnifiedPhiRuntime,
    UnifiedPunchHost,
)

__all__ = [
    "UnifiedPhiRuntime",
    "UnifiedPunchHost",
]
