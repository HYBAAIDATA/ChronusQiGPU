"""EUCLID Unified Intelligence — Cognition & Formal Reasoning Submodule."""
from __future__ import annotations

from typing import Any
import Intelligence.cognition as _cognition

from euclid.capabilities.empirical_state_bridge import (
    EmpiricalStateController,
    EmpiricalStateBridge,
    StateTransitionRequest,
    AuditReceipt,
)

__all__ = [
    "EmpiricalStateController",
    "EmpiricalStateBridge",
    "StateTransitionRequest",
    "AuditReceipt",
    "MathematicalProofTracker",
    "register_proof_capability",
    "repository_review",
    "repository_review_capability",
    "PythiaMemorySystem",
    "PythiaLearning",
]


def __getattr__(name: str) -> Any:
    return getattr(_cognition, name)


def __dir__():
    return sorted(set(globals()) | set(__all__) | set(dir(_cognition)))
