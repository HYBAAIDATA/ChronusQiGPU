"""Ovid — metamorphosis owner: folded data is the working form.

Canonical top-level module exposing Ovid data metamorphosis and working form transforms.
"""
from __future__ import annotations

from aethel.ovid import (
    CLAIM_BOUNDARY,
    CONTRACT_VERSION,
    EvidenceState,
    Exactness,
    FoldedWorkingForm,
    Ovid,
    TransformContract,
    TransformLineage,
    ZECKENDORF_TRANSFORM_ID,
    open_ovid,
)

__all__ = [
    "Ovid",
    "open_ovid",
    "CLAIM_BOUNDARY",
    "CONTRACT_VERSION",
    "Exactness",
    "EvidenceState",
    "TransformContract",
    "TransformLineage",
    "FoldedWorkingForm",
    "ZECKENDORF_TRANSFORM_ID",
]
