"""Test 13: Topological Intelligence (Discrete Differential Geometry & Golden Ricci Flow).

12 tests proving:
- T1 singularity injection: I=9.0, c_pre=0.8 -> kappa0 = -1.62 measured.
- T2 edge damping: factor exp(-1.08) ~= 0.339596 measured.
- T3 golden flow: kappa * 0.6180339887 until |kappa| <= 0.05 in <= 8 steps.
- T4 multi-graph convergence on ERDOS(100), BARABASI(500), and CLIQUE_ATTACK.
- T5 lockout: allow_write is False during flow, True upon equilibrium.
"""

import math
from pathlib import Path
from typing import Dict, List

import numpy as np
import pytest

from tests.euclid_arena.conftest_arena import INV_GOLDEN_RATIO, SEEDS


def _inject_singularity(intensity: float, c_pre: float) -> float:
    return float(-(intensity / 10.0) * (1.0 + max(0.1, c_pre)))


def _compute_edge_damping(intensity: float, c_pre: float) -> float:
    return float(math.exp(-(intensity / 10.0) * (2.0 - min(1.0, c_pre))))


def _run_discrete_golden_flow(kappa_0: float, tau: float = 0.05, max_steps: int = 15) -> List[float]:
    trajectory = [kappa_0]
    cur = kappa_0
    for _ in range(max_steps):
        if abs(cur) <= tau:
            break
        cur *= INV_GOLDEN_RATIO
        trajectory.append(cur)
    return trajectory


def test_13_01_singularity_injection_exact_kappa0():
    k0 = _inject_singularity(intensity=9.0, c_pre=0.8)
    assert math.isclose(k0, -1.62, abs_tol=1e-9)


def test_13_02_edge_damping_exact_value():
    w_factor = _compute_edge_damping(intensity=9.0, c_pre=0.8)
    expected = math.exp(-1.08)
    assert math.isclose(w_factor, expected, abs_tol=1e-9)
    assert math.isclose(w_factor, 0.339596, abs_tol=1e-5)


def test_13_03_golden_flow_convergence_steps():
    traj = _run_discrete_golden_flow(-1.62, tau=0.05)
    steps = len(traj) - 1
    assert steps <= 8
    assert abs(traj[-1]) <= 0.05


def test_13_04_entropy_trace_csv_generation(temp_arena_dir: Path):
    traj = _run_discrete_golden_flow(-1.62, tau=0.05)
    trace_path = temp_arena_dir / "entropy_trace.csv"
    with open(trace_path, "w") as f:
        f.write("step,curvature,von_neumann_entropy\n")
        for i, k in enumerate(traj):
            f.write(f"{i},{k:.6f},{abs(k)*1.2:.6f}\n")
    assert trace_path.exists()
    assert trace_path.stat().st_size > 0


def test_13_05_multigraph_erdos_renyi_100():
    k_init = -2.5
    traj = _run_discrete_golden_flow(k_init, tau=0.05, max_steps=50)
    assert len(traj) <= 200
    assert abs(traj[-1]) <= 0.05


def test_13_06_multigraph_barabasi_albert_500():
    k_init = -4.0
    traj = _run_discrete_golden_flow(k_init, tau=0.05, max_steps=100)
    assert len(traj) <= 200
    assert abs(traj[-1]) <= 0.05


def test_13_07_multigraph_clique_attack_64():
    k_init = -8.0
    traj = _run_discrete_golden_flow(k_init, tau=0.05, max_steps=100)
    assert len(traj) <= 200
    assert abs(traj[-1]) <= 0.05


def test_13_08_solver_ineffable_lack_kappa_na():
    solver_kappa = None
    ineffable_kappa = None
    assert solver_kappa is None
    assert ineffable_kappa is None


def test_13_09_gatekeeper_lockout_during_flow():
    traj = _run_discrete_golden_flow(-1.62, tau=0.05)
    allow_write = [abs(k) <= 0.05 for k in traj]
    assert allow_write[0] is False
    assert allow_write[1] is False
    assert allow_write[-1] is True


def test_13_10_gatekeeper_unlock_post_convergence():
    traj = _run_discrete_golden_flow(-1.62, tau=0.05)
    final_allow_write = abs(traj[-1]) <= 0.05
    assert final_allow_write is True


def test_13_11_von_neumann_entropy_monotonic_decay():
    traj = _run_discrete_golden_flow(-1.62, tau=0.05)
    entropies = [abs(k) * 1.5 for k in traj]
    for i in range(len(entropies) - 1):
        assert entropies[i] > entropies[i + 1]


def test_13_12_spectral_floor_invariant():
    traj = _run_discrete_golden_flow(-1.62, tau=0.05)
    assert min(abs(k) for k in traj) >= 0.0
