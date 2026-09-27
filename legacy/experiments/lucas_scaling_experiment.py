"""Real scaling experiment: measure runtime vs problem size for each algorithm.

Deterministic. No randomness. Reports:
  - Wall-clock time at each Lucas scale point
  - Accuracy / correctness metric
  - Unitarity error (for unitary algorithms)
  - Scaling exponent (log-log regression of T vs L_k)
  - Whether Conjecture S is supported or falsified for this instance

This is NOT a claim of quantum advantage. It is an honest measurement of
how the algorithms behave under Lucas-indexed budget scaling on classical
hardware.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np

from lucas import core as lucas_core, pool as lucas_pool
from Intelligence.quantum_algorithms import (
    ExactQFT,
    GroverSearch,
    QuantumPhaseEstimation,
    QuantumWalk,
    VQE,
    QuantumGates,
    QuantumState,
    MathEigensolver,
)

# ---------------------------------------------------------------------------
# Timing utility — median of N runs
# ---------------------------------------------------------------------------


def median_runtime(fn, runs: int = 5) -> float:
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    times.sort()
    return times[len(times) // 2]


def scaling_exponent(scales: List[float], times: List[float]) -> float:
    """Log-log linear regression slope: T ~ L_k^alpha."""
    if len(scales) < 2:
        return 0.0
    log_s = [math.log(s) for s in scales if s > 0]
    log_t = [math.log(t) for t in times if t > 0]
    if len(log_s) < 2:
        return 0.0
    n = len(log_s)
    sum_x = sum(log_s)
    sum_y = sum(log_t)
    sum_xy = sum(x * y for x, y in zip(log_s, log_t))
    sum_x2 = sum(x * x for x in log_s)
    denom = n * sum_x2 - sum_x * sum_x
    if abs(denom) < 1e-30:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denom


# ---------------------------------------------------------------------------
# QFT scaling: unitarity error vs n_qubits at each Lucas scale
# ---------------------------------------------------------------------------


def experiment_qft() -> Dict[str, Any]:
    """QFT: measure unitarity error and runtime at increasing qubit counts."""
    lucas_indices = [10, 12, 15]
    results = []
    for k in lucas_indices:
        L_k = lucas_core.lucas(k)
        # Map L_k to qubit count: n_qubits = min(8, max(2, log2(L_k)))
        n_qubits = min(8, max(2, int(math.log2(max(L_k, 4)))))
        N = 1 << n_qubits

        def run():
            Q = ExactQFT.matrix(n_qubits)
            Qi = ExactQFT.inverse(n_qubits)
            QQi = Q.matmul(Qi)
            return QQi

        t = median_runtime(run, runs=3)
        Q = ExactQFT.matrix(n_qubits)
        Qi = ExactQFT.inverse(n_qubits)
        QQi = Q.matmul(Qi)
        # Unitarity: QQi should be identity
        unitary_err = 0.0
        for r in range(N):
            for c in range(N):
                expected = 1.0 if r == c else 0.0
                unitary_err = max(
                    unitary_err, abs(QQi.data[r][c].re - expected), abs(QQi.data[r][c].im)
                )

        # Pool call: trace_kernel on the QFT matrix
        Q_np = np.array([[Q.data[r][c].re for c in range(N)] for r in range(N)])
        trace_bound = lucas_pool.get("trace_kernel")(Q_np, k)

        results.append(
            {
                "lucas_index": k,
                "L_k": L_k,
                "n_qubits": n_qubits,
                "N": N,
                "unitarity_error": unitary_err,
                "runtime_seconds": t,
                "trace_bound": trace_bound,
            }
        )

    scales = [r["L_k"] for r in results]
    times = [r["runtime_seconds"] for r in results]
    alpha = scaling_exponent(scales, times)

    return {
        "algorithm": "QFT",
        "substrate": "trace",
        "pool_kernel": "trace_kernel",
        "measurements": results,
        "scaling_exponent": alpha,
        "conjecture_S_supported": all(r["unitarity_error"] < 1e-10 for r in results),
        "theorem_proven": False,
    }


# ---------------------------------------------------------------------------
# Grover scaling: peak success probability vs n_qubits
# ---------------------------------------------------------------------------


def experiment_grover() -> Dict[str, Any]:
    """Grover: measure peak success probability and runtime at increasing qubit counts."""
    lucas_indices = [10, 12, 15]
    results = []
    for k in lucas_indices:
        L_k = lucas_core.lucas(k)
        n_qubits = min(6, max(2, int(math.log2(max(L_k, 4)))))
        N = 1 << n_qubits
        marked = [N // 3]

        def run():
            g = GroverSearch(n_qubits)
            return g.run(marked)

        t = median_runtime(run, runs=3)
        g = GroverSearch(n_qubits)
        result = g.run(marked)
        peak = result["peak_success_probability"]

        # Pool call: path_kernel on the Grover diffusion operator's adjacency
        # The diffusion operator S0 has entries 2/N - delta, which is a complete
        # graph adjacency (up to scaling). Use the adjacency of a cycle graph
        # as the path substrate.
        cycle_adj = np.zeros((N, N), dtype=np.int64)
        for i in range(N):
            cycle_adj[i][(i + 1) % N] = 1
            cycle_adj[(i + 1) % N][i] = 1
        path_bound = lucas_pool.get("path_kernel")(cycle_adj, k)

        results.append(
            {
                "lucas_index": k,
                "L_k": L_k,
                "n_qubits": n_qubits,
                "N": N,
                "marked_count": len(marked),
                "peak_success_probability": peak,
                "optimal_iterations": result["optimal_k"],
                "runtime_seconds": t,
                "path_bound": path_bound,
            }
        )

    scales = [r["L_k"] for r in results]
    times = [r["runtime_seconds"] for r in results]
    alpha = scaling_exponent(scales, times)

    return {
        "algorithm": "Grover",
        "substrate": "path",
        "pool_kernel": "path_kernel",
        "measurements": results,
        "scaling_exponent": alpha,
        "conjecture_S_supported": all(r["peak_success_probability"] > 0.5 for r in results),
        "theorem_proven": False,
    }


# ---------------------------------------------------------------------------
# QPE scaling: phase error vs precision qubits
# ---------------------------------------------------------------------------


def experiment_qpe() -> Dict[str, Any]:
    """QPE: measure phase estimation error and runtime at increasing precision."""
    lucas_indices = [10, 12, 15]
    results = []
    true_phase = 0.125  # 1/8 — exactly representable
    unitary = QuantumGates.Z
    eigenstate = QuantumState.from_basis(2, 0)

    for k in lucas_indices:
        L_k = lucas_core.lucas(k)
        precision_qubits = min(8, max(3, int(math.log2(max(L_k, 8)))))

        def run():
            qpe = QuantumPhaseEstimation()
            return qpe.run(unitary, eigenstate, precision_qubits, true_phase)

        t = median_runtime(run, runs=3)
        qpe = QuantumPhaseEstimation()
        result = qpe.run(unitary, eigenstate, precision_qubits, true_phase)

        # Pool call: gap_kernel on the unitary's Hermitian part
        H = np.array([[1.0, 0.0], [0.0, -1.0]])  # Z is Hermitian
        gap_bound = lucas_pool.get("gap_kernel")(H, k)

        results.append(
            {
                "lucas_index": k,
                "L_k": L_k,
                "precision_qubits": precision_qubits,
                "phase_error": result["phase_error"],
                "is_exact_dyadic": result["is_exact_dyadic"],
                "runtime_seconds": t,
                "gap_bound": gap_bound,
            }
        )

    scales = [r["L_k"] for r in results]
    times = [r["runtime_seconds"] for r in results]
    alpha = scaling_exponent(scales, times)

    return {
        "algorithm": "QPE",
        "substrate": "gap",
        "pool_kernel": "gap_kernel",
        "measurements": results,
        "scaling_exponent": alpha,
        "conjecture_S_supported": all(r["phase_error"] < 1e-10 for r in results),
        "theorem_proven": False,
    }


# ---------------------------------------------------------------------------
# Quantum Walk scaling: ballistic vs diffusive variance ratio
# ---------------------------------------------------------------------------


def experiment_quantum_walk() -> Dict[str, Any]:
    """Quantum walk: measure quantum/classical variance ratio (ballistic > diffusive)."""
    lucas_indices = [10, 12, 15]
    results = []
    for k in lucas_indices:
        L_k = lucas_core.lucas(k)
        num_positions = min(64, max(8, int(math.log2(max(L_k, 8))) * 4))
        steps = min(20, max(3, int(math.log2(max(L_k, 8)))))

        def run():
            return QuantumWalk.run_cycle_walk(num_positions, steps)

        t = median_runtime(run, runs=3)
        result = QuantumWalk.run_cycle_walk(num_positions, steps)
        ratio = result["quantum_variance"] / max(result["classical_variance"], 1e-30)

        # Pool call: path_kernel on the cycle graph
        cycle_adj = np.zeros((num_positions, num_positions), dtype=np.int64)
        for i in range(num_positions):
            cycle_adj[i][(i + 1) % num_positions] = 1
            cycle_adj[(i + 1) % num_positions][i] = 1
        path_bound = lucas_pool.get("path_kernel")(cycle_adj, k)

        results.append(
            {
                "lucas_index": k,
                "L_k": L_k,
                "num_positions": num_positions,
                "steps": steps,
                "quantum_variance": result["quantum_variance"],
                "classical_variance": result["classical_variance"],
                "ballistic_diffusive_ratio": ratio,
                "runtime_seconds": t,
                "path_bound": path_bound,
            }
        )

    scales = [r["L_k"] for r in results]
    times = [r["runtime_seconds"] for r in results]
    alpha = scaling_exponent(scales, times)

    return {
        "algorithm": "QuantumWalk",
        "substrate": "path",
        "pool_kernel": "path_kernel",
        "measurements": results,
        "scaling_exponent": alpha,
        "conjecture_S_supported": all(r["ballistic_diffusive_ratio"] > 1.0 for r in results),
        "theorem_proven": False,
    }


# ---------------------------------------------------------------------------
# VQE scaling: final energy vs exact ground energy
# ---------------------------------------------------------------------------


def experiment_vqe() -> Dict[str, Any]:
    """VQE: measure energy convergence to exact ground state."""
    lucas_indices = [10, 12, 15]
    results = []
    H = VQE.ising_hamiltonian()
    eigenvalues = MathEigensolver.hermitian_eigenvalues(H)
    exact_e0 = min(eigenvalues)

    for k in lucas_indices:
        L_k = lucas_core.lucas(k)
        iterations = min(50, max(10, int(math.log2(max(L_k, 8))) * 5))

        def run():
            vqe = VQE()
            return vqe.optimize(H, [0.1, 0.2, 0.3, 0.4], iterations=iterations)

        t = median_runtime(run, runs=3)
        vqe = VQE()
        result = vqe.optimize(H, [0.1, 0.2, 0.3, 0.4], iterations=iterations)
        energy_error = abs(result["final_energy"] - exact_e0)

        # Pool call: gap_kernel on the Hamiltonian
        H_np = np.array([[H.data[r][c].re for c in range(H.rows)] for r in range(H.rows)])
        gap_bound = lucas_pool.get("gap_kernel")(H_np, k)

        results.append(
            {
                "lucas_index": k,
                "L_k": L_k,
                "iterations": iterations,
                "final_energy": result["final_energy"],
                "exact_ground_energy": exact_e0,
                "energy_error": energy_error,
                "runtime_seconds": t,
                "gap_bound": gap_bound,
            }
        )

    scales = [r["L_k"] for r in results]
    times = [r["runtime_seconds"] for r in results]
    alpha = scaling_exponent(scales, times)

    return {
        "algorithm": "VQE",
        "substrate": "gap",
        "pool_kernel": "gap_kernel",
        "measurements": results,
        "scaling_exponent": alpha,
        "conjecture_S_supported": all(r["energy_error"] < 1.0 for r in results),
        "theorem_proven": False,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 78)
    print("LUCAS POWER SCALING — REAL EXPERIMENTAL PROTOCOL")
    print("Deterministic. No randomness. No Monte Carlo. No claims of quantum advantage.")
    print("=" * 78)

    experiments = [
        ("QFT", experiment_qft),
        ("Grover", experiment_grover),
        ("QPE", experiment_qpe),
        ("QuantumWalk", experiment_quantum_walk),
        ("VQE", experiment_vqe),
    ]

    all_results = {}
    for name, fn in experiments:
        print(f"\n--- {name} ---")
        result = fn()
        all_results[name] = result
        for m in result["measurements"]:
            print(
                f"  L_{m['lucas_index']} = {m['L_k']:>6d}  "
                f"runtime={m['runtime_seconds']:.6f}s  "
                f"scale_point={m.get('n_qubits', m.get('precision_qubits', m.get('num_positions', m.get('iterations', '?'))))}"
            )
        print(f"  scaling exponent alpha = {result['scaling_exponent']:.4f}")
        print(f"  Conjecture S supported: {result['conjecture_S_supported']}")
        print(f"  theorem_proven: {result['theorem_proven']}")

    # Honest summary
    print("\n" + "=" * 78)
    print("HONEST SUMMARY")
    print("=" * 78)
    supported = sum(1 for r in all_results.values() if r["conjecture_S_supported"])
    total = len(all_results)
    print(f"Conjecture S supported on {supported}/{total} algorithm instances.")
    print("This is EMPIRICAL EVIDENCE, not a proof.")
    print("The scaling exponents measure how runtime grows with L_k on classical hardware.")
    print("No quantum advantage is claimed. No post-quantum security is claimed.")
    print("See papers/discovery/LUCAS_POWER_SCALING_RIGOROUS_FOUNDATIONS.md for full analysis.")

    out_path = Path(__file__).resolve().parent / "lucas_scaling_experiment_results.json"
    out_path.write_text(json.dumps(all_results, indent=2, default=str), encoding="utf-8")
    print(f"\nResults written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
