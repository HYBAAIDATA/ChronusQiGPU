"""Opt-in PULVINI V3 research operator. Not a TURING or mining-authority API.

The exact-source operator is maintained under a protected research contract.
No caller may infer net storage savings from working-set reduction alone.
"""
from .formal import FoldState, PhiRecursiveOperator, ValidationError
from .interop import FoldEvidence, fold_verified, unfold_verified

__all__ = ["FoldState", "PhiRecursiveOperator", "ValidationError", "FoldEvidence", "fold_verified", "unfold_verified"]
