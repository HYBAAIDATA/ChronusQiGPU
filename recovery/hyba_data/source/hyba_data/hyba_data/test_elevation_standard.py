"""Tests: code elevated to meet HYBA Data documentation standard.

Run:
  PYTHONPATH=python_backend python3 -m hyba_data.test_elevation_standard
or with pytest if available.
"""

from __future__ import annotations

import traceback

import numpy as np

from hyba_data.data_class_gate import assert_eligible, classify_array
from hyba_data.elevation import build_elevation_report
from hyba_data.savings_metering import compute_fee, compute_savings
from hyba_data.sealed_claims import (
    ClaimLane,
    assert_claim_allowed,
    gate_external_copy,
    may_leave_ecosystem,
)
from hyba_data.sealed_metric_card import get_external_metric, get_metric


def test_external_claims_may_leave():
    assert may_leave_ecosystem("CAT_CIAAS") is True
    assert may_leave_ecosystem("TECH_M1_2_62") is True
    assert may_leave_ecosystem("TECH_M2_PHI4") is False
    assert may_leave_ecosystem("TECH_UNIVERSAL") is False


def test_restricted_claim_raises():
    try:
        assert_claim_allowed("TECH_UNIVERSAL")
        raise AssertionError("expected PermissionError")
    except PermissionError:
        pass


def test_internal_claim_blocked_externally():
    try:
        assert_claim_allowed("TECH_M3_7_155")
        raise AssertionError("expected PermissionError")
    except PermissionError:
        pass
    c = assert_claim_allowed("TECH_M3_7_155", allow_internal=True)
    assert c.lane == ClaimLane.INTERNAL


def test_metric_card_external_only_m1():
    m1 = get_external_metric("M1")
    assert m1["ratio"] == 2.62
    try:
        get_external_metric("M2")
        raise AssertionError("expected PermissionError for M2")
    except PermissionError:
        pass
    assert get_metric("M3").lane == ClaimLane.INTERNAL


def test_data_class_gate_structured_vs_noise():
    t = np.linspace(0, 6 * np.pi, 200)
    structured = np.sin(t)
    noise = np.random.default_rng(1).normal(size=200)
    assert classify_array(structured).eligible is True
    assert_eligible(structured, for_external_claim=True)
    assert classify_array(noise).eligible is False
    try:
        assert_eligible(noise, for_external_claim=True)
        raise AssertionError("expected PermissionError for noise")
    except PermissionError:
        pass


def test_savings_fee_only_when_measured():
    un = compute_savings(s_memory=1000, f=0.5, m_eff=2.0, measured=False)
    assert un.hyba_fee == 0.0
    me = compute_savings(s_memory=1000, f=0.5, m_eff=2.0, measured=True)
    assert me.gross_savings == 250.0
    assert me.hyba_fee == 62.5
    assert compute_fee(s_memory=1000, f=0.5, m_eff=2.0, measured=True) == 62.5


def test_internal_multiplier_blocked_when_unmeasured():
    try:
        compute_savings(s_memory=1e6, f=0.4, m_eff=7.155, measured=False)
        raise AssertionError("expected PermissionError")
    except PermissionError:
        pass


def test_copy_gate_blocks_restricted_language():
    bad = gate_external_copy("SaaS with 99.999 uptime and 7.155x universal compression")
    assert bad["allowed"] is False
    assert bad.get("restricted_hits") or bad.get("banned_hits")
    good = gate_external_copy(
        "Computational Intelligence as a Service. Structured working sets. "
        "Twenty-five percent of measured savings. No maintenance charge."
    )
    assert good["allowed"] is True


def test_elevation_report_self_test():
    report = build_elevation_report()
    assert report["elevation_self_test_passed"] is True
    assert report["company"] == "HYBA Data"


def main() -> int:
    tests = [name for name in globals() if name.startswith("test_")]
    failed = 0
    for name in sorted(tests):
        fn = globals()[name]
        try:
            fn()
            print("PASS", name)
        except Exception as e:
            failed += 1
            print("FAIL", name, type(e).__name__, e)
            traceback.print_exc()
    print(f"summary failed={failed} total={len(tests)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
