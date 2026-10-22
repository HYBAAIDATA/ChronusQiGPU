"""Tests for portfolio elevation (SDK / Storage / GPUizer / metrics / CIaaS)."""

from __future__ import annotations

import traceback

import numpy as np


def test_external_metrics_lock():
    from hyba_data.external_metrics import (
        M1_RATIO,
        SENSITIVITY_M,
        assert_external_ratio_allowed,
        external_copy_ok,
    )

    assert M1_RATIO == 2.62
    assert SENSITIVITY_M == (1.5, 2.0, 2.6)
    assert_external_ratio_allowed(1.5)
    try:
        assert_external_ratio_allowed(6.85)
        raise AssertionError
    except PermissionError:
        pass
    assert external_copy_ok("maintenance fee and 6.94")["allowed"] is False


def test_sdk_core_m1_demo():
    from hyba_data.sdk_core import demo_m1, fold, unfold

    d = demo_m1()
    assert d["passed_gate"] is True
    x = np.linspace(0, 1, 64)
    w = fold(x, depth=1)
    u = unfold(w["handle"]["handle_id"])
    assert w["passed_gate"]


def test_storage_engine_roundtrip():
    from hyba_data.storage_engine import Phi1StorageEngine

    eng = Phi1StorageEngine()
    x = np.cos(np.linspace(0, 6, 128))
    eng.put_object("t/k1", x)
    g = eng.get_object("t/k1")
    err = float(np.max(np.abs(g["data"][: x.size] - x)))
    assert err < 1e-5


def test_gpuizer_callback_and_fee():
    from hyba_data.gpuizer import Phi1GpuizerCallback

    cb = Phi1GpuizerCallback(depth=2)
    x = np.sin(np.linspace(0, 10, 512))
    rep = cb.measure_working_set(x, s_memory=1000.0, f=0.5)
    assert rep.fee_unmeasured == 0.0
    assert rep.fee_measured > 0.0
    assert rep.recon_error < 1e-5


def test_pricing_dashboard_viability():
    from hyba_data.pricing_dashboard import compute_dashboard

    d = compute_dashboard(s_memory=1e6, f=0.4, measured=True)
    assert d["fee_rate"] == 0.25
    assert "SaaS seats" in d["not"]
    rows = {r["m"]: r for r in d["sensitivity_rows"]}
    assert rows[1.5]["external_viability_m_ge_2"] is False
    assert rows[2.0]["external_viability_m_ge_2"] is True


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
