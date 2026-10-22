"""HYBA Data — sealed claims register (code elevated to documentation).

Doctrine (board):
- We elevate code to meet documentation, always.
- We do not have banned claims. Claims that are not external-ready are RESTRICTED.
- RESTRICTED = not ready for external use yet; we still implement, test, and elevate.
- Quantum comes from maths. First principles. Everything tested.
- EXTERNAL / BOUNDED / INTERNAL / RESTRICTED lanes.

This module is the machine-readable gate for marketing and product language.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ClaimLane(str, Enum):
    EXTERNAL = "EXTERNAL"
    BOUNDED = "BOUNDED"
    INTERNAL = "INTERNAL"
    RESTRICTED = "RESTRICTED"  # not external-ready; implement + elevate (never "banned")

    # legacy name — prefer RESTRICTED
    BANNED = "RESTRICTED"




@dataclass(frozen=True)
class SealedClaim:
    claim_id: str
    text: str
    lane: ClaimLane
    required_bounds: str = ""
    code_elevation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["lane"] = self.lane.value
        return d


# Canonical register — keep in sync with Notion: HYBA Data — Sealed Claims Register
SEALED_CLAIMS: List[SealedClaim] = [
    SealedClaim(
        "CAT_CIAAS",
        "Category is Computational Intelligence as a Service (CIaaS)",
        ClaimLane.EXTERNAL,
        "Always define; never default to SaaS",
    ),
    SealedClaim(
        "CAT_NOT_SAAS",
        "HYBA Data is not SaaS and does not bill or deliver as SaaS",
        ClaimLane.EXTERNAL,
    ),
    SealedClaim(
        "CO_HYBA_DATA",
        "HYBA Data is first-to-market company under HYBA Software Ltd",
        ClaimLane.EXTERNAL,
    ),
    SealedClaim(
        "HIERARCHY",
        "Company HYBA Data → Product HERMES → Engine PULVINI",
        ClaimLane.EXTERNAL,
    ),
    SealedClaim(
        "COMM_GAIN_SHARE",
        "Pricing intent: 25% of measured savings; no fee if savings not measured",
        ClaimLane.EXTERNAL,
        "Measured is mandatory",
        "savings_metering.compute_fee",
    ),
    SealedClaim(
        "COMM_NO_MAINT",
        "No maintenance fee — nothing to maintain under self-healing design",
        ClaimLane.EXTERNAL,
    ),
    SealedClaim(
        "TECH_PULVINI_SCOPE",
        "PULVINI φ-folds structured numerical / φ-pattern working sets only",
        ClaimLane.BOUNDED,
        "Always state data class",
        "data_class_gate.assert_eligible",
    ),
    SealedClaim(
        "TECH_M1_2_62",
        "~2.62× (φ² / depth-1 class) on structured numerical arrays",
        ClaimLane.BOUNDED,
        "Method + error + test hash; illustrative until sealed",
        "sealed_metric_card.get_external_metric",
    ),
    SealedClaim(
        "TECH_M2_PHI4",
        "~6.85–6.94× / 85.4% (φ⁴ / depth-4 narratives)",
        ClaimLane.INTERNAL,
        "Unreconciled for external use — elevate metric card to seal",
        "claim_closures.seal_m1_with_harness",
    ),
    SealedClaim(
        "TECH_M3_7_155",
        "7.155× commercial multiplier",
        ClaimLane.INTERNAL,
        "Requires customer seal (T3) — implement pilot measurement",
        "savings_metering.compute_savings",
    ),
    SealedClaim(
        "TECH_UNIVERSAL",
        "Universal / all-memory compression",
        ClaimLane.RESTRICTED,
        "Not external-ready: scope is structured/φ-pattern working sets; elevate honest scope language + product",
        "data_class_gate.assert_eligible",
    ),
    SealedClaim(
        "TECH_SELF_HEAL",
        "Self-healing / self-optimising software implemented",
        ClaimLane.BOUNDED,
        "Implemented with tests — not customer SLA until pack",
    ),
    SealedClaim(
        "TECH_99999",
        "99.999% uptime",
        ClaimLane.INTERNAL,
        "No sealed measurement pack yet — implement then elevate",
        "claim_closures.availability_measurement_pack",
    ),
    SealedClaim(
        "TECH_MULTICLOUD_STRATEGY",
        "Multi-cloud service availability strategy",
        ClaimLane.EXTERNAL,
        "Strategy only",
    ),
    SealedClaim(
        "TECH_MULTICLOUD_PROVEN",
        "Multi-cloud proven production on named providers",
        ClaimLane.INTERNAL,
        "Until certificates sealed — implement proofs",
        "claim_closures.issue_multi_cloud_certificates",
    ),
    SealedClaim(
        "TECH_OLOG_N_SEARCH",
        "PHI-Space geodesic search O(log N)",
        ClaimLane.RESTRICTED,
        "Architecture Lane C — implement first principles + seal before external",
        "phi1_runtime.phi_dist",
    ),
    SealedClaim(
        "GTM_MINING_PROOF",
        "Live mining economics as HYBA Data customer proof",
        ClaimLane.RESTRICTED,
        "Not external-ready: mining is not Data product surface; product is quantum-for-data",
    ),
    SealedClaim(
        "GTM_IIT_PRODUCT",
        "Consciousness / IIT as customer product claim",
        ClaimLane.RESTRICTED,
        "Not external-ready — implement first principles + evidence before external",
    ),
    SealedClaim(
        "FIN_ORPHAN_TAM",
        "Orphan $T TAM / revenue projections without sealed citation card",
        ClaimLane.RESTRICTED,
        "Not external-ready until citation card sealed — implement TAM protocol",
    ),
    SealedClaim(
        "Q_FROM_MATHS",
        "Quantum comes from maths; substrate- and hardware-agnostic",
        ClaimLane.EXTERNAL,
        "Always",
        "quantum_honest.run_honest_quantum_battery",
    ),
    SealedClaim(
        "Q_SERVES_DATA",
        "Quantum serves data — not mining theatre",
        ClaimLane.EXTERNAL,
        "Always",
        "quantum_honest.help_hyba_data",
    ),
    SealedClaim(
        "FOLD_NEVER_TRUNCATE",
        "Compress by folding, not by truncating",
        ClaimLane.EXTERNAL,
        "Recon gate mandatory",
        "phi1_runtime.phi_fold_write",
    ),
]


# Phrases that must not leave the ecosystem until elevated / cited
_RESTRICTED_EXTERNAL_PHRASES = (
    "saas",
    "universal compression",
    "compresses all data",
    "compress everything",
    "100t",
    "$100t",
    "99.999",
    "7.155",
    "6.94",
    "85.4%",
    "no competition",
    "maintenance fee",
    "maintenance subscription",
)


def list_claims(lane: Optional[ClaimLane] = None) -> List[Dict[str, Any]]:
    rows = SEALED_CLAIMS if lane is None else [c for c in SEALED_CLAIMS if c.lane == lane]
    return [c.to_dict() for c in rows]


def get_claim(claim_id: str) -> Optional[SealedClaim]:
    for c in SEALED_CLAIMS:
        if c.claim_id == claim_id:
            return c
    return None


def may_leave_ecosystem(claim_id: str) -> bool:
    c = get_claim(claim_id)
    if c is None:
        return False
    return c.lane in (ClaimLane.EXTERNAL, ClaimLane.BOUNDED)


def assert_claim_allowed(
    claim_id: str, *, allow_internal: bool = False, allow_restricted: bool = False
) -> SealedClaim:
    c = get_claim(claim_id)
    if c is None:
        raise ValueError(f"Unknown claim_id: {claim_id}")
    if c.lane == ClaimLane.RESTRICTED and not allow_restricted:
        raise PermissionError(
            f"Claim is RESTRICTED (not external-ready) — implement, test, elevate: {claim_id}. "
            f"Bounds: {c.required_bounds}"
        )
    if c.lane == ClaimLane.INTERNAL and not allow_internal:
        raise PermissionError(
            f"Claim is INTERNAL — code/docs not elevated for external release: {claim_id}"
        )
    return c


def scan_text_for_restricted_language(text: str) -> List[str]:
    """Return restricted external-phrase hits (not ready to leave without elevation)."""
    raw = text or ""
    t = raw.lower().replace(" ", "")
    hits = []
    for p in _RESTRICTED_EXTERNAL_PHRASES:
        key = p.replace(" ", "")
        if key in t or p in raw.lower():
            hits.append(p)
    return hits


# Backward-compatible aliases
scan_text_for_banned_language = scan_text_for_restricted_language
_BANNED_PHRASES = _RESTRICTED_EXTERNAL_PHRASES


def gate_external_copy(text: str) -> Dict[str, Any]:
    """Gate marketing copy before it leaves the ecosystem."""
    hits = scan_text_for_restricted_language(text)
    return {
        "allowed": len(hits) == 0,
        "restricted_hits": hits,
        "banned_hits": hits,  # compat
        "doctrine": (
            "We do not ban claims forever. RESTRICTED = not external-ready. "
            "Implement first principles, test, elevate code to documentation. "
            "If criteria not satisfied, it does not leave the ecosystem."
        ),
    }


def register_summary() -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for c in SEALED_CLAIMS:
        counts[c.lane.value] = counts.get(c.lane.value, 0) + 1
    return {
        "company": "HYBA Data",
        "parent": "HYBA Software Ltd",
        "claim_count": len(SEALED_CLAIMS),
        "by_lane": counts,
        "elevation_rule": "We elevate code to meet documentation, always.",
        "no_banned_claims": True,
        "restricted_means": "Not external-ready yet — implement, test, elevate",
        "quantum_from_maths": True,
        "claims": list_claims(),
    }
