"""Fail-closed AL HARAS authorization capability."""

from __future__ import annotations

import math
import time
from typing import Any, Callable

from .common import SkillError

SKILL_ID = "security.verify_authority"
TITLE = "Verify a capability against the configured AL HARAS boundary"
SOURCE = "AL HARAS Guardian/SubscriptionAuthority adapter (deployment supplied)"
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "identity": {"type": "string", "minLength": 1},
        "capability": {"type": "string", "minLength": 1},
        "lease_duration": {"type": "number", "minimum": 0.000001},
    },
    "required": ["identity", "capability", "lease_duration"],
    "additionalProperties": False,
}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "allowed": {"type": "boolean"},
        "reason": {"type": "string"},
        "audit_record": {"type": "object"},
    },
    "required": ["allowed", "reason", "audit_record"],
}
COST_ESTIMATE = 1
RISK_LEVEL = 0.05
TIME_ESTIMATE = 1.0
EXAMPLES = (
    {
        "input": {
            "identity": "operator-1",
            "capability": "reasoning.causal_explain",
            "lease_duration": 60,
        },
        "output": {"allowed": False, "reason": "denied by default", "audit_record": {}},
    },
)
LIMITATIONS = (
    "No AL HARAS credential, tenant, or lease issuer is bundled; without a configured authorizer the answer is denied.",
    "A positive result authorizes only the named capability for the supplied lease duration; it grants no proof or execution rights.",
)


def run(
    identity: str,
    capability: str,
    lease_duration: float,
    *,
    authorizer: Callable[[str, str, dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Request a decision from a deployment-supplied authorization boundary."""
    if not identity.strip() or not capability.strip():
        raise SkillError("identity and capability are required")
    if (
        isinstance(lease_duration, bool)
        or not isinstance(lease_duration, (int, float))
        or not math.isfinite(lease_duration)
        or lease_duration <= 0
    ):
        raise SkillError("lease_duration must be greater than zero")
    if authorizer is None:
        return {
            "allowed": False,
            "reason": "AL HARAS authorizer unavailable; denied by default",
            "audit_record": {
                "identity": identity,
                "capability": capability,
                "lease_duration": lease_duration,
                "evaluated_at": time.time(),
                "allowed": False,
            },
        }
    try:
        verdict = authorizer(
            identity,
            capability,
            {"lease_duration": lease_duration},
        )
    except Exception as exc:
        raise SkillError(f"AL HARAS authorization failed closed: {exc}") from exc
    if isinstance(verdict, tuple):
        allowed = verdict[0] is True
        reason = str(verdict[1]) if len(verdict) > 1 else ("allowed" if allowed else "denied")
        record = verdict[2] if len(verdict) > 2 and isinstance(verdict[2], dict) else {}
    elif isinstance(verdict, dict):
        allowed = verdict.get("allowed") is True
        reason = str(verdict.get("reason", "allowed" if allowed else "denied"))
        record = verdict.get("audit_record", {})
    else:
        allowed = verdict is True
        reason = "allowed" if allowed else "denied"
        record = {}
    return {
        "allowed": allowed,
        "reason": reason if allowed else f"denied: {reason}",
        "audit_record": {
            **record,
            "identity": identity,
            "capability": capability,
            "lease_duration": lease_duration,
            "evaluated_at": time.time(),
            "allowed": allowed,
        },
    }
