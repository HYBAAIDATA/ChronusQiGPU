"""EUCLID Unified Intelligence — Canonical Gatekeeper Subdomain.

Compatibility facade over existing capability owners. Production invocations use
EuclidRuntime.dispatch_specialist; this facade alone grants no runtime authority.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

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
    """Host-only facade; not a substitute for canonical runtime authorization.

    State transitions require an explicitly configured bridge. Capability
    dispatch below is the existing trusted-host registry API; externally
    requested work must use EuclidRuntime.dispatch_specialist.
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
        return ok, receipt, msg

    def dispatch_capability(
        self,
        capability_id: str,
        *,
        profile: ExecutionProfile,
        **kwargs: Any,
    ) -> Tuple[Any, Any]:
        """Trusted-host registry API, not the AL HARAS/creator-rights boundary."""
        output, receipt = self.registry.dispatch(
            capability_id,
            profile=profile,
            _strict_json=True,
            **kwargs,
        )
        self.audit_log.append(
            {
                "type": "CAPABILITY_EXECUTION",
                "receipt_id": receipt.receipt_id,
                "status": receipt.status,
                "capability_id": capability_id,
                "profile": profile.value,
                "timestamp_epoch": receipt.execution_timestamp,
            }
        )
        return output, receipt

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Return detached copy of the audit trail."""
        state_events = [
            {
                "type": "STATE_TRANSITION",
                "receipt_id": receipt.receipt_id,
                "status": receipt.status,
                "capability_id": receipt.capability_id,
                "caller_id": receipt.caller_id,
                "timestamp_epoch": receipt.timestamp_epoch,
                "state_hash": receipt.new_state_hash,
            }
            for receipt in self.state_bridge.audit_log
        ]
        return copy.deepcopy([*self.audit_log, *state_events])
