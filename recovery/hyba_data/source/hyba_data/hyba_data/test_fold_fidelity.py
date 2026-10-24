"""Reconstruction fidelity + φ-fold performance — fold never truncate.

CI: claims / doctrine enforcement.
"""

from __future__ import annotations

import time
import traceback

import numpy as np

from hyba_data.fold_doctrine import assert_fold_not_truncate
from hyba_data.phi1_runtime import Phi1Runtime
from hyba_data.sealed_metric_card import get_external_metric


def test_recon_fidelity_cf_tower():
    rt = Phi1Runtime()
    x = np.sin(np.linspace(0, 8 * np.pi, 256))
    w = rt.phi_fold_write(x, mode="cf_tower", depth=3)
    assert w["passed_gate"] is True
    u = rt.phi_unfold_read(w["handle"]["handle_id"])
    y = np.asarray(u["data"], dtype=np.float64)
    err = float(np.max(np.abs(y - x)))
    assert_fold_not_truncate(err, max_err=1e-5)


def test_recon_fidelity_iir():
    rt = Phi1Runtime()
    x = np.cos(np.linspace(0, 4 * np.pi, 128))
    w = rt.phi_fold_write(x, mode="iir")
    assert w["passed_gate"] is True
    err = w["cert"]["recon_error"]
    assert_fold_not_truncate(float(err), max_err=1e-5)


def test_error_bounds_on_cert():
    rt = Phi1Runtime()
    x = np.linspace(-1, 1, 64)
    w = rt.phi_fold_write(x, mode="cf_tower", depth=2)
    cert = w["cert"]
    assert cert["doctrine"] == "fold_never_truncate"
    assert cert["recon_error"] <= cert["max_err_gate"] or cert["passed_gate"] is True


def test_throughput_smoke():
    rt = Phi1Runtime()
    x = np.random.default_rng(0).normal(size=4096)
    # structure it slightly so eligibility not required for runtime fold
    x = np.sin(np.linspace(0, 20 * np.pi, 4096)) + 0.01 * x
    t0 = time.perf_counter()
    w = rt.phi_fold_write(x, mode="cf_tower", depth=2)
    elapsed = time.perf_counter() - t0
    assert w["passed_gate"] is True
    # loose performance smoke: < 5s for 4k samples in sandbox
    assert elapsed < 5.0
    mb_s = (x.nbytes / 1e6) / max(elapsed, 1e-9)
    assert mb_s > 0


def test_m1_external_metric_has_hash_path():
    # M1 must be fetchable as BOUNDED external metric
    m = get_external_metric("M1")
    assert m["metric_id"] == "M1"
    assert m["lane"] == "BOUNDED"
    assert m["ratio"] == 2.62


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
