"""Tests for sealed claim closures — implement, test, elevate, unblock."""

from __future__ import annotations

import traceback

from hyba_data.claim_closures import (
    availability_measurement_pack,
    gain_share_closure,
    issue_multi_cloud_certificates,
    run_all_closures,
    seal_m1_with_harness,
)
from hyba_data.quantum_honest import help_hyba_data, make_grover_engine


def test_m1_seal_has_hash_and_band():
    m1 = seal_m1_with_harness(seed=1)
    assert m1["test_hash"]
    assert len(m1["test_hash"]) == 64
    assert m1["within_illustrative_band"] is True
    assert m1["external_ok"] is True


def test_multi_cloud_certs():
    m = issue_multi_cloud_certificates()
    assert m["unblocked"] is True
    assert len(m["certificates"]) == 3
    assert all(c["status"] == "IMPLEMENTED_STUB" for c in m["certificates"])


def test_availability_pack_stays_internal():
    a = availability_measurement_pack(window_hours=1.0)
    assert a["external_ok"] is False
    assert a["lane"] == "INTERNAL"


def test_gain_share_invariant():
    g = gain_share_closure()
    assert g["invariant"] is True
    assert g["unmeasured_fee"] == 0.0
    assert g["measured_fee"] > 0.0


def test_run_all_closures():
    r = run_all_closures()
    assert r["self_test_passed"] is True
    assert r["repo_posture"].startswith("HYBA Data")
    assert "ethos" in r
    assert r["ethos"]["stance"]


def test_quantum_honest_no_mining_import():
    h = help_hyba_data()
    assert h["mining"] is False
    eng = make_grover_engine(100)
    assert eng.iterations() >= 1


def main() -> int:
    tests = [n for n in globals() if n.startswith("test_")]
    failed = 0
    for name in sorted(tests):
        try:
            globals()[name]()
            print("PASS", name)
        except Exception as e:
            failed += 1
            print("FAIL", name, type(e).__name__, e)
            traceback.print_exc()
    print(f"summary failed={failed} total={len(tests)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
