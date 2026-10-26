"""Model/tool/policy-bound identity, progression and lifecycle are not authority."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ._contracts import ContractError, integer, sha, text


class ProgressionStage(Enum):
    ANSWER_QUESTIONS = 0
    PRODUCE_WORK = 1
    TAKE_ACTIONS = 2
    COMPLETE_PROJECTS = 3
    OWN_OUTCOMES = 4
    DISCOVER_KNOWLEDGE = 5


class LifecycleState(Enum):
    DRAFT = 0
    EVALUATION = 1
    ACTIVE = 2
    SUSPENDED = 3
    QUARANTINED = 4
    RETIRED = 5


@dataclass(frozen=True)
class AgentIdentity:
    id: str
    born_at: int
    owner: str
    operator: str
    policy_version: str
    model_fingerprint: str
    tool_fingerprint: str
    training_process: str
    lineage: tuple[str, ...] = ()
    institutions: tuple[str, ...] = ()
    jurisdictions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value in (
            self.id,
            self.owner,
            self.operator,
            self.policy_version,
            self.training_process,
        ):
            text(value)

        integer(self.born_at)
        sha(self.model_fingerprint)
        sha(self.tool_fingerprint)

        for values in (self.lineage, self.institutions, self.jurisdictions):
            if type(values) is not tuple or len(values) > 64:
                raise ContractError("bounded immutable identity sets required")
            for value in values:
                text(value)
