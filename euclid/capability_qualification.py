"""Evidence-bound qualification for narrowly scoped EUCLID capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from types import MappingProxyType
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


_REVISION = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._:-]{0,127}\Z")
_REQUIRED_SAFETY_CHECKS = frozenset(
    {"proxy-reward-exploitation", "negative-transfer"}
)


class EvidenceKind(str, Enum):
    THEOREM = "theorem"
    EMPIRICAL = "empirical"
    TEST = "test"
    BENCHMARK = "benchmark"
    DECISION = "decision"


class EvidenceStatus(str, Enum):
    EXECUTED = "executed"
    FORMALLY_VERIFIED = "formally_verified"
    REPORTED = "reported"
    UNAVAILABLE = "unavailable"


class EvidenceOutcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"


class QualificationStatus(str, Enum):
    PROMOTED = "promoted"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"
    REVOKED = "revoked"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _valid_identifier(value: object) -> bool:
    return type(value) is str and _IDENTIFIER.fullmatch(value) is not None


@dataclass(frozen=True)
class EvidenceRecord:
    """Signed evidence metadata; the referenced artifact remains independently retained."""

    evidence_id: str
    check_id: str
    source_revision: str
    domain: str
    task_scope: str
    kind: EvidenceKind
    status: EvidenceStatus
    outcome: EvidenceOutcome
    artifact_sha256: str
    verifier_id: str
    independent: bool
    summary: str
    failures: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    signature: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "failures", tuple(self.failures))
        object.__setattr__(self, "limitations", tuple(self.limitations))
        if (
            not _valid_identifier(self.evidence_id)
            or not _valid_identifier(self.check_id)
            or not _valid_identifier(self.verifier_id)
            or not _REVISION.fullmatch(self.source_revision)
            or type(self.domain) is not str
            or not self.domain.strip()
            or type(self.task_scope) is not str
            or not self.task_scope.strip()
            or type(self.kind) is not EvidenceKind
            or type(self.status) is not EvidenceStatus
            or type(self.outcome) is not EvidenceOutcome
            or not _SHA256.fullmatch(self.artifact_sha256)
            or type(self.independent) is not bool
            or type(self.summary) is not str
            or not self.summary.strip()
            or any(type(item) is not str or not item.strip()
                   for item in (*self.failures, *self.limitations))
        ):
            raise ValueError("complete, scoped evidence metadata is required")

    def body(self) -> bytes:
        return _canonical(
            {
                "evidence_id": self.evidence_id,
                "check_id": self.check_id,
                "source_revision": self.source_revision,
                "domain": self.domain,
                "task_scope": self.task_scope,
                "kind": self.kind.value,
                "status": self.status.value,
                "outcome": self.outcome.value,
                "artifact_sha256": self.artifact_sha256,
                "verifier_id": self.verifier_id,
                "independent": self.independent,
                "summary": self.summary,
                "failures": list(self.failures),
                "limitations": list(self.limitations),
            }
        )


@dataclass(frozen=True)
class ClaimConclusion:
    conclusion_id: str
    statement: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))
        if (
            not _valid_identifier(self.conclusion_id)
            or type(self.statement) is not str
            or not self.statement.strip()
            or any(not _valid_identifier(item) for item in self.evidence_ids)
        ):
            raise ValueError("a conclusion needs an identifier, statement, and evidence references")


@dataclass(frozen=True)
class CapabilityClaim:
    """A claim whose qualification cannot escape its revision, domain, or task scope."""

    claim_id: str
    statement: str
    source_revision: str
    domain: str
    task_scope: str
    conclusions: tuple[ClaimConclusion, ...]
    evidence: tuple[EvidenceRecord, ...]
    acceptance_checks: tuple[str, ...]
    authority_limits: tuple[str, ...]
    rollback_plan: str

    def __post_init__(self) -> None:
        for name in ("conclusions", "evidence", "acceptance_checks", "authority_limits"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if (
            not _valid_identifier(self.claim_id)
            or type(self.statement) is not str
            or not self.statement.strip()
            or not _REVISION.fullmatch(self.source_revision)
            or type(self.domain) is not str
            or not self.domain.strip()
            or type(self.task_scope) is not str
            or not self.task_scope.strip()
            or not self.conclusions
            or any(type(item) is not ClaimConclusion for item in self.conclusions)
            or any(type(item) is not EvidenceRecord for item in self.evidence)
            or len({item.conclusion_id for item in self.conclusions}) != len(self.conclusions)
            or len({item.evidence_id for item in self.evidence}) != len(self.evidence)
            or any(not _valid_identifier(item) for item in self.acceptance_checks)
            or len(set(self.acceptance_checks)) != len(self.acceptance_checks)
            or not self.authority_limits
            or any(type(item) is not str or not item.strip() or "*" in item
                   for item in self.authority_limits)
            or len(set(self.authority_limits)) != len(self.authority_limits)
            or type(self.rollback_plan) is not str
            or not self.rollback_plan.strip()
        ):
            raise ValueError("a scoped claim needs conclusions, limits, and a rollback plan")

    @property
    def scope_key(self) -> tuple[str, str, str, str]:
        return (self.claim_id, self.source_revision, self.domain, self.task_scope)


@dataclass(frozen=True)
class QualificationDecision:
    status: QualificationStatus
    claim_id: str
    source_revision: str
    domain: str
    task_scope: str
    evidence_digest: str
    reasons: tuple[str, ...] = ()
    unavailable_conclusions: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class CapabilityQualificationRegistry:
    """Fail-closed, in-process promotion and revocation gate.

    This registry grants only exact-scope capability authority. It is not a
    durable audit store or an executor; hosts must retain artifacts and persist
    registry events before relying on qualifications across restarts.
    """

    def __init__(
        self,
        *,
        trusted_verifiers: Mapping[str, Ed25519PublicKey],
        required_safety_checks: frozenset[str] = _REQUIRED_SAFETY_CHECKS,
    ) -> None:
        if (
            not trusted_verifiers
            or any(
                not _valid_identifier(name) or not isinstance(key, Ed25519PublicKey)
                for name, key in trusted_verifiers.items()
            )
            or not required_safety_checks
            or any(not _valid_identifier(item) for item in required_safety_checks)
        ):
            raise ValueError("trusted evidence verifiers and safety checks are required")
        self._verifiers = MappingProxyType(dict(trusted_verifiers))
        self._required_safety_checks = frozenset(required_safety_checks)
        self._active: dict[tuple[str, str, str, str], CapabilityClaim] = {}
        self._revoked: dict[tuple[str, str, str, str], str] = {}
        self._events: list[dict[str, str]] = []

    @property
    def events(self) -> tuple[dict[str, str], ...]:
        return tuple(dict(event) for event in self._events)

    def evaluate(self, claim: CapabilityClaim) -> QualificationDecision:
        if type(claim) is not CapabilityClaim:
            raise TypeError("a typed CapabilityClaim is required")

        reasons: list[str] = []
        failures: list[str] = []
        limitations: list[str] = []
        by_id: dict[str, EvidenceRecord] = {}
        valid: dict[str, EvidenceRecord] = {}
        for record in claim.evidence:
            by_id[record.evidence_id] = record
            limitations.extend(record.limitations)
            failures.extend(record.failures)
            if record.outcome is EvidenceOutcome.FAIL:
                failures.append(f"{record.check_id}: recorded failure")
            if (
                record.source_revision != claim.source_revision
                or record.domain != claim.domain
                or record.task_scope != claim.task_scope
            ):
                reasons.append(f"{record.evidence_id}: revision or scope mismatch")
                continue
            verifier = self._verifiers.get(record.verifier_id)
            if verifier is None or not record.signature:
                reasons.append(f"{record.evidence_id}: unavailable trusted attestation")
                continue
            try:
                verifier.verify(bytes.fromhex(record.signature), record.body())
            except (InvalidSignature, ValueError):
                reasons.append(f"{record.evidence_id}: invalid evidence signature")
                continue
            valid[record.evidence_id] = record

        missing_safety = self._required_safety_checks - set(claim.acceptance_checks)
        if missing_safety:
            reasons.append(
                "missing required safety checks: " + ", ".join(sorted(missing_safety))
            )
        if not any(
            check not in self._required_safety_checks
            for check in claim.acceptance_checks
        ):
            reasons.append("independent domain acceptance check is required")

        unavailable_conclusions: list[str] = []
        for conclusion in claim.conclusions:
            supporting = [valid.get(evidence_id) for evidence_id in conclusion.evidence_ids]
            if not supporting or any(record is None for record in supporting):
                unavailable_conclusions.append(conclusion.conclusion_id)
                continue
            if not any(self._supports(record) for record in supporting if record is not None):
                unavailable_conclusions.append(conclusion.conclusion_id)

        for check in claim.acceptance_checks:
            candidates = [
                record for record in valid.values() if record.check_id == check
            ]
            if not any(self._acceptance_passes(record) for record in candidates):
                reasons.append(f"{check}: executed independent passing evidence unavailable")

        if unavailable_conclusions:
            reasons.append(
                "unsupported conclusions unavailable: "
                + ", ".join(unavailable_conclusions)
            )
        if failures:
            reasons.append("recorded failures prohibit promotion")

        evidence_payload = [
            {"body": record.body().decode("utf-8"), "signature": record.signature}
            for record in claim.evidence
        ]
        digest = hashlib.sha256(_canonical(evidence_payload)).hexdigest()
        status = (
            QualificationStatus.BLOCKED
            if failures
            else QualificationStatus.UNAVAILABLE
            if reasons
            else QualificationStatus.PROMOTED
        )
        return QualificationDecision(
            status=status,
            claim_id=claim.claim_id,
            source_revision=claim.source_revision,
            domain=claim.domain,
            task_scope=claim.task_scope,
            evidence_digest=digest,
            reasons=tuple(dict.fromkeys(reasons)),
            unavailable_conclusions=tuple(unavailable_conclusions),
            failures=tuple(dict.fromkeys(failures)),
            limitations=tuple(dict.fromkeys(limitations)),
        )

    @staticmethod
    def _supports(record: EvidenceRecord) -> bool:
        if record.outcome is not EvidenceOutcome.PASS:
            return False
        if record.kind is EvidenceKind.THEOREM:
            return record.status is EvidenceStatus.FORMALLY_VERIFIED
        return record.status is EvidenceStatus.EXECUTED

    @staticmethod
    def _acceptance_passes(record: EvidenceRecord) -> bool:
        return (
            record.kind is EvidenceKind.TEST
            and record.status is EvidenceStatus.EXECUTED
            and record.outcome is EvidenceOutcome.PASS
            and record.independent
            and not record.failures
        )

    def promote(self, claim: CapabilityClaim) -> QualificationDecision:
        decision = self.evaluate(claim)
        if decision.status is not QualificationStatus.PROMOTED:
            self._events.append(
                {
                    "action": "promotion-refused",
                    "claim_id": claim.claim_id,
                    "domain": claim.domain,
                    "task_scope": claim.task_scope,
                    "reason": "; ".join(decision.reasons),
                }
            )
            return decision
        self._active[claim.scope_key] = claim
        self._revoked.pop(claim.scope_key, None)
        self._events.append(
            {
                "action": "promoted",
                "claim_id": claim.claim_id,
                "domain": claim.domain,
                "task_scope": claim.task_scope,
                "evidence_digest": decision.evidence_digest,
            }
        )
        return decision

    def authorize(
        self,
        *,
        claim_id: str,
        source_revision: str,
        domain: str,
        task_scope: str,
        authority: str,
    ) -> bool:
        key = (claim_id, source_revision, domain, task_scope)
        claim = self._active.get(key)
        if (
            claim is None
            or key in self._revoked
            or authority not in claim.authority_limits
        ):
            raise PermissionError("capability is not promoted for this exact scope and authority")
        return True

    def revoke(
        self,
        *,
        claim_id: str,
        source_revision: str,
        domain: str,
        task_scope: str,
        reason: str,
    ) -> None:
        key = (claim_id, source_revision, domain, task_scope)
        if key not in self._active or type(reason) is not str or not reason.strip():
            raise ValueError("an active exact-scope qualification and revocation reason are required")
        self._revoked[key] = reason
        self._events.append(
            {
                "action": "revoked",
                "claim_id": claim_id,
                "domain": domain,
                "task_scope": task_scope,
                "reason": reason,
                "rollback_plan": self._active[key].rollback_plan,
            }
        )
        del self._active[key]
