"""Phase 1 — Reconciliation lock-in: external-facing metrics only.

EXTERNAL-safe:
  - M1 ~2.62× (BOUNDED, structured numerical, method required)
  - sensitivity m ∈ {1.5, 2.0, 2.6}

INTERNAL (DD / engineering only):
  - M2 6.85–6.94× / ~85.4%
  - M3 7.155×
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from hyba_data.savings_metering import ALLOWED_ILLUSTRATIVE_M
from hyba_data.sealed_claims import ClaimLane, get_claim, may_leave_ecosystem
from hyba_data.sealed_metric_card import get_metric

M1_RATIO = 2.62
SENSITIVITY_M: Tuple[float, ...] = ALLOWED_ILLUSTRATIVE_M  # (1.5, 2.0, 2.6)
M2_RATIO_LOW = 6.85
M2_RATIO_HIGH = 6.94
M3_RATIO = 7.155

DOCTRINE_LINE = "geometry + measure + gain-share"


def external_metric_pack() -> Dict[str, Any]:
    m1 = get_metric("M1")
    return {
        "doctrine": DOCTRINE_LINE,
        "external_only": {
            "M1": {
                "ratio": m1.ratio,
                "lane": m1.lane.value,
                "data_class": m1.data_class,
                "mode": m1.mode,
                "required_bounds": "method + data class + recon gate",
            },
            "sensitivity_m": list(SENSITIVITY_M),
        },
        "internal_only": {
            "M2": {
                "ratio_range": [M2_RATIO_LOW, M2_RATIO_HIGH],
                "lane": "INTERNAL",
                "use": "DD / engineering annex only",
            },
            "M3": {
                "ratio": M3_RATIO,
                "lane": "INTERNAL",
                "use": "Until T3 customer seal",
            },
        },
        "fee": {
            "rate": 0.25,
            "formula": "Fee = 0.25 × Measured_Savings; Fee = 0 if unmeasured",
            "category": "CIaaS",
            "not": ["SaaS seats", "maintenance subscription"],
        },
    }


def assert_external_ratio_allowed(m: float, *, measured: bool = False) -> None:
    """Raise if ratio must not leave ecosystem as external fact."""
    if abs(m - M1_RATIO) < 1e-9:
        return
    if m in SENSITIVITY_M:
        return
    if abs(m - M2_RATIO_LOW) < 1e-9 or abs(m - M2_RATIO_HIGH) < 1e-9 or abs(m - 6.94) < 1e-9:
        if not measured:
            raise PermissionError("M2 ratios are INTERNAL — not external without seal/measurement")
        return
    if abs(m - M3_RATIO) < 1e-9:
        if not measured:
            raise PermissionError("M3 is INTERNAL until T3 customer seal")
        return
    # custom measured pilot ok
    if measured:
        return
    raise PermissionError(
        f"m={m} not in external set (M1={M1_RATIO} or sensitivity {SENSITIVITY_M}) "
        "unless measured pilot"
    )


def external_copy_ok(text: str) -> Dict[str, Any]:
    """Heuristic gate for GTM copy (Phase 1)."""
    t = (text or "").lower()
    hits: List[str] = []
    for bad in (
        "6.85",
        "6.94",
        "85.4%",
        "7.155",
        "saas seat",
        "maintenance fee",
        "maintenance subscription",
        "universal compression",
        "70b on 8",
    ):
        if bad in t:
            hits.append(bad)
    return {
        "allowed": len(hits) == 0,
        "hits": hits,
        "doctrine": DOCTRINE_LINE,
        "external_metrics": external_metric_pack()["external_only"],
    }


def claim_lane_snapshot() -> Dict[str, Any]:
    return {
        "M1_may_leave": may_leave_ecosystem("TECH_M1_2_62"),
        "M2_claim": get_claim("TECH_M2_PHI4").lane.value if get_claim("TECH_M2_PHI4") else None,
        "M3_claim": get_claim("TECH_M3_7_155").lane.value if get_claim("TECH_M3_7_155") else None,
        "pack": external_metric_pack(),
    }
