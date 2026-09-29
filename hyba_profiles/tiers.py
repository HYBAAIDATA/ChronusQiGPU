from __future__ import annotations
from .model import SpeedClass, Tier, TierPolicy

TIER_POLICY = {
    Tier.T0: TierPolicy(Tier.T0, SpeedClass.S0, True, False, True),
    Tier.T1: TierPolicy(Tier.T1, SpeedClass.S1, True, True, True),
    Tier.T2: TierPolicy(Tier.T2, SpeedClass.S2, False, True, True),
    Tier.T3: TierPolicy(Tier.T3, SpeedClass.S3, False, True, True),
    Tier.T4: TierPolicy(Tier.T4, SpeedClass.S4, True, True, True),
    Tier.T5: TierPolicy(Tier.T5, SpeedClass.S5, False, False, False),
}


class ProofRequired(ValueError):
    pass


class LineageRequired(ValueError):
    pass


class FoldedQueryNotAllowed(ValueError):
    pass


def authorize_placement(
    *, tier: Tier, cassini_valid: bool, lineage_present: bool, folded_query: bool = False
) -> TierPolicy:
    policy = TIER_POLICY[tier]
    if policy.deterministic_proof_required and not cassini_valid:
        raise ProofRequired(tier.value)
    if policy.lineage_required and not lineage_present:
        raise LineageRequired(tier.value)
    if folded_query and not policy.folded_query_allowed:
        raise FoldedQueryNotAllowed(tier.value)
    return policy
