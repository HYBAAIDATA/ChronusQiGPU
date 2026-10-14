"""Candidate acquisition/composition admission, without inherited task authority.

Actual method construction, sandbox execution, hidden task custody and red-team
execution are host ports. An absent executor is unavailable, not a passing test.
"""

from dataclasses import dataclass, replace
from ._contracts import ContractError, integer, text
from .trust import TrustLevel
from .assurance import assurance_required


@dataclass(frozen=True)
class Attempt:
    strategy: str
    passed: bool
    evidence: str


@dataclass(frozen=True)
class CapabilityGap:
    id: str
    task_key: str
    missing_method: str
    attempts: tuple[Attempt, ...]


def detect_capability_gap(task, attempts, *, minimum_failures):
    integer(minimum_failures, minimum=2)
    if type(attempts) is not tuple or len(attempts) > 128:
        raise ContractError("bounded prior attempts required")
    failed = [a for a in attempts if a.passed is False]
    if len(failed) >= minimum_failures and len({a.strategy for a in failed}) >= 2:
        return CapabilityGap("gap:" + task.key, task.key, "no adequate tested method", attempts)
    return None


@dataclass(frozen=True)
class CapabilityCandidate:
    id: str
    contract: object
    source: str
    task: object
    report: object
    attestation: object
    sandbox_passed: bool
    red_team_passed: bool
    authority: TrustLevel = TrustLevel.OBSERVE
    deployment_state: str = "PROPOSED"

    def __post_init__(self):
        text(self.id)
        if self.authority is not TrustLevel.OBSERVE:
            raise ContractError("new capabilities inherit zero authority")
        if self.source not in ("RESEARCH", "CONSTRUCTION", "ACQUISITION", "COMPOSITION"):
            raise ContractError("method provenance required")
        if self.task.workflow != "candidate:" + self.id:
            raise ContractError("candidate requires a new, isolated task scope")


def create_capability(gap, *, propose, sandbox, red_team, ledger, now):
    from .anti_goodhart import disclose_optimization
    from ._contracts import digest

    disclose_optimization(
        ledger,
        objective=gap.missing_method,
        kind="capability_creation",
        evidence=digest(gap),
        now=now,
    )
    candidate = propose(gap)
    if not isinstance(candidate, CapabilityCandidate):
        raise ContractError("typed method candidate required")
    # Host executors perform actual candidate testing; false/missing never pass.
    sandbox_ok = sandbox(candidate) is True
    red_ok = red_team(candidate) is True if sandbox_ok else False
    state = "EVALUATED" if sandbox_ok and red_ok else "RETIRED"
    candidate = replace(
        candidate, sandbox_passed=sandbox_ok, red_team_passed=red_ok, deployment_state=state
    )
    ledger.append(
        "capability_proposed",
        {
            "id": candidate.id,
            "state": state,
            "task": candidate.task.key,
            "source": candidate.source,
        },
        now=now,
    )
    return candidate


def integrate_capability(
    candidate, identity, registry, adapter, ledger, *, now, evaluator_keys, verifier_keys, max_age
):
    if (
        candidate.attestation is None
        or not candidate.sandbox_passed
        or not candidate.red_team_passed
        or candidate.deployment_state != "EVALUATED"
        or not candidate.report.admitted(
            identity, candidate.task, now=now, keys=evaluator_keys, max_age=max_age
        )
        or not candidate.attestation.admissible(
            identity, candidate.task, candidate.report.metrics, now, verifier_keys
        )
        or candidate.attestation.level < assurance_required(TrustLevel.OBSERVE, candidate.task)
    ):
        raise ContractError("candidate lacks sandbox/adversarial/independent qualification")
    # Distinct task key and artifact fingerprints must be qualified separately.
    ledger.append(
        "capability_integrated",
        {
            "id": candidate.id,
            "task": candidate.task.key,
            "authority": TrustLevel.OBSERVE,
            "state": "APPROVED_FOR_LIMITED_USE",
        },
        now=now,
    )
    registry.register(candidate.contract, adapter, task_key=candidate.task.key)
    return replace(candidate, deployment_state="APPROVED_FOR_LIMITED_USE")


def retire_capability(candidate, registry, ledger, *, now, reason):
    text(reason)
    ledger.append("capability_retired", {"id": candidate.id, "reason": reason}, now=now)
    registry.unregister(candidate.contract.name)
    return replace(candidate, deployment_state="RETIRED")
