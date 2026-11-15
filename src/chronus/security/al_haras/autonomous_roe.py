"""
AL HARAS (HYBA Security): policy-criteria completeness check for review requests.

Historical name in the product notes: "autonomous rules of engagement". The
class names ``AutonomousROEValidator``, ``ROECriterion`` and
``EngagementSimplex`` are kept for import compatibility only.

This module does not authorise, recommend, rank or execute any action, and it
never authorises an engagement or any use of force. It answers one
bookkeeping question about a review request record: does the record contain
every approval the configured policy requires, recorded by enough distinct
people, with the stated risk score within the stated ceiling? Whatever the
answer, a decision always requires an accountable human; a complete record
only means the request can be put to that person.

Simplicial reading (exact and small): the required criteria R are the vertices
of a simplex Delta_R, and the approvals present in the record span the face
Delta_(R and A). The record is complete for the criteria iff that face is all
of Delta_R; the number of missing vertices |R minus A| (the face's
codimension) is reported as ``boundary_defect_norm``. The distinct-approver
and risk-ceiling checks add their own violation codes.

Every evaluation, complete or not, returns a review record signed with Ed25519
(``receipts.py``) over canonical JSON. The record is tamper-evident; it is not
a zero-knowledge proof and attests nothing about legality or about compliance
with any law or treaty.
"""

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Set, Tuple

from chronus.security.al_haras.receipts import ReceiptSigner, default_signer, signed_receipt

RECORD_TYPE = "policy-criteria-completeness-check"
DECISION_AUTHORITY = (
    "an accountable human reviewer; this software checks record completeness "
    "only and makes no decision"
)
_HEX64 = re.compile(r"[0-9a-f]{64}")


class ROECriterion(str, Enum):
    """Neutral approval criteria a policy can require (historical class name)."""

    SUBJECT_IDENTIFIED = "SUBJECT_IDENTIFIED"
    RISK_ASSESSMENT_RECORDED = "RISK_ASSESSMENT_RECORDED"
    EXCLUSIONS_CHECKED = "EXCLUSIONS_CHECKED"
    LEGAL_REVIEW_RECORDED = "LEGAL_REVIEW_RECORDED"


def _normalise_approvals(approvals: Mapping[Any, Any]) -> Tuple[Dict[ROECriterion, str], List[str]]:
    recognised: Dict[ROECriterion, str] = {}
    unrecognised: List[str] = []
    for key, approver in (approvals or {}).items():
        try:
            criterion = key if isinstance(key, ROECriterion) else ROECriterion(key)
        except ValueError:
            unrecognised.append(str(key))
            continue
        if isinstance(approver, str) and approver.strip():
            recognised[criterion] = approver.strip()
    return recognised, sorted(unrecognised)


def _non_negative_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


@dataclass
class EngagementSimplex:
    """A review-request record (historical class name). Nothing in it is acted on.

    ``subject_commitment`` is a caller-supplied SHA-256 hex digest of the
    request subject; it is stored and checked for format, never interpreted.
    ``approvals`` maps each criterion to the identifier of the person who
    recorded it.
    """

    request_id: str
    subject_commitment: str
    approvals: Dict[ROECriterion, str]
    risk_score: int
    risk_ceiling: int

    @property
    def satisfied_criteria(self) -> Set[ROECriterion]:
        return set(_normalise_approvals(self.approvals)[0])


class AutonomousROEValidator:
    """Completeness check for review records (historical class name; see module docstring)."""

    DEFAULT_REQUIRED_CRITERIA: FrozenSet[ROECriterion] = frozenset(ROECriterion)

    def __init__(
        self,
        policy_owner: str = "POLICY_OWNER_UNSPECIFIED",
        required_criteria: Optional[Iterable[ROECriterion]] = None,
        min_distinct_approvers: int = 2,
    ) -> None:
        required = frozenset(self.DEFAULT_REQUIRED_CRITERIA if required_criteria is None else required_criteria)
        if not required or not all(isinstance(c, ROECriterion) for c in required):
            raise ValueError("required_criteria must be a non-empty set of ROECriterion members")
        _non_negative_int("min_distinct_approvers", min_distinct_approvers)
        if not 1 <= min_distinct_approvers <= len(required):
            raise ValueError("min_distinct_approvers must be between 1 and the number of required criteria")
        self.policy_owner = policy_owner
        self.required_criteria = required
        self.min_distinct_approvers = min_distinct_approvers

    def _assess(self, request: EngagementSimplex) -> Dict[str, Any]:
        score = _non_negative_int("risk_score", request.risk_score)
        ceiling = _non_negative_int("risk_ceiling", request.risk_ceiling)
        approvals, unrecognised = _normalise_approvals(request.approvals)
        violations: List[str] = []
        request_id = request.request_id if isinstance(request.request_id, str) and request.request_id.strip() else None
        if request_id is None:
            violations.append("INVALID_REQUEST_ID")
        commitment = request.subject_commitment if isinstance(request.subject_commitment, str) else None
        if commitment is None or not _HEX64.fullmatch(commitment):
            violations.append("INVALID_SUBJECT_COMMITMENT")
        present = sorted((c for c in approvals if c in self.required_criteria), key=lambda c: c.value)
        missing = sorted(self.required_criteria - set(present), key=lambda c: c.value)
        violations.extend(f"MISSING_REQUIRED_CRITERION_{c.value}" for c in missing)
        approvers = {approvals[c] for c in present}
        if len(approvers) < self.min_distinct_approvers:
            violations.append(f"INSUFFICIENT_DISTINCT_APPROVERS_{len(approvers)}_OF_{self.min_distinct_approvers}")
        if score > ceiling:
            violations.append(f"RISK_SCORE_EXCEEDS_CEILING_BY_{score - ceiling}")
        return {
            "request_id": request_id,
            "subject_commitment": commitment,
            "present": present,
            "missing": missing,
            "approvals": approvals,
            "approvers": approvers,
            "unrecognised": unrecognised,
            "score": score,
            "ceiling": ceiling,
            "violations": violations,
        }

    def evaluate_boundary_closure(self, engagement: EngagementSimplex) -> Tuple[bool, int, List[str]]:
        """Return (complete, number of missing required criteria, violation codes)."""
        assessed = self._assess(engagement)
        return (not assessed["violations"], len(assessed["missing"]), list(assessed["violations"]))

    def check_policy_completeness(self, engagement: EngagementSimplex) -> Dict[str, Any]:
        """Compute completeness and return it with a signed review record. Decides nothing."""
        start = time.perf_counter_ns()
        assessed = self._assess(engagement)
        complete = not assessed["violations"]
        body = {
            "record_type": RECORD_TYPE,
            "request_id": assessed["request_id"],
            "subject_commitment": assessed["subject_commitment"],
            "policy_owner": self.policy_owner,
            "required_criteria": sorted(c.value for c in self.required_criteria),
            "approved_criteria": [c.value for c in assessed["present"]],
            "missing_criteria": [c.value for c in assessed["missing"]],
            "unrecognised_criteria": assessed["unrecognised"],
            "approvers_by_criterion": {c.value: assessed["approvals"][c] for c in assessed["present"]},
            "distinct_approvers": len(assessed["approvers"]),
            "min_distinct_approvers": self.min_distinct_approvers,
            "risk_score": assessed["score"],
            "risk_ceiling": assessed["ceiling"],
            "violations": list(assessed["violations"]),
            "complete": complete,
            "decision_authority": DECISION_AUTHORITY,
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        return {
            "request_id": assessed["request_id"],
            "complete": complete,
            "status": "COMPLETE_AWAITING_HUMAN_DECISION" if complete else "INCOMPLETE",
            "boundary_defect_norm": len(assessed["missing"]),
            "missing_criteria": [c.value for c in assessed["missing"]],
            "violations": list(assessed["violations"]),
            "distinct_approvers": len(assessed["approvers"]),
            "decision_authority": DECISION_AUTHORITY,
            "review_record": signed_receipt(body),
            "evaluation_duration_ns": time.perf_counter_ns() - start,
        }

    @staticmethod
    def verify_review_record(
        record: Any,
        trusted_public_key_hex: Optional[str] = None,
        trusted_pq_public_key_hex: Optional[str] = None,
    ) -> bool:
        """Both signatures by the trusted keys (default: this process's signer) and internal consistency.

        Both keys are pinned: pinning only the Ed25519 key would let a forger who
        breaks Ed25519 attach an ML-DSA-87 key of their own.
        """
        try:
            body = record["body"]
            signature = record["signature"]
            trusted = trusted_public_key_hex or default_signer().public_key.hex()
            trusted_pq = trusted_pq_public_key_hex or default_signer().pq_public_key.hex()
            if signature.get("public_key_hex") != trusted:
                return False
            if (signature.get("post_quantum") or {}).get("public_key_hex") != trusted_pq:
                return False
            if not ReceiptSigner.verify(body, signature):
                return False
            required = list(body["required_criteria"])
            approved = list(body["approved_criteria"])
            missing = list(body["missing_criteria"])
            violations = list(body["violations"])
            return (
                body["record_type"] == RECORD_TYPE
                and set(approved) <= set(required)
                and missing == sorted(set(required) - set(approved))
                and all(f"MISSING_REQUIRED_CRITERION_{m}" in violations for m in missing)
                and body["complete"] == (not violations)
                and body["distinct_approvers"] == len(set(body["approvers_by_criterion"].values()))
            )
        except (TypeError, KeyError, AttributeError, ValueError):
            return False
