"""EUCLID Unified Intelligence — Cognition & Formal Reasoning Subdomain.

Consolidates empirical state control, mathematical conjecture and proof tracking,
governed repository review, Socratic loops, and ASI dimension reasoning.
"""
from __future__ import annotations

import importlib
from typing import Any

from euclid.capabilities.empirical_state_bridge import (
    EmpiricalStateController,
    EmpiricalStateBridge,
    StateTransitionRequest,
    AuditReceipt,
)

__all__ = [
    # Empirical State & Native Bridge
    "EmpiricalStateController",
    "EmpiricalStateBridge",
    "StateTransitionRequest",
    "AuditReceipt",
    # Mathematical Research & Proof Tracking
    "MathematicalProofTracker",
    "register_proof_capability",
    # Governed Repository Review
    "repository_review",
    "repository_review_capability",
    # Memory & Learning
    "PythiaMemorySystem",
    "PythiaLearning",
]

_SUBMODULE_MAP = {
    "repository_review": "Intelligence.repository_review",
    "repository_review_capability": "Intelligence.repository_review_capability",
}


def __getattr__(name: str) -> Any:
    if name == "MathematicalProofTracker":
        from Intelligence.mathematical_research import MathematicalProofTracker
        return MathematicalProofTracker

    if name == "register_proof_capability":
        from Intelligence.proof_capability import register_proof_capability
        return register_proof_capability

    if name == "PythiaMemorySystem":
        from Intelligence.pythia_memory import PythiaMemorySystem
        return PythiaMemorySystem

    if name == "PythiaLearning":
        from Intelligence.pythia_learning import PythiaLearning
        return PythiaLearning

    if name in _SUBMODULE_MAP:
        return importlib.import_module(_SUBMODULE_MAP[name])

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
