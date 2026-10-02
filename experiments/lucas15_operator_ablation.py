"""Deterministic Lucas-15 operator ablation for non-Grover algorithms.

This is a numerical experiment, not a physical-quantum or mining-speed claim.
All arms receive identical seeded workloads.  The schedule-only arm is kept
separate from arms that apply a linear operator to the state/problem data.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import time
import tracemalloc
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PSI = -1.0 / PHI
LUCAS_INDEX = 15
LUCAS_15 = 1364
PISOT_15 = abs(PSI) ** LUCAS_INDEX
M = np.array([[1.0, 1.0], [1.0, 0.0]], dtype=np.float64)
M15_EXACT = np.array([[987.0, 610.0], [610.0, 377.0]], dtype=np.float64)
ARMS = ("baseline", "lucas15_schedule", "phi_pisot", "m15", "m15_golden_eigenbasis")
ALGORITHMS = ("qaoa", "vqe", "quantum_walk", "qml_kernel", "time_evolution", "qec", "qft")


@dataclass(frozen=True)
class Measurement:
    algorithm: str
    arm: str
    repeat: int
    seed: int
    dimension: int
    wall_clock_seconds: float
    operator_applications: int
    iterations: int
    final_objective_or_error: float
    spectral_concentration: float
    numerical_stability: float
    peak_memory_bytes: int
    throughput_values_per_second: float
    backend: str = "numpy_cpu"
    lucas_index: int = LUCAS_INDEX
    lucas_value: int = LUCAS_15
    pisot_damping: float = PISOT_15


def _golden_eigenbasis_operator() -> np.ndarray:
    values, vectors = np.linalg.eigh(M)
    powered = np.diag(np.power(values, LUCAS_INDEX))
    return (vectors @ powered @ vectors.T) / (PHI**LUCAS_INDEX)


def operator_for_arm(arm: str) -> np.ndarray:
    if arm in ("baseline", "lucas15_schedule"):
        return np.eye(2, dtype=np.float64)
    if arm == "phi_pisot":
        return np.diag([1.0, PISOT_15])
    if arm == "m15":
        return M15_EXACT / (PHI**LUCAS_INDEX)
    if arm == "m15_golden_eigenbasis":
        return _golden_eigenbasis_operator()
    raise ValueError(f"unknown arm: {arm}")


def _coprime_stride(size: int) -> int:
    if size < 2:
        return 1
    candidate = LUCAS_15 % size or 1
    while math.gcd(candidate, size) != 1:
        candidate = (candidate + 1) % size or 1
    return candidate


def _schedule(vector: np.ndarray, arm: str) -> np.ndarray:
    if arm != "lucas15_schedule":
        return vector
    stride = _coprime_stride(vector.size)
    return vector[(np.arange(vector.size) * stride) % vector.size]


def apply_operator(vector: np.ndarray, arm: str) -> np.ndarray:
    vector = _schedule(np.asarray(vector, dtype=np.complex128), arm)
    if vector.size % 2:
        raise ValueError("dimension must be even")
    op = operator_for_arm(arm).astype(np.complex128)
    return (vector.reshape(-1, 2) @ op.T).reshape(-1)


def _spectral_concentration(vector: np.ndarray) -> float:
    power = np.abs(np.fft.fft(vector)) ** 2
    total = float(power.sum())
    if total == 0.0:
        return 0.0
    keep = max(1, power.size // 8)
    return float(np.partition(power, -keep)[-keep:].sum() / total)


def _normalise(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    return vector if norm == 0.0 else vector / norm


def _qaoa_like(x: np.ndarray) -> tuple[int, float, float]:
    # Fixed-grid p=1 ring-MaxCut surrogate: lower energy is better.
    edges = np.real(x * np.conj(np.roll(x, -1)))
    gammas = np.linspace(0.0, math.pi, 65)
    values = np.array([np.mean(np.cos(g * edges)) for g in gammas])
    return len(gammas), float(values.min()), float(np.std(values))


def _vqe_like(x: np.ndarray) -> tuple[int, float, float]:
    diag = np.linspace(-1.0, 1.0, x.size)
    h = np.diag(diag) + 0.03 * (np.eye(x.size, k=1) + np.eye(x.size, k=-1))
    state = _normalise(x)
    target = float(np.linalg.eigvalsh(h)[0])
    last = float(np.real(np.vdot(state, h @ state)))
    iterations = 0
    for iterations in range(1, 129):
        state = _normalise(state - 0.08 * (h @ state - last * state))
        energy = float(np.real(np.vdot(state, h @ state)))
        if abs(energy - last) < 1e-10:
            last = energy
            break
        last = energy
    return iterations, abs(last - target), abs(float(np.linalg.norm(state)) - 1.0)


def _quantum_walk(x: np.ndarray) -> tuple[int, float, float]:
    spectrum = np.fft.fft(_normalise(x))
    evolved = np.fft.ifft(spectrum * np.exp(-1j * np.linspace(0, 2 * math.pi, x.size)))
    return 1, _spectral_concentration(evolved), abs(float(np.linalg.norm(evolved)) - 1.0)


def _qml_kernel(x: np.ndarray) -> tuple[int, float, float]:
    samples = np.vstack([np.roll(x.real, i) for i in range(8)])
    samples = samples / np.maximum(np.linalg.norm(samples, axis=1, keepdims=True), 1e-15)
    kernel = np.square(samples @ samples.T)
    labels = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    same = kernel[labels[:, None] == labels[None, :]].mean()
    different = kernel[labels[:, None] != labels[None, :]].mean()
    return 1, float(same - different), float(np.max(np.abs(kernel - kernel.T)))


def _time_evolution(x: np.ndarray) -> tuple[int, float, float]:
    phases = np.linspace(-1.0, 1.0, x.size)
    exact = x * np.exp(-1j * phases)
    approx = x.copy()
    steps = 32
    dt = 1.0 / steps
    for _ in range(steps):
        approx *= 1.0 - 1j * phases * dt - 0.5 * (phases * dt) ** 2
    return steps, float(np.linalg.norm(approx - exact)), abs(float(np.linalg.norm(approx)) - float(np.linalg.norm(x)))


def _qec(x: np.ndarray) -> tuple[int, float, float]:
    syndromes = np.sign(np.vstack([np.roll(x.real, i) for i in range(6)]))
    separation = float(np.mean(np.abs(syndromes[:3].mean(0) - syndromes[3:].mean(0))))
    duplicate_rate = 1.0 - len({tuple(row) for row in syndromes}) / len(syndromes)
    return 1, separation, duplicate_rate


def _qft(x: np.ndarray) -> tuple[int, float, float]:
    restored = np.fft.ifft(np.fft.fft(x))
    error = float(np.linalg.norm(restored - x) / max(np.linalg.norm(x), 1e-15))
    return 2, error, abs(float(np.linalg.norm(restored)) - float(np.linalg.norm(x)))


_RUNNERS: dict[str, Callable[[np.ndarray], tuple[int, float, float]]] = {
    "qaoa": _qaoa_like,
    "vqe": _vqe_like,
    "quantum_walk": _quantum_walk,
    "qml_kernel": _qml_kernel,
    "time_evolution": _time_evolution,
    "qec": _qec,
    "qft": _qft,
}


def run_ablation(*, repeats: int = 5, dimension: int = 64, seed: int = 1517) -> list[Measurement]:
    if repeats < 1 or dimension < 4 or dimension % 2:
        raise ValueError("repeats must be positive and dimension must be even and >= 4")
    records: list[Measurement] = []
    for repeat in range(repeats):
        rng = np.random.default_rng(seed + repeat)
        base = _normalise(rng.normal(size=dimension) + 1j * rng.normal(size=dimension))
        for algorithm in ALGORITHMS:
            for arm in ARMS:
                tracemalloc.start()
                started = time.perf_counter_ns()
                transformed = apply_operator(base, arm)
                iterations, objective, stability = _RUNNERS[algorithm](transformed)
                elapsed = max((time.perf_counter_ns() - started) / 1e9, 1e-12)
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                records.append(Measurement(
                    algorithm=algorithm, arm=arm, repeat=repeat, seed=seed + repeat,
                    dimension=dimension, wall_clock_seconds=elapsed,
                    operator_applications=0 if arm in ("baseline", "lucas15_schedule") else 1,
                    iterations=iterations, final_objective_or_error=objective,
                    spectral_concentration=_spectral_concentration(transformed),
                    numerical_stability=stability, peak_memory_bytes=peak,
                    throughput_values_per_second=dimension / elapsed,
                ))
    return records


def summarise(records: list[Measurement]) -> dict[str, object]:
    groups: dict[tuple[str, str], list[Measurement]] = {}
    for record in records:
        groups.setdefault((record.algorithm, record.arm), []).append(record)
    rows = []
    for (algorithm, arm), values in sorted(groups.items()):
        rows.append({
            "algorithm": algorithm,
            "arm": arm,
            "runs": len(values),
            "median_wall_clock_seconds": statistics.median(v.wall_clock_seconds for v in values),
            "median_iterations": statistics.median(v.iterations for v in values),
            "median_final_objective_or_error": statistics.median(v.final_objective_or_error for v in values),
            "median_spectral_concentration": statistics.median(v.spectral_concentration for v in values),
            "max_numerical_stability_error": max(v.numerical_stability for v in values),
            "median_peak_memory_bytes": statistics.median(v.peak_memory_bytes for v in values),
            "median_throughput_values_per_second": statistics.median(v.throughput_values_per_second for v in values),
        })
    return {
        "claim_boundary": "numerical quantum-algorithm simulation; no physical quantum or mining acceleration claim",
        "constants": {"lucas_index": LUCAS_INDEX, "lucas_15": LUCAS_15, "pisot_15": PISOT_15, "m15": M15_EXACT.astype(int).tolist()},
        "backend": "numpy_cpu",
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--dimension", type=int, default=64)
    parser.add_argument("--seed", type=int, default=1517)
    parser.add_argument("--output", type=Path, default=Path("artifacts/lucas15_operator_ablation.json"))
    args = parser.parse_args()
    records = run_ablation(repeats=args.repeats, dimension=args.dimension, seed=args.seed)
    payload = {"summary": summarise(records), "measurements": [asdict(r) for r in records]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
