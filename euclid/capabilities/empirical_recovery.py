"""Explicit host-authorized reconciliation of a prepared custody publication.

This is a maintenance API, not a specialist operation or an authorization grant.
Stop all writers for this single-writer stream before use. The host must supply
an independent recovery authorizer backed by its actual AL HARAS/operator policy.
No custody bytes are rewritten, no mutation is replayed, and no original request
is reported as having completed on time. Legacy ambiguous records without a
durable PREPARED intent remain quarantined for independent forensic recovery.
"""

from dataclasses import asdict, dataclass
import hashlib
import re
import time
from typing import Callable

from .empirical_state_bridge import (
    AuditReceipt,
    EmpiricalStateBridge,
    StateCommitUncertain,
    _decode_envelope,
)


@dataclass(frozen=True)
class PublicationRecoveryRequest:
    owner_id: str
    binding_id: str
    envelope_sha256: str
    caller_id: str
    operator_token: str
    deadline_epoch: float


def reconcile_publication(
    request: PublicationRecoveryRequest,
    *,
    recovery_authorizer: Callable[[PublicationRecoveryRequest], bool] | None = None,
    audit=None,
    data_port=None,
) -> AuditReceipt:
    """Record completion only for an authorized, exactly prepared publication.

    The credential is never persisted. Authorization is mandatory on retries,
    including idempotent retries after a completion append that raised.
    Existing quarantined bridge objects stay quarantined: construct a fresh
    canonical runtime binding after maintenance finishes.
    """
    if type(request) is not PublicationRecoveryRequest:
        raise ValueError("invalid recovery request")
    import math

    if (
        any(
            type(value) is not str or not 1 <= len(value) <= 256
            for value in (request.owner_id, request.binding_id, request.caller_id)
        )
        or type(request.envelope_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", request.envelope_sha256) is None
        or type(request.operator_token) is not str
        or not request.operator_token
        or type(request.deadline_epoch) not in (float, int)
        or not math.isfinite(request.deadline_epoch)
        or request.deadline_epoch <= time.time()
    ):
        raise ValueError("invalid or expired recovery request")
    if (
        not callable(recovery_authorizer)
        or audit is None
        or getattr(audit, "path", None) is None
        or data_port is None
    ):
        raise PermissionError("independent recovery authority and durable ports required")
    try:
        authorized = recovery_authorizer(request) is True
    except Exception:
        authorized = False
    if not authorized:
        raise PermissionError("recovery not authorized")

    def check_latest():
        latest = data_port.latest(EmpiricalStateBridge.STATE_KIND)
        if latest is None or latest.binding_id != request.binding_id:
            raise StateCommitUncertain("stale recovery target")
        raw = data_port.read(request.binding_id)
        if hashlib.sha256(raw).hexdigest() != request.envelope_sha256:
            raise StateCommitUncertain("recovery target digest mismatch")
        return raw

    state, receipt = _decode_envelope(check_latest(), request.owner_id)
    execution_id = receipt.receipt_id.removeprefix("rcpt_")
    events = [
        record["event"]
        for record in audit.records  # Actual audit verifies its durable chain.
        if record["event"].get("schema") == "euclid.empirical-transition/1"
    ]
    matching = [
        (i, event)
        for i, event in enumerate(events)
        if event.get("execution_id") == execution_id and event.get("owner_id") == request.owner_id
    ]
    prepared = [(i, e) for i, e in matching if e.get("phase") == "PREPARED"]
    if len(prepared) != 1:
        raise StateCommitUncertain("exactly one durable prepared intent required")
    prepared_index, intent = prepared[0]
    if (
        intent.get("receipt") != asdict(receipt)
        or intent.get("envelope_sha256") != request.envelope_sha256
        or intent.get("capability_id") != receipt.capability_id
        or intent.get("caller_id") != receipt.caller_id
        or any(e.get("phase") == "ROLLED_BACK" for _, e in matching)
    ):
        raise StateCommitUncertain("prepared intent mismatch or rolled back")
    admitted = [(i, e) for i, e in matching if e.get("phase") == "ADMITTED"]
    if (
        len(admitted) != 1
        or admitted[0][0] >= prepared_index
        or admitted[0][1].get("prior_state_hash") != intent.get("prior_state_hash")
        or admitted[0][1].get("capability_id") != receipt.capability_id
        or admitted[0][1].get("caller_id") != receipt.caller_id
    ):
        raise StateCommitUncertain("prepared intent has no matching prior admission")
    prior_binding = intent.get("prior_binding_id")
    if prior_binding is None:
        # A new controller can have a host-supplied initial state; require its
        # recorded hash, not an invented default state or a prior identity.
        if state["version"] < 2:
            raise StateCommitUncertain("invalid initial transition version")
    else:
        prior_state, prior_receipt = _decode_envelope(
            data_port.read(prior_binding), request.owner_id
        )
        if (
            prior_receipt.new_state_hash != intent.get("prior_state_hash")
            or state["version"] != prior_state["version"] + 1
            or not any(
                i < admitted[0][0]
                and e.get("phase") == "COMMITTED"
                and e.get("owner_id", request.owner_id) == request.owner_id
                and e.get("custody_binding_id") == prior_binding
                and e.get("receipt") == asdict(prior_receipt)
                for i, e in enumerate(events)
            )
        ):
            raise StateCommitUncertain("prior durable lineage mismatch")
    completed = [(i, e) for i, e in matching if e.get("phase") == "COMMITTED"]
    if completed:
        if (
            len(completed) != 1
            or completed[0][0] <= prepared_index
            or completed[0][1].get("receipt") != asdict(receipt)
            or completed[0][1].get("custody_binding_id") != request.binding_id
        ):
            raise StateCommitUncertain("conflicting completion evidence")
        return receipt
    if request.deadline_epoch <= time.time():
        raise StateCommitUncertain("recovery deadline expired")
    event = {
        "schema": "euclid.empirical-transition/1",
        "execution_id": execution_id,
        "owner_id": request.owner_id,
        "capability_id": receipt.capability_id,
        "caller_id": receipt.caller_id,
        "recovery_actor_id": request.caller_id,
        "recovered": True,
        "recovery_timestamp_epoch": time.time(),
        "custody_binding_id": request.binding_id,
        "envelope_sha256": request.envelope_sha256,
    }
    try:
        audit.append({**event, "phase": "RECOVERY_ADMITTED"})
        check_latest()
        if request.deadline_epoch <= time.time():
            raise TimeoutError("recovery deadline expired after admission")
        audit.append({**event, "phase": "COMMITTED", "receipt": asdict(receipt)})
    except Exception as exc:
        raise StateCommitUncertain(
            "recovery uncertain; inspect durable evidence before retry"
        ) from exc
    return receipt
