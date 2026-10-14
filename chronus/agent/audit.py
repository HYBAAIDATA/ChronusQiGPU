"""Signed hash-chain with durable-before-action publication and pure replay.

MACSigner authenticates a local message construction; it does NOT replace any
protocol hash/signature or confer independent assurance/institutional consent.
Production custody remains a host-selected signer/store and external anchor.
"""

from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
from ._contracts import ContractError, canonical, digest, integer, text

LEDGERED_EVENTS = frozenset(
    "agent_boot objective_inferred clarification_requested plan_created plan_revised permission_granted permission_denied action_selected action_executed effect_confirmed verification_run verification_failed refusal_issued escalation_requested rollback_executed memory_candidate_rejected memory_lesson_stored memory_lesson_retracted reliability_measured assurance_updated trust_promoted trust_held trust_demoted agent_suspended agent_quarantined agent_retired permission_revoked strategy_selected outcome_recorded evaluation_run goodhart_checked capability_proposed capability_integrated capability_retired fact_adjudicated memory_adjudicated".split()
)


class MACSigner:
    def __init__(self, key_id, key):
        self.key_id = text(key_id)
        if type(key) is not bytes or len(key) < 32:
            raise ContractError("host-supplied MAC key of at least 32 bytes required")
        self._key = key

    def sign(self, data):
        return hmac.new(self._key, data, hashlib.sha256).hexdigest()

    def verify(self, data, signature):
        return type(signature) is str and hmac.compare_digest(self.sign(data), signature)


@dataclass(frozen=True)
class LedgerEvent:
    body: bytes
    signature: str
    digest: str


class AuditLedger:
    def __init__(self, identity, signer, *, path=None):
        self.identity = identity
        self.signer = signer
        self.path = Path(path) if path is not None else None
        self._events = []
        self._lock = threading.RLock()
        if self.path is not None and self.path.exists():
            self.restore(self.path.read_bytes())

    @property
    def events(self):
        return tuple(self._events)

    def append(self, event_type, payload, *, now, actor=None, rationale=""):
        if event_type not in LEDGERED_EVENTS:
            raise ContractError("unknown consequential event")
        integer(now)
        with self._lock:
            body = canonical(
                {
                    "index": len(self._events),
                    "agent_id": self.identity.id,
                    "event_type": event_type,
                    "occurred_at": now,
                    "actor": actor or self.identity.operator,
                    "policy_version": self.identity.policy_version,
                    "key_id": self.signer.key_id,
                    "payload": payload,
                    "rationale": rationale,
                    "previous": self._events[-1].digest if self._events else "",
                }
            )
            event = LedgerEvent(body, self.signer.sign(body), hashlib.sha256(body).hexdigest())
            line = (
                canonical(
                    {"body": json.loads(body), "signature": event.signature, "digest": event.digest}
                )
                + b"\n"
            )
            if self.path is not None:
                nofollow = getattr(os, "O_NOFOLLOW", 0)
                fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | nofollow, 0o600)
                try:
                    with os.fdopen(fd, "ab", closefd=False) as stream:
                        stream.write(line)
                        stream.flush()
                        os.fsync(fd)
                finally:
                    os.close(fd)
            self._events.append(event)
            return event

    def export(self):
        return b"".join(
            canonical({"body": json.loads(e.body), "signature": e.signature, "digest": e.digest})
            + b"\n"
            for e in self._events
        )

    def restore(self, data, *, expected_head=None):
        if len(data) > 16 * 1024 * 1024:
            raise ContractError("bounded ledger import required")
        events = []
        for index, line in enumerate(data.splitlines()):
            row = json.loads(line)
            if canonical(row) != line:
                raise ContractError("noncanonical or duplicate-key ledger row")
            body = canonical(row["body"])
            obj = row["body"]
            integer(obj["index"])
            integer(obj["occurred_at"])
            if (
                obj["index"] != index
                or obj["agent_id"] != self.identity.id
                or obj["policy_version"] != self.identity.policy_version
                or obj["key_id"] != self.signer.key_id
                or obj["event_type"] not in LEDGERED_EVENTS
                or obj["previous"] != (events[-1].digest if events else "")
                or hashlib.sha256(body).hexdigest() != row["digest"]
                or not self.signer.verify(body, row["signature"])
            ):
                raise ContractError("ledger integrity/identity/sequence failure")
            events.append(LedgerEvent(body, row["signature"], row["digest"]))
        if expected_head is not None and (events[-1].digest if events else "") != expected_head:
            raise ContractError("external ledger head anchor mismatch")
        self._events = events

    def verify(self):
        other = AuditLedger(self.identity, self.signer)
        other.restore(self.export())
        return True

    def replay(self):
        self.verify()
        return tuple(json.loads(e.body) for e in self._events)


@dataclass(frozen=True)
class ReplayRecord:
    model_fingerprint: str
    model_version: str
    sampling_config: tuple[tuple[str, str], ...]
    random_seed: int | None
    prompt_refs: tuple[str, ...]
    tool_output_refs: tuple[str, ...]
    environment_snapshot: str
    data_snapshot: str
    policy_version: str
    verifier_refs: tuple[str, ...]
    decision_summary: str


def replay_decision(ledger, records, *, load_evidence):
    """Resolve every reference; missing custody is unavailable, never reconstructed."""
    from ._contracts import sha

    trace = ledger.replay()
    if type(records) is not tuple or not records:
        raise ContractError("model/tool provenance records required")
    anchored = {
        row["payload"].get("record_digest")
        for row in trace
        if type(row.get("payload")) is dict and row["payload"].get("phase") == "replay_record"
    }
    if any(digest(record) not in anchored for record in records):
        raise ContractError("replay provenance not anchored to the authenticated ledger")
    resolved = []
    for record in records:
        sha(record.model_fingerprint)
        text(record.model_version)
        if record.policy_version != ledger.identity.policy_version:
            raise ContractError("replay policy mismatch")
        for ref in (
            record.prompt_refs
            + record.tool_output_refs
            + record.verifier_refs
            + (record.environment_snapshot, record.data_snapshot)
        ):
            sha(ref)
            data = load_evidence(ref)
            if type(data) is not bytes or hashlib.sha256(data).hexdigest() != ref:
                raise ContractError("missing or altered replay evidence")
            resolved.append(ref)
    return {
        "decision_path_reconstructed": True,
        "byte_identical": False,
        "events": trace,
        "records": records,
        "resolved": tuple(resolved),
        "deviations": ("stochastic outputs/external state not re-executed",),
    }


def record_replay(ledger, record, *, now):
    return ledger.append(
        "plan_created",
        {"phase": "replay_record", "record": record, "record_digest": digest(record)},
        now=now,
    )


def replay_deterministic_component(input_bytes, *, transform, expected_sha256):
    """Execute a host-selected pure component and compare actual output bytes."""
    from ._contracts import sha

    sha(expected_sha256)
    if type(input_bytes) is not bytes or len(input_bytes) > 65536:
        raise ContractError("bounded component input required")
    output = transform(input_bytes)
    if type(output) is not bytes or len(output) > 65536:
        raise ContractError("bounded component output required")
    return {
        "byte_identical": hashlib.sha256(output).hexdigest() == expected_sha256,
        "actual_digest": hashlib.sha256(output).hexdigest(),
    }
