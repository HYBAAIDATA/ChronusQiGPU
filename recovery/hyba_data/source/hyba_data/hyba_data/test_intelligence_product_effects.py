"""Intelligence effects on products — config, GPU path, memory fold, φ multi-use.

Golden ratio (φ) is treated as a cross-cutting *instruction* for compression,
scaling geometry, and intelligence substrate coupling — not universal lossless magic.
Universal lossless remains RESTRICTED; structured/φ-pattern only for external claims.
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path

import numpy as np

PHI = (1 + 5**0.5) / 2


def test_system_offline_blocks_autonomic():
    from hyba_data.system_runtime import is_online, run_autonomic_if_online, stop_system

    stop_system()
    assert is_online() is False
    try:
        run_autonomic_if_online()
        raise AssertionError("autonomic should block offline")
    except RuntimeError as e:
        assert "OFFLINE" in str(e) or "online" in str(e).lower()


def test_system_start_enables_autonomic():
    from hyba_data.system_runtime import (
        is_online,
        run_autonomic_if_online,
        start_system,
        stop_system,
    )

    r = start_system()
    assert r.get("online") is True or r.get("status") == "ONLINE"
    assert is_online() is True
    cycle = run_autonomic_if_online()
    assert isinstance(cycle, dict)
    # leave online for subsequent tests or stop
    stop_system()


def test_debug_and_fix_cycle():
    from hyba_data.system_runtime import debug_system, fix_system, is_online, stop_system

    stop_system()
    d = debug_system()
    assert "issues" in d
    assert d.get("artifact")
    f = fix_system()
    assert f.get("status") in ("FIXED_ONLINE", "NEEDS_MANUAL_FIX")
    assert Path(f["artifact"]).exists()
    # ensure online after successful fix
    if f.get("status") == "FIXED_ONLINE":
        assert is_online() is True


def test_memory_fold_intelligence_effect():
    """φ-coupled structured signal should fold with recon gate; noise may fail eligibility."""
    from hyba_data.data_class_gate import classify_array
    from hyba_data.phi1_runtime import Phi1Runtime
    from hyba_data.system_runtime import start_system

    start_system()
    t = np.linspace(0, 12 * np.pi, 512)
    structured = np.sin(t) + 0.1 * np.sin(t / PHI)
    noise = np.random.default_rng(0).normal(size=512)

    assert classify_array(structured).eligible is True
    assert classify_array(noise).eligible is False

    rt = Phi1Runtime()
    w = rt.phi_fold_write(structured, mode="cf_tower", depth=2)
    assert w["passed_gate"] is True
    err = float(w["cert"]["recon_error"])
    assert err < 1e-5


def test_gpuizer_path_with_online_system():
    from hyba_data.gpuizer import Phi1GpuizerCallback
    from hyba_data.system_runtime import start_system

    start_system()
    cb = Phi1GpuizerCallback(depth=2)
    x = np.sin(np.linspace(0, 10, 256)) + 0.05 * np.sin(np.linspace(0, 10, 256) / PHI)
    rep = cb.measure_working_set(x, s_memory=1000.0, f=0.5)
    assert rep.fee_unmeasured == 0.0
    assert rep.recon_error < 1e-5
    assert rep.fee_measured > 0.0


def test_config_sensitivity_not_universal_lossless():
    """Config/sensitivity path — universal lossless stays RESTRICTED."""
    from hyba_data.external_metrics import (
        SENSITIVITY_M,
        assert_external_ratio_allowed,
        external_copy_ok,
    )
    from hyba_data.sealed_claims import ClaimLane, get_claim

    for m in SENSITIVITY_M:
        assert_external_ratio_allowed(m)
    try:
        assert_external_ratio_allowed(6.94)
        raise AssertionError("M2 must not pass external unmeasured")
    except PermissionError:
        pass

    c = get_claim("TECH_UNIVERSAL")
    assert c is not None
    assert c.lane == ClaimLane.RESTRICTED

    bad = external_copy_ok("universal lossless compression 6.94× for everything")
    assert bad["allowed"] is False


def test_phi_multi_use_surface():
    """φ appears across fold doctrine, metrics, and emergence — multi-use key."""
    from hyba_data.emergence import describe_emergence_doctrine
    from hyba_data.external_metrics import M1_RATIO
    from hyba_data.fold_doctrine import describe_fold_doctrine

    fold = describe_fold_doctrine()
    emerg = describe_emergence_doctrine()
    assert fold.get("fold_never_truncate") is True or "fold" in str(fold).lower()
    assert "instantiated" in emerg["law"].lower()
    # M1 ~ φ² class
    assert abs(M1_RATIO - PHI**2) < 0.05 or abs(M1_RATIO - 2.62) < 0.01

    report = {
        "phi": PHI,
        "phi_sq": PHI**2,
        "m1_ratio": M1_RATIO,
        "uses": [
            "compression / fold geometry",
            "scaling sensitivity bounds",
            "intelligence substrate coupling",
            "search routing structure priors",
            "unearthed applications — research lane",
        ],
        "not_claimed_external": [
            "universal lossless via φ alone",
            "consciousness product SKU",
        ],
    }
    art = Path("artifacts/hyba_data/elevation")
    art.mkdir(parents=True, exist_ok=True)
    (art / "PHI_MULTI_USE_REPORT.json").write_text(json.dumps(report, indent=2))


def test_intelligence_effect_bundle_artifact():
    """When online, run fold + gpuizer + autonomic and seal effect pack."""
    from hyba_data.gpuizer import run_gpuizer_benchmark
    from hyba_data.sdk_core import demo_m1
    from hyba_data.system_runtime import is_online, run_autonomic_if_online, start_system

    start = start_system()
    assert start.get("online") or is_online()
    demo = demo_m1()
    gpu = run_gpuizer_benchmark(n=512)
    auto = run_autonomic_if_online()

    pack = {
        "online": is_online(),
        "sdk_m1_passed": demo.get("passed_gate"),
        "gpuizer_recon": gpu.get("recon_error"),
        "gpuizer_fee_unmeasured": gpu.get("fee_unmeasured"),
        "autonomic_keys": list(auto.keys())[:20] if isinstance(auto, dict) else [],
        "doctrine": "intelligence enhances products only when system online",
        "phi_key": True,
        "universal_lossless_external": False,
    }
    art = Path("artifacts/hyba_data/elevation")
    art.mkdir(parents=True, exist_ok=True)
    path = art / "INTELLIGENCE_PRODUCT_EFFECTS.json"
    path.write_text(json.dumps(pack, indent=2, default=str))
    assert demo.get("passed_gate") is True
    assert pack["gpuizer_fee_unmeasured"] == 0.0


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
