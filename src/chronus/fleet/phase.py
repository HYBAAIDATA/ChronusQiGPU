# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Commercial tiers with the option to scale (Planetary Fabric Rev. 3 phases).

The spec's four phases are commercial tiers. Each tier carries a provisioned
entitlement: logical warps (32 logical lanes each) of the scheduling lattice
and storage in TB (10**12 bytes). Entitlements are provisioning, never
performance claims: warps and lanes are logical units of the scheduling
lattice, not physical cores, and an entitlement of 160,000 warps says nothing
about hardware anyone owns.

Above Tier 4 sits the Scale tier, whose entitlement is set per contract: an
explicit figure the operator supplies. There is no open-ended tier.

Demand beyond the current tier's entitlement is never refused outright. The
fleet records a scale event, admits the work when a signed scale grant
authorises a tier that covers it (``chronus.fleet.scale``) and otherwise
queues it and reports "scale available: Tier N+1". Moving down a tier is
always possible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Iterable

from chronus.fleet.canonical import iso_utc
from chronus.fleet.errors import TierGateRejected

WARP_LANES = 32
BYTES_PER_TB = 10**12
SCALE_TIER_NUMBER = 5
ENTITLEMENT_KIND = "provisioned entitlement (not a performance claim)"

#: Fleet transports. The spec leaves PHASE_n.connectors undefined; for the
#: compute fabric they are the transports a tier needs (docs/fleet/DECISIONS.md).
CONNECTOR_FLEET_HTTP = "fleet-http"
CONNECTOR_FLEET_TLS = "fleet-tls"
TLS_CONNECTORS = frozenset({CONNECTOR_FLEET_HTTP, CONNECTOR_FLEET_TLS})


def _whole(value: Any, what: str, minimum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{what} must be an explicit whole number >= {minimum}")
    return value


@dataclass(frozen=True)
class Tier:
    name: str
    number: int
    warps: int
    simd_lanes: int
    storage_tb: int
    connectors: frozenset[str] = field(default_factory=frozenset)
    capabilities: tuple[str, ...] = ()
    contract: str | None = None

    def __post_init__(self) -> None:
        _whole(self.warps, f"{self.name} warps", 1)
        _whole(self.storage_tb, f"{self.name} storage_tb", 0)
        if self.simd_lanes != self.warps * WARP_LANES:
            raise ValueError(f"{self.name}: simd_lanes must equal warps * {WARP_LANES}")

    @property
    def label(self) -> str:
        return "Scale" if self.number == SCALE_TIER_NUMBER else f"Tier {self.number}"

    @property
    def storage_bytes(self) -> int:
        return self.storage_tb * BYTES_PER_TB

    def covers(self, warps: int, lanes: int, storage_bytes: int) -> bool:
        return warps <= self.warps and lanes <= self.simd_lanes and storage_bytes <= self.storage_bytes

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "number": self.number,
            "warps": self.warps,
            "simd_lanes": self.simd_lanes,
            "storage_tb": self.storage_tb,
            "connectors": sorted(self.connectors),
            "capabilities": list(self.capabilities),
            "contract": self.contract,
            "kind": ENTITLEMENT_KIND,
        }


TIER_1 = Tier(
    "TIER_1", 1, 1024, 32_768, 100,
    frozenset({CONNECTOR_FLEET_HTTP}),
    ("1.1 instant onboarding", "1.2 in-place schema discovery", "1.3 Binet-Zeckendorf ingest"),
)
TIER_2 = Tier(
    "TIER_2", 2, 10_000, 320_000, 1000, TLS_CONNECTORS,
    ("2.1 disaggregated pools", "2.2 H4 crossbar routing", "2.3 blind-check fault recovery"),
)
TIER_3 = Tier(
    "TIER_3", 3, 40_000, 1_280_000, 10_000, TLS_CONNECTORS,
    ("3.1 air-gapped deployment", "3.2 sheaf prompt filtration", "3.3 exact anyon braids", "3.4 ML-DSA-65 signing"),
)
TIER_4 = Tier(
    "TIER_4", 4, 160_000, 5_120_000, 100_000, TLS_CONNECTORS,
    ("4.1 value-share reconciliation", "4.2 base-phi tensor execution", "4.3 zk-STARK verification"),
)
TIERS: tuple[Tier, ...] = (TIER_1, TIER_2, TIER_3, TIER_4)


def scale_tier(warps: int, storage_tb: int, contract: str) -> Tier:
    """The Scale tier for one contract: explicit warps and TB, at least Tier 4's figures."""
    _whole(warps, "Scale warps", TIER_4.warps)
    _whole(storage_tb, "Scale storage_tb", TIER_4.storage_tb)
    if not isinstance(contract, str) or not contract.strip():
        raise ValueError("the Scale tier needs the contract reference that sets its figure")
    return Tier(
        "SCALE", SCALE_TIER_NUMBER, warps, warps * WARP_LANES, storage_tb, TLS_CONNECTORS,
        ("contracted entitlement",), contract.strip()[:120],
    )


def tier_by_number(number: int) -> Tier:
    for tier in TIERS:
        if tier.number == number:
            return tier
    raise ValueError(f"no Tier {number}; tiers are 1 to 4, and Scale is granted per contract")


def next_tier_label(tier: Tier) -> str:
    """What scaling past ``tier`` means: the next tier, or a new Scale contract figure."""
    if tier.number < TIER_4.number:
        return tier_by_number(tier.number + 1).label
    return "Scale (contract figure)"


def scale_available_message(tier: Tier) -> str:
    return f"scale available: {next_tier_label(tier)}"


def lattice_footprint(virtual_units: int) -> tuple[int, int]:
    """(logical warps, logical lanes) occupied by a resident lattice of virtual units."""
    if not isinstance(virtual_units, int) or virtual_units < 0:
        raise ValueError("virtual_units must be a non-negative integer")
    return -(-virtual_units // WARP_LANES), virtual_units


def _storage_bytes(storage_used_tb: Any) -> Fraction:
    value = Fraction(storage_used_tb) if not isinstance(storage_used_tb, float) else Fraction(str(storage_used_tb))
    if value < 0:
        raise ValueError("storage_used_tb must be non-negative")
    return value * BYTES_PER_TB


@dataclass(frozen=True)
class EntitlementCheck:
    """Demand against one tier's entitlement, with every dimension that is over it."""

    tier: str
    active_warps: int
    simd_lanes: int
    storage_used_bytes: int
    connectors_required: tuple[str, ...]
    connectors_available: tuple[str, ...]
    over_entitlement: tuple[str, ...]
    missing_connectors: tuple[str, ...]
    evaluated_at: str

    @property
    def within_entitlement(self) -> bool:
        return not self.over_entitlement and not self.missing_connectors

    @property
    def passed(self) -> bool:
        return self.within_entitlement

    @property
    def reasons(self) -> tuple[str, ...]:
        missing = ()
        if self.missing_connectors:
            missing = (f"connectors needed for {self.tier}: {', '.join(self.missing_connectors)}",)
        return self.over_entitlement + missing

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "active_warps": self.active_warps,
            "simd_lanes": self.simd_lanes,
            "storage_used_bytes": self.storage_used_bytes,
            "connectors_required": list(self.connectors_required),
            "connectors_available": list(self.connectors_available),
            "within_entitlement": self.within_entitlement,
            "over_entitlement": list(self.over_entitlement),
            "missing_connectors": list(self.missing_connectors),
            "evaluated_at": self.evaluated_at,
        }


def evaluate_entitlement(
    tier: Tier,
    active_warps: int,
    simd_lanes: int,
    storage_used_tb: Any,
    available_connectors: Iterable[str],
) -> EntitlementCheck:
    available = frozenset(available_connectors)
    storage = _storage_bytes(storage_used_tb)
    over = []
    if active_warps > tier.warps:
        over.append(f"active_warps {active_warps} > {tier.label} entitlement {tier.warps}")
    if simd_lanes > tier.simd_lanes:
        over.append(f"simd_lanes {simd_lanes} > {tier.label} entitlement {tier.simd_lanes}")
    if storage > tier.storage_bytes:
        over.append(f"storage {storage} bytes > {tier.label} entitlement {tier.storage_tb} TB")
    return EntitlementCheck(
        tier=tier.name,
        active_warps=int(active_warps),
        simd_lanes=int(simd_lanes),
        storage_used_bytes=int(storage),
        connectors_required=tuple(sorted(tier.connectors)),
        connectors_available=tuple(sorted(available)),
        over_entitlement=tuple(over),
        missing_connectors=tuple(sorted(tier.connectors - available)),
        evaluated_at=iso_utc(),
    )


def TIER_GATE(  # noqa: N802 - the spec's PHASE_GATE, renamed for tiers
    tier: Tier,
    active_warps: int,
    simd_lanes: int,
    storage_used_tb: Any,
    available_connectors: Iterable[str],
) -> bool:
    """True when demand is within the tier's entitlement and its connectors are present."""
    return evaluate_entitlement(tier, active_warps, simd_lanes, storage_used_tb, available_connectors).within_entitlement


#: The spec's name for TIER_GATE (docs/fleet/DECISIONS.md).
PHASE_GATE = TIER_GATE


def require_connectors(tier: Tier, available_connectors: Iterable[str], action: str) -> None:
    missing = sorted(tier.connectors - frozenset(available_connectors))
    if missing:
        raise TierGateRejected(
            f"{action}: {tier.label} needs connectors {', '.join(missing)} (start the coordinator with --tls)",
            tuple(f"connector missing: {m}" for m in missing),
        )
