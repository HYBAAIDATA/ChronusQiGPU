"""Autonomy fabric (Salamander) — BOUNDED claim tests."""
from __future__ import annotations

import traceback


def test_salamander_cycle_runs():
    from hyba_substrate.salamander_support import run_autonomic_cycle
    r = run_autonomic_cycle()
    assert isinstance(r, dict)
    assert r  # non-empty

def test_self_heal_claim_bounded():
    from hyba_data.sealed_claims import ClaimLane, get_claim, may_leave_ecosystem
    c = get_claim("TECH_SELF_HEAL")
    assert c is not None
    assert c.lane == ClaimLane.BOUNDED
    assert may_leave_ecosystem("TECH_SELF_HEAL") is True

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
