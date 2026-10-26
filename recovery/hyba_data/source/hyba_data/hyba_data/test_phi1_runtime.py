"""Tests: PHI-1 runtime elevates code to meet OS/Architecture documentation.

Rule: We elevate code to meet documentation, always.
"""

from __future__ import annotations

import traceback

import numpy as np

from hyba_data.phi1_runtime import Phi1Runtime, build_runtime_report


def test_describe_elevation_rule():
    rt = Phi1Runtime()
    d = rt.describe()
    assert "elevate code to meet documentation" in d["elevation_rule"].lower()
    assert d["quantum_serves_data"] is True
    assert d["mining_product_surface"] is False
    assert "phi_FOLD" in d["isa_implemented"]


def test_fold_unfold_verify_roundtrip():
    rt = Phi1Runtime()
    x = np.cos(np.linspace(0, 4 * np.pi, 64))
    w = rt.phi_fold_write(x, mode="cf_tower", depth=2)
    assert w["passed_gate"] is True
    hid = w["handle"]["handle_id"]
    u = rt.phi_unfold_read(hid)
    assert u["n"] == 64
    v = rt.phi_verify(hid)
    assert v["ok"] is True
    s = rt.phi_stat(hid)
    assert s["mode"] == "cf_tower"


def test_fold_never_truncate_gate_on_cert():
    rt = Phi1Runtime()
    x = np.sin(np.linspace(0, 2 * np.pi, 32))
    w = rt.phi_fold_write(x, mode="iir")
    cert = w["cert"]
    assert cert["doctrine"] == "fold_never_truncate"
    assert cert["quantum_serves_data"] is True
    assert cert["passed_gate"] is True


def test_runtime_report_self_test():
    r = build_runtime_report()
    assert r["self_test_passed"] is True
    assert "always" in r["elevation_rule"].lower()


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
