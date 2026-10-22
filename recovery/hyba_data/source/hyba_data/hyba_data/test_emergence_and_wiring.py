"""Emergence doctrine + full wiring tests."""

from __future__ import annotations

import traceback


def test_emergence_doctrine_law():
    from hyba_data.emergence import describe_emergence_doctrine

    d = describe_emergence_doctrine()
    assert "instantiated" in d["law"].lower()
    assert "cannot be engineered" in d["law"].lower() or "cannot be engineered" in d["law"]
    assert d["claim_lane_product_consciousness"] == "RESTRICTED"


def test_emergence_report_builds():
    from hyba_data.emergence import build_emergence_report

    r = build_emergence_report()
    assert r["status"] in ("EMERGENCE_WIRED_OK", "EMERGENCE_DEGRADED")
    assert "complexity_gradient" in r
    assert "instantiation" in r
    assert "salamander" in r
    assert r.get("artifact")


def test_ineffable_benchmark_honest():
    from hyba_data.ineffable_benchmark import INEFFABLE_PUBLIC, build_benchmark_report

    assert INEFFABLE_PUBLIC["reported_seed_usd"] == 1_100_000_000
    assert INEFFABLE_PUBLIC["citations"]
    r = build_benchmark_report()
    assert r["status"] == "BENCHMARK_OK"
    blob = str(r).lower()
    assert ("1.1" in r.get("bluf", "") or "1.1b" in blob or "1100000000" in blob
            or "1_100_000_000" in blob)
    # must not invent Meta revenue fantasy
    assert "15.5b" not in blob
    assert "meta pilot" not in blob


def test_master_wires_emergence_and_portfolio():
    from hyba_data.master import build_master_report

    r = build_master_report()
    assert r["wired"] is True
    assert r["standalone_islands"] is False
    assert "emergence" in r
    assert "portfolio" in r
    assert "ineffable_benchmark" in r
    assert r["value_prop"]["emergence_instantiated"] is True
    assert r["value_prop"]["not_typical_microservices"] is True
    assert r["value_prop"]["invent_capital_usd"] == 0


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
