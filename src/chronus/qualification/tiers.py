"""Tier contracts and operations economics keyed by measured class."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class Tier(str, Enum):
    """Measured convergence classes. Assigned by harness, never declared."""

    GEOMETRIC = "TIER_GEOMETRIC"
    POLYNOMIAL = "TIER_POLYNOMIAL"
    STATISTICAL = "TIER_STATISTICAL"
    SUSPENDED = "TIER_SUSPENDED"


TIER_CONTRACT_VERSION = "tier-contract.v1"


@dataclass(frozen=True)
class TierContract:
    """Signed error-envelope contract shipped with a tier assignment."""

    tier: Tier
    tier_contract_version: str
    residual_bound_by_size: tuple[tuple[int, str], ...]  # (size, bound as decimal str)
    qualification_evidence_hash: str
    suspended: bool = False

    def to_public_dict(self) -> dict[str, Any]:
        """Customer-visible contract — behavior only, no mechanism tokens."""
        return {
            "tier": self.tier.value,
            "tier_contract_version": self.tier_contract_version,
            "envelope": {
                "residual_bound": [
                    {"size": size, "max_residual": bound}
                    for size, bound in self.residual_bound_by_size
                ]
            },
            "qualification_evidence_hash": self.qualification_evidence_hash,
            "suspended": self.suspended,
        }


@dataclass(frozen=True)
class TierEconomics:
    """Operations cost model: the customer buys the envelope, not the method."""

    tier: Tier
    service_level: str
    escalation_threshold: str
    review_budget_ccu: int
    relative_price_weight: float

    def to_public_dict(self) -> dict[str, Any]:
        return asdict(self) | {"tier": self.tier.value}


_ECONOMICS: dict[Tier, TierEconomics] = {
    Tier.GEOMETRIC: TierEconomics(
        tier=Tier.GEOMETRIC,
        service_level="envelope.tight",
        escalation_threshold="residual_violation_immediate",
        review_budget_ccu=8,
        relative_price_weight=1.0,
    ),
    Tier.POLYNOMIAL: TierEconomics(
        tier=Tier.POLYNOMIAL,
        service_level="envelope.bounded",
        escalation_threshold="residual_violation_review",
        review_budget_ccu=24,
        relative_price_weight=0.6,
    ),
    Tier.STATISTICAL: TierEconomics(
        tier=Tier.STATISTICAL,
        service_level="envelope.probabilistic",
        escalation_threshold="confidence_breach_review",
        review_budget_ccu=64,
        relative_price_weight=0.35,
    ),
    Tier.SUSPENDED: TierEconomics(
        tier=Tier.SUSPENDED,
        service_level="envelope.suspended",
        escalation_threshold="model_risk_alarm",
        review_budget_ccu=0,
        relative_price_weight=0.0,
    ),
}


def economics_for_tier(tier: Tier) -> TierEconomics:
    return _ECONOMICS[tier]
