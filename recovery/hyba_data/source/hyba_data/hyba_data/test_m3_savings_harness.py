"""M3 commercial multiplier — INTERNAL until T3 customer seal.

Harness validates savings metering math; does NOT authorize 7.155× as EXTERNAL.
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path

from hyba_data.savings_metering import compute_savings, sensitivity_table
from hyba_data.sealed_claims import ClaimLane, get_claim, may_leave_ecosystem
from hyba_data.sealed_metric_card import get_metric


def test_m3_metric_internal():
    m3 = get_metric("M3")
    assert m3.lane == ClaimLane.INTERNAL
    assert m3.ratio == 7.155
    assert may_leave_ecosystem("TECH_M3_7_155") is False


def test_savings_metering_integration():
    # measured fee only when measured=True
    un = compute_savings(s_memory=1_000_000, f=0.4, m_eff=2.0, measured=False)
    me = compute_savings(s_memory=1_000_000, f=0.4, m_eff=2.0, measured=True)
    assert un.hyba_fee == 0.0
    assert me.hyba_fee > 0.0
    # internal multiplier blocked when unmeasured
    try:
        compute_savings(s_memory=1e6, f=0.5, m_eff=7.155, measured=False)
        raise AssertionError("should block unmeasured 7.155")
    except PermissionError:
        pass


def test_m3_internal_evidence_pack_artifact():
    sens = sensitivity_table(1_000_000_000.0)
    pack = {
        "metric_id": "M3",
        "ratio": 7.155,
        "lane": "INTERNAL",
        "status": "INTERNAL_UNTIL_T3_CUSTOMER_SEAL",
        "doctrine": "Elevate code to docs; customer seal required for commercial multiplier",
        "savings_harness": {
            "unmeasured_fee_must_be_zero": True,
            "measured_fee_positive": True,
            "blocks_unmeasured_7_155": True,
        },
        "sensitivity_illustrative": sens,
        "t3_requirements": [
            "Named customer or anonymised production telemetry",
            "Signed baseline and post-deploy measurement report",
            "Board seal of commercial multiplier for that engagement",
        ],
        "not_external": True,
    }
    art = Path("artifacts/hyba_data")
    art.mkdir(parents=True, exist_ok=True)
    (art / "M3_INTERNAL_PACK.json").write_text(json.dumps(pack, indent=2))
    c = get_claim("TECH_M3_7_155")
    assert c.lane == ClaimLane.INTERNAL


def main() -> int:
    failed = 0
    for name in sorted(n for n in globals() if n.startswith("test_")):
        try:
            globals()[name]()
            print("PASS", name)
        except Exception as e:
            failed += 1
            print("FAIL", name, type(e).__name__, e)
            traceback.print_exc()
    print(f"summary failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
