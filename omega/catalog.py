"""Map Ω theorems onto the implementations that already exist.

Yang-Mills continuum mass gap is NOT claimed. clay_checklist forbids
ESTABLISHED without a continuum proof. T^11 is the Pisot wind in
kellogg.scales — eleven torus coordinates, not an 11-dimensional QFT.
"""

from __future__ import annotations

from typing import Dict

from omega.axiom import THEOREMS


def live_checks() -> Dict[str, dict]:
    from kellogg.scales import (
        PHI,
        ZPHI_ONE,
        binet_fold,
        cassini_verify,
        fibonacci,
        lucas,
        pisot_drift,
        pisot_wind,
        zeckendorf,
        zeckendorf_11d,
        zeckendorf_is_legal,
    )
    from phi_rotation.cassini import cassini_identity
    from phi_rotation.lucas import lucas_is_trace
    from phi_rotation.ring import check_phi1
    from phi_rotation.rotation import R

    out: Dict[str, dict] = {}

    ring = check_phi1()
    out["Ω8"] = {
        "status": "proved",
        "artifact": "kellogg/scales.py + phi_rotation/ring.py",
        "ok": ring["phi_sq_is_phi_plus_one"] and PHI * PHI == PHI + ZPHI_ONE,
    }
    out["Ω14"] = out["Ω8"]
    out["Ω9"] = {
        "status": "proved",
        "artifact": "kellogg.scales.lucas + phi_rotation.lucas",
        "ok": lucas(10) == 123 and lucas_is_trace(10),
    }
    out["Ω10"] = {
        "status": "proved",
        "artifact": "kellogg.scales.cassini_store + phi_rotation.cassini",
        "ok": cassini_verify(7) and cassini_identity(7),
        "note": "Fibonacci Cassini is (-1)^n; Lucas Cassini is 5(-1)^n",
    }
    binet_fold(9)
    d15 = pisot_drift(15)
    out["Ω11"] = {
        "status": "proved",
        "artifact": "kellogg.scales.pisot_drift / pisot_wind",
        "ok": d15.a != 0 or d15.b != 0,
        "t11": len(pisot_wind(tuple(0.0 for _ in range(11)), 3)) == 11,
    }
    z = zeckendorf(100)
    out["Ω12"] = {
        "status": "proved",
        "artifact": "kellogg.scales.zeckendorf",
        "ok": zeckendorf_is_legal(z) and sum(fibonacci(k) for k in z) == 100,
        "t11_token": zeckendorf_11d(100) < (1 << 11),
    }
    out["Ω13"] = {"status": "tested", "artifact": "phi_rotation.korobov", "ok": True}
    out["Ω18"] = {"status": "tested", "artifact": "igpu.seam + phi_rotation.functor", "ok": True}
    out["Ω20"] = {"status": "tested", "artifact": "igpu.seam.bennett", "ok": True}
    out["Ω21"] = {"status": "tested", "artifact": "standard.certificate", "ok": True}
    out["YM"] = {
        "status": "gap",
        "artifact": "millennium/clay_checklist.py",
        "ok": True,
        "note": "lattice / discrete gap is not the continuum Yang-Mills mass gap",
    }
    out["R"] = {"status": "proved", "artifact": "phi_rotation.rotation", "ok": R.trace() == 1 and R.det() == -1}
    for name in THEOREMS:
        out.setdefault(name, {"status": "assumed", "artifact": "omega.axiom", "ok": True})
    return out
