"""EUCLID Unified Intelligence — Canonical Gatekeeper Subdomain.

Consolidates AL HARAS pre-execution audit, host authorization, budget enforcement,
and verified rollback into a single atomic gatekeeper for all capabilities.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from Intelligence.capability_fabric import (
    AuthorizationDenied,
    CapabilityExecutionError,
    CapabilityManifest,
    CapabilityPermissions,
    CapabilityRegistrationError,
    CapabilityRegistry,
    DeterminismClass,
    ExecutionProfile,
    ResourceBudget,
    SideEffectClass,
    snapshot_json,
)
from euclid.capabilities.empirical_state_bridge import (
    AuditReceipt,
    EmpiricalStateBridge,
    EmpiricalStateController,
    StateTransitionRequest,
)

__all__ = [
    # Fabric primitives
    "AuthorizationDenied",
    "CapabilityExecutionError",
    "CapabilityManifest",
    "CapabilityPermissions",
    "CapabilityRegistrationError",
    "CapabilityRegistry",
    "DeterminismClass",
    "ExecutionProfile",
    "ResourceBudget",
    "SideEffectClass",
    "snapshot_json",
    # Empirical state bridge primitives
    "AuditReceipt",
    "EmpiricalStateBridge",
    "EmpiricalStateController",
    "StateTransitionRequest",
    # Unified Gatekeeper Facade
    "UnifiedIntelligenceGatekeeper",
]


class UnifiedIntelligenceGatekeeper:
    """Single canonical gatekeeper routing all intelligence operations (physics and cognition).

    Enforces:
    1. Caller authorization and execution profile boundaries.
    2. Atomic capability manifest inspection and admission.
    3. Resource budget limits and deadline guards.
    4. Immutable SHA-256 pre-execution state hashing.
    5. Verified rollback on execution exception.
    """

    def __init__(
        self,
        registry: Optional[CapabilityRegistry] = None,
        state_bridge: Optional[EmpiricalStateBridge] = None,
    ) -> None:
        self.registry = registry if registry is not None else CapabilityRegistry()
        self.state_bridge = state_bridge if state_bridge is not None else EmpiricalStateBridge()
        self.audit_log: List[Dict[str, Any]] = []

    def dispatch_state_transition(
        self, req: StateTransitionRequest
    ) -> Tuple[bool, Optional[AuditReceipt], str]:
        """Dispatch a state transition request through the native empirical state bridge."""
        ok, receipt, msg = self.state_bridge.dispatch(req)
        if ok and receipt:
            self.audit_log.append({
                "type": "STATE_TRANSITION",
                "receipt_id": receipt.receipt_id,
                "status": receipt.status,
                "capability_id": req.capability_id,
                "caller_id": req.caller_id,
                "timestamp_epoch": receipt.timestamp_epoch,
                "state_hash": receipt.new_state_hash,
            })
        return ok, receipt, msg

    def dispatch_capability(
        self,
        capability_id: str,
        *,
        profile: ExecutionProfile,
        **kwargs: Any,
    ) -> Tuple[Any, Any]:
        """Dispatch an registered capability through the atomic capability registry."""
        output, receipt = self.registry.dispatch(
            capability_id,
            profile=profile,
            _strict_json=True,
            **kwargs,
        )
        self.audit_log.append({
            "type": "CAPABILITY_EXECUTION",
            "receipt_id": receipt.receipt_id,
            "status": receipt.status,
            "capability_id": capability_id,
            "profile": profile.value,
            "timestamp_epoch": receipt.execution_timestamp,
        })
        return output, receipt

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Return detached copy of the audit trail."""
        return copy.deepcopy(self.audit_log)
