"""Advisory quotes that become binding only when is_binding is true.

Quotes are behavior-only: size, tier, space_bytes, contract version, evidence
hash. How space is derived is not exposed on the wire beyond the measured
envelope class.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from chronus.core.seal import assert_sealed

CONTRACT_VERSION = "procurement-contract.v1"

# Public tier vocabulary — measured convergence class only.
PUBLIC_TIERS = frozenset(
    {"TIER_GEOMETRIC", "TIER_POLYNOMIAL", "TIER_STATISTICAL", "TIER_SUSPENDED"}
)

# Pilot envelope: bytes reserved per unit of requested size by tier.
# Not a claim of DRAM savings — a procurement accounting unit.
_BYTES_PER_UNIT: dict[str, int] = {
    "TIER_GEOMETRIC": 4096,
    "TIER_POLYNOMIAL": 8192,
    "TIER_STATISTICAL": 16384,
    "TIER_SUSPENDED": 0,
}


def live_evidence_hash(*, contract_version: str = CONTRACT_VERSION) -> str:
    """Stable hash of the live procurement contract surface for quote binding."""
    payload = {
        "contract_version": contract_version,
        "tiers": sorted(PUBLIC_TIERS),
        "bytes_per_unit": _BYTES_PER_UNIT,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()


def build_quote(
    size: int,
    *,
    tier: str = "TIER_POLYNOMIAL",
    contract_version: str | None = None,
    evidence_hash: str | None = None,
    releases_old: int = 0,
) -> dict[str, Any]:
    """Build a quote. Suspended / invalid sizes are non-binding."""
    version = contract_version or CONTRACT_VERSION
    evidence = evidence_hash or live_evidence_hash(contract_version=version)
    assert_sealed(tier, context="quote.tier")
    assert_sealed(version, context="quote.contract_version")

    if tier not in PUBLIC_TIERS:
        verdict = "out_of_range"
        binding = False
        space = 0
    elif tier == "TIER_SUSPENDED":
        verdict = "suspended"
        binding = False
        space = 0
    elif size <= 0:
        verdict = "degenerate"
        binding = False
        space = 0
    else:
        verdict = "within_envelope"
        binding = releases_old == 0 and version == CONTRACT_VERSION
        space = int(size) * _BYTES_PER_UNIT[tier]

    quote = {
        "size": int(size),
        "tier": tier,
        "space_bytes": space,
        "verdict": verdict,
        "is_binding": binding,
        "releases_old": int(releases_old),
        "contract_version": version,
        "evidence_hash": evidence,
        "assignment_basis": (
            "tier class is assigned by measured convergence behavior under our "
            "qualification harness"
        ),
    }
    assert_sealed(json.dumps(quote), context="quote")
    return quote
