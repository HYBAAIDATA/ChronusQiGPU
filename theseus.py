"""Theseus — self-healing prime-manifold storage owner.

Canonical top-level module exposing Theseus prime-manifold storage and self-healing custody.
"""
from __future__ import annotations

from aethel.theseus import (
    CLAIM_BOUNDARY,
    Theseus,
    TheseusError,
    TheseusRecord,
    open_theseus,
)
from aethel.triad import (
    TRIAD_CLAIM_BOUNDARY,
    Triad,
    open_triad,
)

__all__ = [
    "Theseus",
    "open_theseus",
    "TheseusRecord",
    "TheseusError",
    "CLAIM_BOUNDARY",
    "Triad",
    "open_triad",
    "TRIAD_CLAIM_BOUNDARY",
]
