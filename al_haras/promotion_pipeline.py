"""Commit-bound promotion and separation-of-duties contracts."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import asdict
from dataclasses import dataclass
from typing import Iterable
from typing import Mapping

from .promotion_gates import PromotionState

ROLE_REQUIREMENTS = {
    PromotionState.VERIFIED: ("ARCH_OWNER", "EVIDENCE_OWNER"),
    PromotionState.PILOT: ("SECURITY_OWNER", "PRODUCT_OWNER"),
    PromotionState.PRODUCTION: ("SECURITY_OWNER", "COMPLIANCE_OWNER", "INDEPENDENT_REVIEWER"),
}


@dataclass(frozen=True)
class Approval:
    subsystem: str
    from_state: PromotionState
    to_state: PromotionState
    approver_role: str
    approver_identity: str
    approved_at: int
    evidence_commit: str
    reason: str
    source_url: str


@dataclass(frozen=True)
class PromotionReceipt:
    subsystem: str
    from_state: PromotionState
    to_state: PromotionState
    commit: str
    gate_result_hashes: tuple[str, ...]
    approvals: tuple[Approval, ...]
    issued_at: int
    signature_algorithm: str
    signature: str
    cedr_decision_digest: str = ""


class PromotionRejected(ValueError):
    pass


def required_roles(target: PromotionState) -> tuple[str, ...]:
    if target not in ROLE_REQUIREMENTS:
        raise PromotionRejected("only VERIFIED/PILOT/PRODUCTION can be promoted")
    return ROLE_REQUIREMENTS[target]


def validate_transition(current: PromotionState, target: PromotionState) -> None:
    allowed = {
        (PromotionState.CONTRACTED, PromotionState.VERIFIED),
        (PromotionState.REFERENCE, PromotionState.VERIFIED),
        (PromotionState.VERIFIED, PromotionState.PILOT),
        (PromotionState.PILOT, PromotionState.PRODUCTION),
    }
    if (current, target) not in allowed:
        raise PromotionRejected("invalid governed promotion transition")


def enforce_sod(
    subsystem,
    current,
    target,
    commit,
    authors: Iterable[str],
    approvals: Iterable[Approval],
    role_members: Mapping[str, set[str]],
) -> tuple[Approval, ...]:
    validate_transition(current, target)
    authors = {a.casefold() for a in authors}
    approvals = tuple(approvals)
    for role in required_roles(target):
        matches = [
            a
            for a in approvals
            if a.subsystem == subsystem
            and a.from_state == current
            and a.to_state == target
            and a.evidence_commit == commit
            and a.approver_role == role
        ]
        if not matches:
            raise PromotionRejected(f"missing approval role: {role}")
        if not any(a.approver_identity in role_members.get(role, set()) for a in matches):
            raise PromotionRejected(f"approver is not assigned role: {role}")
        if any(a.approver_identity.casefold() in authors for a in matches):
            raise PromotionRejected(f"self approval: {role}")
    identities = [a.approver_identity.casefold() for a in approvals]
    if len(identities) != len(set(identities)):
        raise PromotionRejected("one identity cannot satisfy multiple approval roles")
    return approvals


def build_receipt(
    subsystem,
    current,
    target,
    commit,
    gate_results: Iterable[dict],
    approvals: Iterable[Approval],
    key: bytes,
    *,
    cedr_decision: dict | None = None,
) -> PromotionReceipt:
    if len(key) < 32:
        raise PromotionRejected("promotion signing key too short")
    # This low-level signing helper is not itself a qualification producer.
    # The receipt command evaluates CEDR and binds that complete report here.
    cedr_digest = ""
    if cedr_decision is not None:
        if (
            cedr_decision.get("eligible") is not True
            or cedr_decision.get("source_commit") != commit
        ):
            raise PromotionRejected("CEDR report does not qualify this candidate")
        cedr_digest = hashlib.sha256(
            json.dumps(
                cedr_decision, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
    results = tuple(gate_results)
    if not results or any(r.get("status") != "PASS" for r in results):
        raise PromotionRejected("all required gates must PASS; SKIP is not promotable")
    hashes = tuple(
        hashlib.sha256(json.dumps(r, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        for r in results
    )
    unsigned = {
        "cedr_decision_digest": cedr_digest,
        "subsystem": subsystem,
        "from_state": current,
        "to_state": target,
        "commit": commit,
        "gate_result_hashes": hashes,
        "approvals": tuple(approvals),
        "issued_at": int(time.time()),
        "signature_algorithm": "HMAC-SHA256",
    }
    raw = json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda x: (
            x.value
            if hasattr(x, "value")
            else asdict(x) if hasattr(x, "__dataclass_fields__") else str(x)
        ),
    ).encode()
    sig = hmac.new(key, raw, hashlib.sha256).hexdigest()
    return PromotionReceipt(**unsigned, signature=sig)
