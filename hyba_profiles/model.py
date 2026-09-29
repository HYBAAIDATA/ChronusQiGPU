from __future__ import annotations
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

class Tier(str, Enum):
    T0 = "T0_PROOF_REGISTER"
    T1 = "T1_VERTEX"
    T2 = "T2_SHELL"
    T3 = "T3_M32_FABRIC"
    T4 = "T4_SOVEREIGN_PERSISTENT"
    T5 = "T5_EXTERNAL_COMPAT"

class SpeedClass(str, Enum):
    S0 = "S0_IMMEDIATE"
    S1 = "S1_ULTRA_LOW"
    S2 = "S2_LOCAL_FABRIC"
    S3 = "S3_FABRIC"
    S4 = "S4_PERSISTENCE"
    S5 = "S5_COMPATIBILITY"

class GateStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    CONDITIONALLY_ACCEPTED = "CONDITIONALLY_ACCEPTED"
    REJECTED = "REJECTED"
    NOT_EXECUTED = "NOT_EXECUTED"
    EXTERNAL_ASSESSMENT_REQUIRED = "EXTERNAL_ASSESSMENT_REQUIRED"

@dataclass(frozen=True)
class TierPolicy:
    tier: Tier
    speed_class: SpeedClass
    deterministic_proof_required: bool
    folded_query_allowed: bool
    lineage_required: bool

@dataclass(frozen=True)
class ModuleEvidence:
    module: str
    version: str
    source_verified: bool = False
    tests_passed: bool = False
    deployment_verified: bool = False
    external_assessment: bool = False
    evidence_refs: tuple[str, ...] = ()

@dataclass(frozen=True)
class AssemblyIntent:
    name: str
    deployment_profile: str
    deployment_seed: str
    industry: str
    use_cases: tuple[str, ...]
    risk_level: str
    sovereignty: str
    exactness: str
    resilience: str
    economics: tuple[str, ...]
    modules: tuple[str, ...]
    module_evidence: tuple[ModuleEvidence, ...]
    dominant_tiers: tuple[Tier, ...]
    customer_managed_keys: bool = False
    local_identity_provider: bool = False
    air_gapped: bool = False
    private_networking: bool = False
    human_approval_for_high_risk_actions: bool = False
    silent_fallback: bool = False

@dataclass(frozen=True)
class GateCheck:
    name: str
    passed: bool
    required: bool
    evidence: str

@dataclass(frozen=True)
class GateReport:
    profile: str
    status: GateStatus
    checks: tuple[GateCheck, ...]
    blockers: tuple[str, ...]
    external_assessments: tuple[str, ...]

@dataclass(frozen=True)
class AssemblyBlueprint:
    profile: str
    modules: tuple[str, ...]
    ordered_modules: tuple[str, ...]
    tiers: tuple[Tier, ...]
    policies: dict[str, Any]
    threat_model: tuple[str, ...]
    compliance_crosswalk: tuple[str, ...]
    resource_plan: dict[str, Any]

@dataclass(frozen=True)
class AssemblyLock:
    schema_version: str
    manifest_hash: str
    modules: tuple[str, ...]
    versions: tuple[tuple[str, str], ...]
    policy_hash: str
    evidence_hash: str
    signature_algorithm: str
    signature: str

@dataclass(frozen=True)
class CompilationResult:
    blueprint: AssemblyBlueprint
    lock: AssemblyLock
    gate: GateReport
    explanation: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        def convert(value: Any) -> Any:
            if isinstance(value, Enum): return value.value
            if hasattr(value, "__dataclass_fields__"):
                return {k: convert(v) for k, v in asdict(value).items()}
            if isinstance(value, dict): return {k: convert(v) for k, v in value.items()}
            if isinstance(value, (tuple, list)): return [convert(v) for v in value]
            return value
        return convert(self)
