"""Bounded empirical state transitions over host-owned authorization and custody.

This compatibility controller is not a learner, RewardAuthority, or mining SCM.
It stores only operational reliability state. The host supplies the existing
AL HARAS ledger and shared persistent EUCLID data port; no private store is opened.
One host writer owns a state stream. Cross-process/distributed transactions and
hard preemption are not provided. Uncertain publication blocks subsequent writes
and requires operator reconciliation; it must never be retried as a rollback.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
import threading
import time
from typing import Any, Callable
import uuid


@dataclass(frozen=True)
class StateTransitionRequest:
    capability_id: str
    caller_id: str
    transition_type: str
    state_payload: dict[str, Any]
    deadline_epoch: float
    max_budget: int
    operator_token: str


@dataclass(frozen=True)
class AuditReceipt:
    receipt_id: str
    status: str
    new_state_hash: str
    capability_id: str
    caller_id: str
    timestamp_epoch: float
    transition_type: str
    budget_consumed: int


class StateCommitUncertain(RuntimeError):
    """Publication may have occurred; stop and reconcile custody with the audit."""


def _bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _hash(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _state(value: Any) -> dict:
    if type(value) is not dict or set(value) != {"version", "reliability_weights"}:
        raise ValueError("invalid operational state shape")
    if type(value["version"]) is not int or value["version"] < 1:
        raise ValueError("invalid operational state version")
    weights = value["reliability_weights"]
    if type(weights) is not dict or len(weights) > 1024:
        raise ValueError("invalid reliability weights")
    for domain, weight in weights.items():
        if type(domain) is not str or re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", domain) is None:
            raise ValueError("invalid reliability domain")
        if type(weight) not in (int, float) or not math.isfinite(weight) or not 0 <= weight <= 1:
            raise ValueError("weight must be a finite number in [0, 1]")
    return copy.deepcopy(value)


class EmpiricalStateController:
    """Operational weights only; no prior memories or identity are imported."""

    def __init__(self, initial_state: dict | None = None):
        self.state = _state(
            initial_state
            if initial_state is not None
            else {
                "reliability_weights": {"atomic": 1.0},
                "version": 1,
            }
        )

    def apply(self, req: StateTransitionRequest) -> None:
        if req.transition_type != "UPDATE_RELIABILITY":
            raise ValueError("unsupported transition")
        if type(req.state_payload) is not dict or set(req.state_payload) != {"domain", "weight"}:
            raise ValueError("domain and weight are required")
        domain, weight = req.state_payload["domain"], req.state_payload["weight"]
        candidate = copy.deepcopy(self.state)
        # Validate before using a caller value as a dictionary key.
        _state({"version": 1, "reliability_weights": {domain: weight}})
        candidate["reliability_weights"][domain] = weight
        candidate["version"] += 1
        self.state = _state(candidate)


class EmpiricalStateBridge:
    """Fail closed unless authorization, durable audit and shared custody exist."""

    APPROVED_CAPABILITY_ID = "host:capability:empirical_state_controller"
    STATE_KIND = "euclid.empirical-operational-state.v1"

    def __init__(
        self,
        controller: EmpiricalStateController | None = None,
        *,
        authorizer: Callable[[StateTransitionRequest], bool] | None = None,
        audit: Any = None,
        data_port: Any = None,
        owner_id: str = "host",
    ):
        if type(owner_id) is not str or not 1 <= len(owner_id) <= 128:
            raise ValueError("bounded host owner identifier required")
        self.owner_id = owner_id
        self.controller = controller if controller is not None else EmpiricalStateController()
        self.authorizer, self.audit, self.data_port = authorizer, audit, data_port
        self._lock = threading.RLock()
        self._uncertain = False
        self._binding_id = None
        if data_port is not None:
            self._restore()

    @property
    def audit_log(self) -> list[AuditReceipt]:
        if self.audit is None:
            return []
        return [
            AuditReceipt(**r["event"]["receipt"])
            for r in self.audit.records
            if r["event"].get("schema") == "euclid.empirical-transition/1"
            and r["event"].get("phase") == "COMMITTED"
        ]

    def _restore(self) -> None:
        binding = self.data_port.latest(self.STATE_KIND)
        if binding is None:
            return
        envelope = json.loads(self.data_port.read(binding.binding_id))
        if (
            type(envelope) is not dict
            or set(envelope) != {"schema", "state", "receipt", "owner_id"}
            or envelope["schema"] != self.STATE_KIND
            or envelope["owner_id"] != self.owner_id
        ):
            raise ValueError("invalid empirical custody envelope")
        state = _state(envelope["state"])
        receipt = AuditReceipt(**envelope["receipt"])
        if receipt.status != "COMMITTED" or receipt.new_state_hash != _hash(state):
            raise ValueError("empirical custody state digest mismatch")
        if receipt not in self.audit_log:
            raise StateCommitUncertain("custody publication has no matching durable completion")
        self.controller.state = state
        self._binding_id = binding.binding_id

    def _event(self, phase: str, req: StateTransitionRequest, execution_id: str, **fields):
        # Never write tokens or arbitrary client payloads to the audit spool.
        return self.audit.append(
            {
                "schema": "euclid.empirical-transition/1",
                "phase": phase,
                "execution_id": execution_id,
                "capability_id": req.capability_id,
                "caller_id": req.caller_id,
                **fields,
            }
        )

    def dispatch(self, req: StateTransitionRequest) -> tuple[bool, AuditReceipt | None, str]:
        with self._lock:
            return self._dispatch(req)

    def _dispatch(self, req):
        if self._uncertain:
            raise StateCommitUncertain("writer quarantined after uncertain publication")
        if type(req) is not StateTransitionRequest:
            return False, None, "INVALID_REQUEST"
        if req.capability_id != self.APPROVED_CAPABILITY_ID:
            return False, None, "FORBIDDEN_CAPABILITY"
        if type(req.max_budget) is not int or req.max_budget <= 0:
            return False, None, "BUDGET_EXHAUSTED"
        if (
            type(req.deadline_epoch) not in (float, int)
            or not math.isfinite(req.deadline_epoch)
            or req.deadline_epoch <= time.time()
        ):
            return False, None, "DEADLINE_EXPIRED"
        if (
            type(req.caller_id) is not str
            or not 1 <= len(req.caller_id) <= 128
            or type(req.operator_token) is not str
            or not req.operator_token
        ):
            return False, None, "UNAUTHORIZED_OPERATOR_TOKEN"
        if (
            not callable(self.authorizer)
            or self.audit is None
            or self.data_port is None
            or getattr(self.audit, "path", None) is None
        ):
            return False, None, "GOVERNANCE_UNAVAILABLE"
        req = copy.deepcopy(req)
        try:
            authorized = self.authorizer(copy.deepcopy(req)) is True
        except Exception:
            authorized = False
        if not authorized:
            return False, None, "UNAUTHORIZED_OPERATOR_TOKEN"
        latest = self.data_port.latest(self.STATE_KIND)
        if (latest.binding_id if latest else None) != self._binding_id:
            raise StateCommitUncertain("stale writer; reopen against current custody")
        before = _state(self.controller.state)
        execution_id = uuid.uuid4().hex
        self._event("ADMITTED", req, execution_id, prior_state_hash=_hash(before))
        try:
            if req.deadline_epoch <= time.time():
                raise TimeoutError("deadline expired before execution")
            self.controller.apply(req)
            candidate = _state(self.controller.state)
            if req.deadline_epoch <= time.time():
                raise TimeoutError("deadline expired after execution")
        except Exception:
            self.controller.state = copy.deepcopy(before)
            if _hash(self.controller.state) != _hash(before):
                raise RuntimeError("rollback verification failed")
            self._event("ROLLED_BACK", req, execution_id, prior_state_hash=_hash(before))
            return False, None, "EXECUTION_FAILED_ROLLED_BACK"
        receipt = AuditReceipt(
            "rcpt_" + execution_id,
            "COMMITTED",
            _hash(candidate),
            req.capability_id,
            req.caller_id,
            time.time(),
            req.transition_type,
            1,
        )
        envelope = {
            "schema": self.STATE_KIND,
            "owner_id": self.owner_id,
            "state": candidate,
            "receipt": asdict(receipt),
        }
        try:
            binding = self.data_port.put(
                self.STATE_KIND,
                _bytes(envelope),
                parents=(self._binding_id,) if self._binding_id else (),
            )
            if self.data_port.read(binding.binding_id) != _bytes(envelope):
                raise ValueError("custody readback mismatch")
            if req.deadline_epoch <= time.time():
                raise TimeoutError("deadline expired during custody publication")
            self._event(
                "COMMITTED",
                req,
                execution_id,
                receipt=asdict(receipt),
                custody_binding_id=binding.binding_id,
            )
        except Exception as exc:
            # A store may publish and then raise. Neither retry nor a dictionary
            # rollback can honestly erase that durable side effect.
            self._uncertain = True
            raise StateCommitUncertain(
                "publication/completion uncertain; reconcile before retry"
            ) from exc
        self._binding_id = binding.binding_id
        return True, receipt, "COMMITTED"
