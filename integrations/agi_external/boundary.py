"""Boundary enforcement for the external AGI surface.

Raises if any forbidden internal module is present in sys.modules
at the moment an external AGI call begins. This is a runtime check,
not a comment.
"""

from __future__ import annotations

import sys
from typing import FrozenSet

# Modules that must never be loaded when serving external AGI.
FORBIDDEN_PREFIXES: FrozenSet[str] = frozenset({
    "Intelligence.asi",
    "Intelligence.consciousness",
    "agi.autonomous_learning",
    "agi.autonomy",
})


class BoundaryViolation(Exception):
    """Raised when an external AGI path has loaded an internal ASI module."""


def assert_external_boundary() -> None:
    """Call at the start of every external AGI entry point."""
    loaded = set(sys.modules.keys())
    violations = [
        name for name in loaded
        if any(name == p or name.startswith(p + ".") for p in FORBIDDEN_PREFIXES)
    ]
    if violations:
        raise BoundaryViolation(
            f"External AGI boundary violated; forbidden modules loaded: {violations}"
        )
