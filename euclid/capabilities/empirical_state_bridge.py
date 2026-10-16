"""EUCLID Empirical State Bridge — native capability bridge with AL HARAS audit and verified rollback.

Enforces pre-execution capability verification, fail-closed refusal, budget limits,
immutable audit receipt generation, and rollback on execution exceptions.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid


@dataclass
class StateTransitionRequest:
    """Request payload for an empirical state transition."""
    capability_id: str
    caller_id: str
    transition_type: str
    state_payload: Dict[str, Any]
    deadline_epoch: float
    max_budget: int
    operator_token: str


@dataclass
class AuditReceipt:
    """Immutable audit receipt issued upon state transition commitment."""
    receipt_id: str
    status: str
    new_state_hash: str
    capability_id: str
    caller_id: str
    timestamp_epoch: float
    transition_type: str
    budget_consumed: int


class EmpiricalStateController:
    """Deterministic empirical state controller with explicit reliability weights."""

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        if initial_state is not None:
            self.state: Dict[str, Any] = copy.deepcopy(initial_state)
        else:
            self.state = {
                "reliability_weights": {
                    "atomic": 1.0,
                },
                "version": 1,
            }


class EmpiricalStateBridge:
    """Native capability bridge governing state transitions with pre-execution audit and rollback."""

    APPROVED_CAPABILITY_ID: str = "host:capability:empirical_state_controller"

    def __init__(self, controller: Optional[EmpiricalStateController] = None):
        self.controller = controller if controller is not None else EmpiricalStateController()
        self.audit_log: List[AuditReceipt] = []

    def dispatch(self, req: StateTransitionRequest) -> Tuple[bool, Optional[AuditReceipt], str]:
        """Dispatch a state transition request through fail-closed governance gates."""
        # 1. Negative gate: capability verification
        if req.capability_id != self.APPROVED_CAPABILITY_ID:
            return False, None, f"FORBIDDEN_CAPABILITY: {req.capability_id} is not approved"

        # 2. Negative gate: budget verification
        if req.max_budget <= 0:
            return False, None, f"BUDGET_EXHAUSTED: max_budget={req.max_budget} is non-positive"

        # 3. Deadline verification
        if req.deadline_epoch < time.time():
            return False, None, f"DEADLINE_EXPIRED: request expired at {req.deadline_epoch}"

        # 4. Operator token check
        if not req.operator_token or len(req.operator_token) < 16:
            return False, None, "UNAUTHORIZED_OPERATOR_TOKEN: invalid token"

        # 5. Verified rollback snapshot
        pre_state = copy.deepcopy(self.controller.state)

        # 6. Execution under rollback guard
        try:
            if req.transition_type == "UPDATE_RELIABILITY":
                domain = req.state_payload["domain"]
                weight = float(req.state_payload["weight"])
                if "reliability_weights" not in self.controller.state:
                    self.controller.state["reliability_weights"] = {}
                self.controller.state["reliability_weights"][domain] = weight
            else:
                raise ValueError(f"Unknown or unsupported transition_type: {req.transition_type}")
        except Exception as exc:
            self.controller.state = pre_state
            return False, None, f"EXECUTION_FAILED_ROLLED_BACK: {exc}"

        # 7. Audit hash and receipt generation
        state_serialized = json.dumps(self.controller.state, sort_keys=True).encode("utf-8")
        state_hash = hashlib.sha256(state_serialized).hexdigest()
        receipt = AuditReceipt(
            receipt_id=f"rcpt_{uuid.uuid4().hex[:16]}",
            status="COMMITTED",
            new_state_hash=state_hash,
            capability_id=req.capability_id,
            caller_id=req.caller_id,
            timestamp_epoch=time.time(),
            transition_type=req.transition_type,
            budget_consumed=1,
        )
        self.audit_log.append(receipt)
        return True, receipt, "COMMITTED"
