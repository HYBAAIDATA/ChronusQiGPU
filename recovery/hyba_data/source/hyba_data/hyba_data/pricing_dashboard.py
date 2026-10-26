"""CIaaS pricing dashboard — measured savings only (no seats / maintenance).

Fee = 0.25 × Measured_Savings
Fee = 0 if savings not measured
Sensitivity m ∈ {1.5, 2.0, 2.6}; external viability sketch m ≥ 2 for 2× list.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from hyba_data.external_metrics import DOCTRINE_LINE, M1_RATIO, SENSITIVITY_M
from hyba_data.savings_metering import GAIN_SHARE_RATE, compute_savings


def compute_dashboard(
    *,
    s_memory: float,
    f: float = 0.4,
    s_overhead: float = 0.0,
    measured: bool = False,
    list_price_multiplier: float = 2.0,
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for m in SENSITIVITY_M:
        r = compute_savings(
            s_memory=s_memory,
            f=f,
            m_eff=m,
            s_overhead=s_overhead,
            measured=measured,
        )
        # break-even vs list_price_multiplier × commodity: customer wins if list/m < 1
        customer_unit_cost_factor = list_price_multiplier / m
        rows.append(
            {
                "m": m,
                "gross_savings": r.gross_savings,
                "hyba_fee": r.hyba_fee,
                "measured": r.measured,
                "customer_unit_cost_factor": customer_unit_cost_factor,
                "customer_wins_vs_list": customer_unit_cost_factor < 1.0,
                "external_viability_m_ge_2": m >= 2.0,
            }
        )
    # M1 reference (BOUNDED) — not auto fee unless measured
    m1 = compute_savings(
        s_memory=s_memory, f=f, m_eff=M1_RATIO, s_overhead=s_overhead, measured=measured
    )
    return {
        "doctrine": DOCTRINE_LINE,
        "category": "CIaaS",
        "fee_rate": GAIN_SHARE_RATE,
        "formula": "Fee = 0.25 × Measured_Savings; Fee = 0 if unmeasured",
        "not": ["SaaS seats", "maintenance subscription", "unmeasured success fee"],
        "s_memory": s_memory,
        "f": f,
        "measured": measured,
        "sensitivity_rows": rows,
        "m1_bounded": {
            "m": M1_RATIO,
            "gross_savings": m1.gross_savings,
            "hyba_fee": m1.hyba_fee,
            "lane": "BOUNDED",
        },
        "list_price_multiplier": list_price_multiplier,
        "viability_note": "For list≈2× commodity, customer economics need measured m>2",
    }


def write_dashboard_artifact(
    *,
    s_memory: float = 1_000_000.0,
    f: float = 0.4,
    artifact_dir: str | Path = "artifacts/hyba_data/elevation",
) -> Dict[str, Any]:
    un = compute_dashboard(s_memory=s_memory, f=f, measured=False)
    me = compute_dashboard(s_memory=s_memory, f=f, measured=True)
    out = {"unmeasured": un, "measured": me}
    art = Path(artifact_dir)
    art.mkdir(parents=True, exist_ok=True)
    p = art / "CIAAS_PRICING_DASHBOARD.json"
    p.write_text(json.dumps(out, indent=2))
    out["artifact"] = str(p)
    return out
