"""Versioned, deterministic contracts shared by EUCLID organs."""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping

SCHEMA_VERSION = "euclid.contracts/1"


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def domain_hash(domain: str, value: Any) -> str:
    if not domain or "\x00" in domain:
        raise ValueError("a non-empty hash domain is required")
    return hashlib.sha256(domain.encode() + b"\0" + canonical_json(value)).hexdigest()


class Authority(str, Enum):
    READ_ONLY = "read-only"
    PROPOSE = "propose"
    MUTATE_WORLD = "mutate-world"
    MINING_POLICY_ONLY = "mining-policy-only"


class Health(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class RewardAuthority(str, Enum):
    MEASURED_ENVIRONMENT = "measured-environment"
    OPERATOR = "operator"
    VALIDATED_SIMULATION = "validated-simulation"
    NONE = "none"


@dataclass(frozen=True)
class Mission:
    mission_id: str
    goal: str
    domain: str
    creator_id: str
    created_at: float = field(default_factory=time.time)
    schema: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not all((self.mission_id.strip(), self.goal.strip(), self.domain.strip(),
                    self.creator_id.strip())):
            raise ValueError("mission fields must be non-empty")


@dataclass(frozen=True)
class Capability:
    capability_id: str
    organ_id: str
    authority: Authority
    version: str
    evidence_source: str

    def __post_init__(self) -> None:
        if not all((self.capability_id, self.organ_id, self.version, self.evidence_source)):
            raise ValueError("capability fields must be non-empty")


@dataclass(frozen=True)
class Experience:
    experience_id: str
    mission_id: str
    domain: str
    source: str
    observation: Mapping[str, Any]
    action: str
    outcome: Mapping[str, Any]
    reward: float | None
    reward_authority: RewardAuthority
    provenance: str
    uncertainty: float
    replay_id: str
    created_at: float = field(default_factory=time.time)
    schema: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not all((
            self.experience_id, self.mission_id, self.domain, self.source,
            self.action, self.provenance, self.replay_id
        )):
            raise ValueError("experience identity and provenance are required")
        if not math.isfinite(self.uncertainty) or not 0.0 <= self.uncertainty <= 1.0:
            raise ValueError("uncertainty must be finite and in [0,1]")
        if self.reward is not None and not math.isfinite(float(self.reward)):
            raise ValueError("reward must be finite")
        if self.reward_authority is RewardAuthority.NONE and self.reward is not None:
            raise ValueError("unverified reward is forbidden")
        if self.reward_authority is not RewardAuthority.NONE and self.reward is None:
            raise ValueError("reward authority requires a reward")

    def digest(self) -> str:
        return domain_hash("euclid.experience.v1", asdict(self))
