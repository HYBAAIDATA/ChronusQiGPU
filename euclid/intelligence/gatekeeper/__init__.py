"""EUCLID Unified Intelligence — Canonical Gatekeeper Submodule."""
from __future__ import annotations

from typing import Any
import Intelligence.gatekeeper as _gatekeeper

from Intelligence.gatekeeper import (
    UnifiedIntelligenceGatekeeper,
    CapabilityRegistry,
    CapabilityManifest,
    ExecutionProfile,
    DeterminismClass,
    SideEffectClass,
    ResourceBudget,
    AuthorizationDenied,
    CapabilityExecutionError,
    EmpiricalStateBridge,
    EmpiricalStateController,
    StateTransitionRequest,
    AuditReceipt,
)

__all__ = [
    "UnifiedIntelligenceGatekeeper",
    "CapabilityRegistry",
    "CapabilityManifest",
    "ExecutionProfile",
    "DeterminismClass",
    "SideEffectClass",
    "ResourceBudget",
    "AuthorizationDenied",
    "CapabilityExecutionError",
    "EmpiricalStateBridge",
    "EmpiricalStateController",
    "StateTransitionRequest",
    "AuditReceipt",
]


def __getattr__(name: str) -> Any:
    return getattr(_gatekeeper, name)


def __dir__():
    return sorted(set(globals()) | set(__all__) | set(dir(_gatekeeper)))
