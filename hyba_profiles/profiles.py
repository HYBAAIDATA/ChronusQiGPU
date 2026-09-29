from __future__ import annotations

from dataclasses import dataclass

from .model import Tier


@dataclass(frozen=True)
class ProfileSpec:
    name: str
    dominant_tiers: tuple[Tier, ...]
    required_modules: frozenset[str]
    optional_modules: frozenset[str]
    prohibited_modules: frozenset[str]
    external_assessments: tuple[str, ...]
    requires_customer_keys: bool = False
    requires_local_identity: bool = False
    requires_air_gap: bool = False
    requires_private_networking: bool = False
    requires_human_approval: bool = False


COMMON = frozenset({"core", "mla1517", "primedb", "al_haras", "proof_service", "observe"})
RESEARCH = frozenset({"privacy_compute", "quantum_access", "autonomous_ops", "energy"})
PROFILES = {
    "developer": ProfileSpec(
        "developer",
        (Tier.T1, Tier.T5),
        COMMON,
        frozenset({"studio", "functions", "quality"}) | RESEARCH,
        frozenset(),
        (),
    ),
    "edge": ProfileSpec(
        "edge",
        (Tier.T0, Tier.T1, Tier.T4),
        COMMON | {"edge", "vault", "deploy"},
        frozenset({"flow", "quality", "functions"}),
        RESEARCH,
        (),
        True,
        True,
    ),
    "enterprise": ProfileSpec(
        "enterprise",
        (Tier.T1, Tier.T2, Tier.T4),
        COMMON
        | {
            "flow",
            "ontology",
            "quality",
            "model_gateway",
            "agent_fabric",
            "evidence",
            "vault",
            "deploy",
            "studio",
            "insight",
        },
        frozenset({"share", "federate", "functions", "metering", "edge"}),
        RESEARCH,
        ("security_review", "disaster_recovery_exercise"),
        True,
        False,
        False,
        True,
        True,
    ),
    "sovereign": ProfileSpec(
        "sovereign",
        (Tier.T0, Tier.T1, Tier.T4),
        COMMON | {"evidence", "vault", "edge", "deploy", "quality"},
        frozenset(
            {
                "flow",
                "ontology",
                "agent_fabric",
                "studio",
                "functions",
                "insight",
                "share",
                "federate",
            }
        ),
        RESEARCH | {"model_gateway"},
        ("independent_security_assessment", "sovereign_authorization"),
        True,
        True,
        True,
        True,
        True,
    ),
    "hyperscaler": ProfileSpec(
        "hyperscaler",
        (Tier.T2, Tier.T3, Tier.T5),
        COMMON
        | {
            "flow",
            "quality",
            "model_gateway",
            "agent_fabric",
            "evidence",
            "vault",
            "deploy",
            "metering",
        },
        frozenset({"ontology", "share", "federate", "studio", "functions", "insight", "edge"})
        | RESEARCH,
        frozenset(),
        ("multi_tenant_isolation_assessment", "regional_recovery_exercise"),
        True,
        False,
        False,
        True,
        True,
    ),
}
PROFILES["government"] = PROFILES["sovereign"]
