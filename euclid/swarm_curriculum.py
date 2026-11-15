"""Evidence-preserving leadership skill training curriculum for EUCLID swarms.

Training invokes a REAL caller-supplied trainer. Held-out and adversarial
evaluation invoke a REAL caller-supplied evaluator. No test fixtures, labels,
model scores, or raw training results are promoted into permission grants.
Only independently signed scoped CapabilityQualificationRegistry claims can
later authorize swarm activation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from copy import deepcopy
import hashlib
from typing import Any, Callable, Mapping

from .swarm_evolution import LEADER_SKILLS, SwarmRefused, SwarmMission, SwarmActivator, SwarmTask, _canonical, _text


@dataclass(frozen=True)
class SkillCase:
    case_id: str
    lineage: str
    skill: str
    inputs: Mapping[str, Any]
    expected: Mapping[str, Any]

    def __post_init__(self) -> None:
        _text(self.case_id, "case_id")
        _text(self.lineage, "lineage")
        _text(self.skill, "skill")
        if not isinstance(self.inputs, Mapping) or not isinstance(self.expected, Mapping):
            raise SwarmRefused("training examples must have JSON object inputs and references")
        if len(_canonical(dict(self.inputs))) > 32768 or len(_canonical(dict(self.expected))) > 32768:
            raise SwarmRefused("training example exceeds 32KiB")
        object.__setattr__(self, "inputs", deepcopy(dict(self.inputs)))
        object.__setattr__(self, "expected", deepcopy(dict(self.expected)))


@dataclass(frozen=True)
class LeaderCurriculum:
    """A leader must learn and qualify every role skill, not just delegation."""

    agent_id: str
    scope: str
    revision: str
    training: tuple[SkillCase, ...]
    validation: tuple[SkillCase, ...]
    adversarial: tuple[SkillCase, ...]
    final_test: tuple[SkillCase, ...]

    def __post_init__(self) -> None:
        _text(self.agent_id, "agent_id")
        _text(self.scope, "scope")
        if type(self.revision) is not str or len(self.revision) != 40 \
                or any(c not in "0123456789abcdef" for c in self.revision):
            raise SwarmRefused("curriculum requires exact source revision")
        partitions = {
            "training": self.training, "validation": self.validation,
            "adversarial": self.adversarial, "final_test": self.final_test,
        }
        seen_cases: set[str] = set()
        seen_lineages: set[str] = set()
        seen_contents: set[str] = set()
        for partition, cases in partitions.items():
            if type(cases) is not tuple or not cases:
                raise SwarmRefused(f"{partition} must contain actual cases")
            for case in cases:
                if not isinstance(case, SkillCase):
                    raise SwarmRefused("invalid curriculum case")
                digest = hashlib.sha256(_canonical({
                    "skill": case.skill, "inputs": dict(case.inputs),
                })).hexdigest()
                if case.case_id in seen_cases or case.lineage in seen_lineages \
                        or digest in seen_contents:
                    raise SwarmRefused("training/evaluation leakage or duplicate case")
                seen_cases.add(case.case_id)
                seen_lineages.add(case.lineage)
                seen_contents.add(digest)
        for skill in LEADER_SKILLS:
            if any(skill not in {case.skill for case in partition}
                   for partition in partitions.values()):
                raise SwarmRefused(f"leadership skill has no independent train/evaluation coverage: {skill}")


def _partition_digest(cases: tuple[SkillCase, ...]) -> str:
    return hashlib.sha256(_canonical([
        {
            "case_id": case.case_id, "lineage": case.lineage,
            "skill": case.skill, "inputs": dict(case.inputs),
            "expected": dict(case.expected),
        } for case in cases
    ])).hexdigest()


def train_leadership(
    curriculum: LeaderCurriculum,
    *,
    train: Callable[[tuple[SkillCase, ...]], Mapping[str, Any]],
    evaluate: Callable[[str, SkillCase], Mapping[str, Any]],
    accept: Callable[[SkillCase, Mapping[str, Any]], bool],
) -> dict[str, Any]:
    """Execute training and independent held-out assessments.

    Training must return a persisted checkpoint identifier and its SHA256
    content digest. This function does not pretend to verify checkpoint bytes:
    the trusted evidence verifier must inspect them before signing promotion.
    The final-test set is never passed to the trainer.
    """
    if not all(callable(item) for item in (train, evaluate, accept)):
        raise SwarmRefused("real trainer, evaluator and acceptance assessor required")

    # Detached snapshot prevents callbacks from mutating the source curriculum.
    curriculum = deepcopy(curriculum)
    LeaderCurriculum.__post_init__(curriculum)
    checkpoint = train(deepcopy(curriculum.training))
    if not isinstance(checkpoint, Mapping) or type(checkpoint.get("checkpoint_id")) is not str \
            or not checkpoint["checkpoint_id"].strip():
        raise SwarmRefused("trainer did not produce a checkpoint identity")
    digest = checkpoint.get("sha256")
    if type(digest) is not str or len(digest) != 64 \
            or any(char not in "0123456789abcdef" for char in digest):
        raise SwarmRefused("trainer did not supply a checkpoint SHA256")

    partition_results: dict[str, dict[str, Any]] = {}
    for name, cases in (
        ("validation", curriculum.validation),
        ("adversarial", curriculum.adversarial),
        ("final_test", curriculum.final_test),
    ):
        outcomes = []
        for case in cases:
            # Evaluators must not receive held-out reference labels.
            blinded = replace(case, expected={})
            output = evaluate(checkpoint["checkpoint_id"], blinded)
            if not isinstance(output, Mapping) or len(_canonical(dict(output))) > 32768:
                raise SwarmRefused("invalid evaluation output")
            passed = accept(deepcopy(case), deepcopy(dict(output)))
            if type(passed) is not bool:
                raise SwarmRefused("assessor must return a literal boolean")
            outcomes.append({
                "case_id": case.case_id,
                "skill": case.skill,
                "passed": passed,
                "result_sha256": hashlib.sha256(_canonical(dict(output))).hexdigest(),
            })
        partition_results[name] = {
            "passed": sum(item["passed"] for item in outcomes),
            "total": len(cases),
            "outcomes": outcomes,
            "dataset_sha256": _partition_digest(cases),
        }

    all_passed = all(row["passed"] == row["total"] for row in partition_results.values())
    report: dict[str, Any] = {
        "schema": "euclid.swarm-leadership-training/v1",
        "agent_id": curriculum.agent_id,
        "scope": curriculum.scope,
        "source_revision": curriculum.revision,
        "skills": sorted(LEADER_SKILLS),
        "checkpoint": {
            "checkpoint_id": checkpoint["checkpoint_id"], "sha256": digest,
            "bytes_independently_verified": False,
        },
        "training": {
            "total": len(curriculum.training),
            "dataset_sha256": _partition_digest(curriculum.training),
        },
        "evaluation": partition_results,
        "outcome": "READY_FOR_INDEPENDENT_ATTESTATION" if all_passed else "FAILED",
        "authority_granted": False,
        "model_training_independently_verified": False,
    }
    report["report_sha256"] = hashlib.sha256(_canonical(report)).hexdigest()
    return report


def train_qualify_and_activate(
    curriculum: LeaderCurriculum,
    mission: "SwarmMission",
    *,
    activator: "SwarmActivator",
    train: Callable[[tuple[SkillCase, ...]], Mapping[str, Any]],
    evaluate: Callable[[str, SkillCase], Mapping[str, Any]],
    accept: Callable[[SkillCase, Mapping[str, Any]], bool],
    certify: Callable[[Mapping[str, Any]], None],
    dispatch: Callable[["SwarmTask"], Mapping[str, Any]],
    verify: Callable[["SwarmTask", Mapping[str, Any]], bool],
) -> dict[str, Any]:
    """One ordered training→independent attestation→leadership activation path.

    The certifier must independently inspect checkpoint, cases and test
    artefacts, sign evidence and promote scoped claims in the REAL registry.
    It is not a privileged bypass. Even if certify returns success without
    promotions, activator refuses every unqualified leadership skill.
    """
    from .swarm_evolution import SwarmActivator, SwarmMission
    if not isinstance(activator, SwarmActivator) or not isinstance(mission, SwarmMission):
        raise SwarmRefused("governed swarm activator and typed mission required")
    if mission.leader_id != curriculum.agent_id or mission.scope != curriculum.scope:
        raise SwarmRefused("curriculum leader or scope does not match mission")
    registered = activator.agents.get(mission.leader_id)
    if registered is None or registered.source_revision != curriculum.revision:
        raise SwarmRefused("curriculum revision is not the registered leader revision")
    if not callable(certify):
        raise SwarmRefused("independent attestation callback required")
    report = train_leadership(curriculum, train=train, evaluate=evaluate, accept=accept)
    if report["outcome"] != "READY_FOR_INDEPENDENT_ATTESTATION":
        raise SwarmRefused("leadership training acceptance not satisfied")
    # The certifier receives a detached report and cannot mutate returned evidence.
    certify(deepcopy(report))
    payload = {key: value for key, value in report.items() if key != "report_sha256"}
    if hashlib.sha256(_canonical(payload)).hexdigest() != report["report_sha256"]:
        raise SwarmRefused("training report integrity check failed")

    # Every promoted leadership claim used by this lifecycle must attest this
    # exact report digest, preventing unrelated pre-existing claims from being reused.
    for skill in sorted(LEADER_SKILLS):
        claim_id = registered.capability_claims.get(skill)
        claim = activator.qualification.active_claim(
            claim_id=claim_id,
            source_revision=registered.source_revision,
            domain="euclid.agent.skill",
            task_scope=mission.scope,
        )
        if claim is None or not any(
            record.artifact_sha256 == report["report_sha256"]
            for record in claim.evidence
        ):
            raise SwarmRefused(
                "leadership qualification is not bound to this training report"
            )

    result = activator.activate(mission, dispatch=dispatch, verify=verify)
    return {"training": report, "swarm": result}
