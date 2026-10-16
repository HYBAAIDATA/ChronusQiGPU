"""Host-authenticated independent assurance, exact target/task/artifact binding."""

from dataclasses import dataclass
from enum import IntEnum
from ._contracts import canonical
from .capabilities import RiskTier


class AssuranceLevel(IntEnum):
    NONE = 0
    SELF_ASSESSED = 1
    INTERNALLY_REVIEWED = 2
    EXTERNALLY_REVIEWED = 3
    CERTIFIED = 4


def assurance_required(trust, task_class):
    if task_class.risk_tier == RiskTier.T5_IRREVERSIBLE_OR_SAFETY_CRITICAL:
        return AssuranceLevel.CERTIFIED
    if task_class.risk_tier >= RiskTier.T4_EXTERNAL_CONSEQUENTIAL:
        return AssuranceLevel.EXTERNALLY_REVIEWED
    if task_class.risk_tier == RiskTier.T3_EXTERNAL_REVERSIBLE:
        return AssuranceLevel.EXTERNALLY_REVIEWED
    if task_class.risk_tier in (
        RiskTier.T1_INTERNAL_REVERSIBLE,
        RiskTier.T2_INTERNAL_CONSEQUENTIAL,
    ):
        return AssuranceLevel.INTERNALLY_REVIEWED
    if int(trust) >= 3:
        return AssuranceLevel.INTERNALLY_REVIEWED
    return AssuranceLevel.SELF_ASSESSED


@dataclass(frozen=True)
class AssuranceAttestation:
    task_key: str
    evidence_digest: str
    model_fingerprint: str
    tool_fingerprint: str
    policy_version: str
    verifier: str
    operator: str
    training_process: str
    level: AssuranceLevel
    expires_at: int
    signature: str

    def body(self):
        return canonical({k: v for k, v in self.__dict__.items() if k != "signature"})

    def admissible(self, identity, task, metrics, now, verifier_keys):
        verifier = verifier_keys.get(self.verifier)
        if (
            verifier is None
            or type(self.level) is not AssuranceLevel
            or self.task_key != task.key
            or self.evidence_digest != metrics.evidence_digest
            or self.model_fingerprint != identity.model_fingerprint
            or self.tool_fingerprint != identity.tool_fingerprint
            or self.policy_version != identity.policy_version
            or now >= self.expires_at
        ):
            return False
        independent = (
            self.verifier != identity.id
            and self.operator != identity.operator
            and self.training_process != identity.training_process
        )
        if self.level >= AssuranceLevel.INTERNALLY_REVIEWED and not independent:
            return False
        return verifier.verify(self.body(), self.signature)
