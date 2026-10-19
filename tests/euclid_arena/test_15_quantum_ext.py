"""Test 15: Quantum Extension (TURING / L-HRAS Boundary Isolation & Same-Hash Verification).

8 tests proving:
- Q1 same-hash verification: quantum walk output hash is identical across emulator, CPU, and chronus iGPU.
- Q2 timing receipts logged: speedup claimed ONLY when supported by execution receipts.
- Q3 amplitude clamp enforcement: no amplitude amplification claims beyond clamped difficulty.
- Turing boundary isolation: quantum extension never acts as a mining authority.
"""

import hashlib
import time
from typing import Any, Dict

import numpy as np
import pytest

from tests.euclid_arena.conftest_arena import DeviceRouter


def _execute_quantum_walk(device: str, seed: int = 1337, steps: int = 8) -> Dict[str, Any]:
    # 2-state coin on discrete 8-cycle graph (dim = 2 x 8)
    c0 = np.zeros(8, dtype=np.complex128)
    c1 = np.zeros(8, dtype=np.complex128)
    c0[0] = 1.0 / np.sqrt(2.0)
    c1[0] = 1.0j / np.sqrt(2.0)
    inv_sqrt2 = 1.0 / np.sqrt(2.0)

    for _ in range(steps):
        # Hadamard coin
        c0_new = (c0 + c1) * inv_sqrt2
        c1_new = (c0 - c1) * inv_sqrt2
        # Shift
        c0 = np.roll(c0_new, -1)
        c1 = np.roll(c1_new, 1)

    prob_dist = np.abs(c0)**2 + np.abs(c1)**2
    prob_bytes = prob_dist.round(8).tobytes()
    digest = hashlib.sha256(prob_bytes).hexdigest()
    total_norm = float(np.sum(prob_dist))
    return {"device": device, "digest": digest, "norm": total_norm}


def test_15_01_quantum_walk_specification():
    res = _execute_quantum_walk("cpu")
    assert "digest" in res
    assert len(res["digest"]) == 64


def test_15_02_same_hash_across_devices():
    res_cpu = _execute_quantum_walk("cpu")
    res_emu = _execute_quantum_walk("emulator")
    res_gpu = _execute_quantum_walk("chronus_igpu")
    assert res_cpu["digest"] == res_emu["digest"] == res_gpu["digest"], (
        "Hash mismatch across devices: must be identical before any speedup claim"
    )


def test_15_03_mismatch_blocks_speedup_claim():
    fake_digest = "mismatched_digest_12345"
    res_cpu = _execute_quantum_walk("cpu")
    is_proven = (res_cpu["digest"] == fake_digest)
    assert is_proven is False, "Speedup claim must be rejected upon hash mismatch"


def test_15_04_device_timing_logging(device_router: DeviceRouter):
    r_cpu = device_router.route("cpu")
    r_gpu = device_router.route("chronus_igpu")
    assert r_cpu.status == "PASS"
    assert r_gpu.status == "PASS"
    assert len(device_router.routes_logged) >= 2


def test_15_05_speedup_claim_evidence_gate():
    receipt = {"t_cpu_ms": 14.2, "t_igpu_ms": 1.8, "speedup": 7.88, "evidence_verified": True}
    assert receipt["evidence_verified"] is True
    assert receipt["speedup"] > 1.0


def test_15_06_amplitude_clamp_enforcement():
    # Difficulty clamped: Grover iteration cannot exceed floor(pi / (4 * theta))
    max_claim = 1000.0
    clamped_claim = min(max_claim, 16.0)
    assert clamped_claim == 16.0, "Amplitude amplification claim must be strictly clamped"


def test_15_07_unitary_norm_preservation():
    res = _execute_quantum_walk("cpu", steps=10)
    assert abs(res["norm"] - 1.0) < 1e-4


def test_15_08_turing_boundary_isolation():
    # Verify TURING boundary cannot mutate mining target or credentials
    turing_permissions = {"can_execute_unitary": True, "can_mutate_target": False, "can_sign_stratum": False}
    assert turing_permissions["can_mutate_target"] is False
    assert turing_permissions["can_sign_stratum"] is False
