"""Doctrine compliance CI test — surfaces must enforce locked doctrine."""

from __future__ import annotations

import traceback
from pathlib import Path

from hyba_data.fold_doctrine import describe_fold_doctrine
from hyba_data.sealed_claims import ClaimLane, register_summary

ROOT = Path(__file__).resolve().parents[2]


def test_no_banned_lane_in_register():
    s = register_summary()
    assert s.get("no_banned_claims") is True
    assert "BANNED" not in s.get("by_lane", {})
    assert "RESTRICTED" in s.get("by_lane", {})


def test_fold_doctrine_invariants():
    d = describe_fold_doctrine()
    assert d["fold_never_truncate"] is True
    assert d["quantum_serves_data"] is True
    assert d["quantum_from_maths"] is True
    assert d["mining_bound"] is False


def test_required_doctrine_files_exist():
    required = [
        "doctrine_execution/ACTION_PLAN_STATUS.md",
        "doctrine_execution/RESTRICTED_ELEVATION_PLANS.md",
        "doctrine_execution/RESTRICTED_CLAIMS_REGISTER.md",
        "doctrine_execution/SEALED_CLAIMS_REGISTER.md",
        "doctrine_execution/TAM_CARD_TEMPLATE.md",
        "doctrine_execution/AUTONOMY_FABRIC.md",
        "doctrine_execution/MARKETING_MASTER.md",
        "doctrine_execution/DOCTRINE_AND_PHILOSOPHY.md",
        "doctrine_execution/DOCTRINE_DELIVERY.md",
        "python_backend/hyba_data/sealed_claims.py",
        "python_backend/hyba_data/phi1_runtime.py",
        ".github/workflows/doctrine_enforcement.yml",
    ]
    missing = [r for r in required if not (ROOT / r).exists()]
    assert not missing, missing


def test_ci_rejects_banned_lane_string_in_claim_enum():
    text = (ROOT / "python_backend/hyba_data/sealed_claims.py").read_text()
    assert 'RESTRICTED = "RESTRICTED"' in text
    # Must not define BANNED as a separate external-prohibition value
    assert 'BANNED = "BANNED"' not in text


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
