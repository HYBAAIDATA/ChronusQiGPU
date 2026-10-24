"""Recursive folding package initialization."""

from .recursive_folding import (
    RecursiveFolding,
    FROZEN_MAX_FOLD,
    FROZEN_MAX_FOLD_SIGNATURE,
    verify_frozen_max_fold,
    envelope_for_depth,
    threshold_for_depth,
)

__all__ = [
    "RecursiveFolding",
    "FROZEN_MAX_FOLD",
    "FROZEN_MAX_FOLD_SIGNATURE",
    "verify_frozen_max_fold",
    "envelope_for_depth",
    "threshold_for_depth",
]
