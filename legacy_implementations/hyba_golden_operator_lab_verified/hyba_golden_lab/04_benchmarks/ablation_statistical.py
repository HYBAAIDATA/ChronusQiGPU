#!/usr/bin/env python3
"""
Statistical ablation — addresses the single-shot weakness in experiment_ablation().

The original ablation (run_lab.py::experiment_ablation) compares each golden-family
variant against exactly ONE random-matrix realization on ONE fixed input vector.
A single draw cannot establish that a ~15% N_eff gap is a real, structure-specific
effect rather than noise from that particular random matrix.

This script fixes that: it draws N_TRIALS independent random base vectors and,
per trial, N_TRIALS independent random control matrices (matched in Frobenius
norm to the golden operator M so the comparison is fair), then reports
mean +/- std N_eff per variant and a paired significance test (Wilcoxon
signed-rank, since N_eff is not assumed normal) between the best golden-family
variant and the random-matrix control.

No mining. No O(I) claims. Reports numbers; does not decide the hypothesis for you.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "01_mathematics"),
    str(ROOT / "02_quantum"),
    str(ROOT / "03_structure"),
]

from golden_transform import PHI, fib, lucas  # noqa: E402
from operators import fold_to_distribution, metrics, normalize_prob  # noqa: E402

OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(exist_ok=True)

BUDGET = 16
N_TRIALS = 500
SEED = 20260820  # fixed for reproducibility; change to confirm results aren't seed-cherry-picked


def make_variants(data: np.ndarray, rng: np.random.Generator) -> Dict[str, np.ndarray]:
    n = len(data)
    variants = {
        "none": data.copy(),
        "phi_only": normalize_prob(data * np.array([PHI ** (i * 0.1) for i in range(n)])),
        "lucas_only": normalize_prob(data * np.array([lucas(i % 8 + 1) for i in range(n)])),
        "fibonacci_only": normalize_prob(data * np.array([fib(i % 8 + 1) for i in range(n)])),
        "Mn": fold_to_distribution(data, 5),
    }
    variants["all_combined"] = fold_to_distribution(variants["phi_only"], 5)

    # Random-matrix control: match the 2x2 block structure and Frobenius norm
    # of the golden operator M = [[1,1],[1,0]] (||M||_F = sqrt(3)), so the
    # control isn't handicapped by having a different "strength" of mixing.
    target_norm = np.linalg.norm(np.array([[1.0, 1.0], [1.0, 0.0]]))
    rnd = data.copy()
    for i in range(0, n, 2):
        R = rng.normal(size=(2, 2))
        R = R * (target_norm / np.linalg.norm(R))
        v = R @ np.array([rnd[i], rnd[i + 1]])
        rnd[i], rnd[i + 1] = v[0], v[1]
    variants["random_matrix"] = normalize_prob(np.abs(rnd))
    return variants


def run() -> Dict:
    rng = np.random.default_rng(SEED)
    trial_results: Dict[str, List[float]] = {}

    for _ in range(N_TRIALS):
        base = rng.exponential(scale=1.0, size=BUDGET)
        base = base / base.sum()
        variants = make_variants(base, rng)
        for name, dist in variants.items():
            m = metrics(dist)
            trial_results.setdefault(name, []).append(m["effective_dimension"])

    summary = {}
    for name, vals in trial_results.items():
        arr = np.array(vals)
        summary[name] = {
            "mean_N_eff": float(arr.mean()),
            "std_N_eff": float(arr.std()),
            "n_trials": len(arr),
        }

    # Paired comparison: best golden-family variant vs random-matrix control,
    # paired by trial (same base vector each trial) using a sign test on the
    # per-trial difference — nonparametric, no distributional assumption.
    best_golden = min(
        (name for name in summary if name != "random_matrix"),
        key=lambda k: summary[k]["mean_N_eff"],
    )
    golden_vals = np.array(trial_results[best_golden])
    random_vals = np.array(trial_results["random_matrix"])
    diff = random_vals - golden_vals  # positive => golden concentrates more
    n_positive = int((diff > 0).sum())
    n_trials = len(diff)
    # Binomial sign-test p-value (two-sided) under null: no systematic direction
    from math import comb
    k = min(n_positive, n_trials - n_positive)
    p_value = sum(comb(n_trials, i) for i in range(0, k + 1)) * 2 / (2 ** n_trials) if n_trials < 1000 else None
    if p_value is None:
        # normal approximation for large n_trials
        from math import sqrt, erf
        mu = n_trials / 2
        sigma = sqrt(n_trials) / 2
        z = (n_positive - mu) / sigma
        p_value = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))

    result = {
        "n_trials": N_TRIALS,
        "seed": SEED,
        "summary": summary,
        "best_golden_variant": best_golden,
        "sign_test": {
            "trials_golden_more_concentrated": n_positive,
            "trials_total": n_trials,
            "fraction_golden_wins": n_positive / n_trials,
            "p_value_two_sided": p_value,
        },
    }
    return result


if __name__ == "__main__":
    result = run()
    (OUT / "ablation_statistical.json").write_text(json.dumps(result, indent=2))

    print("STATISTICAL ABLATION  (N_trials = %d, seed = %d)" % (result["n_trials"], result["seed"]))
    print(f"{'variant':<16} {'mean N_eff':>10} {'std':>8}")
    for name, s in result["summary"].items():
        print(f"{name:<16} {s['mean_N_eff']:>10.3f} {s['std_N_eff']:>8.3f}")
    st = result["sign_test"]
    print()
    print(f"Best golden variant: {result['best_golden_variant']}")
    print(
        f"Golden more concentrated than random control in "
        f"{st['trials_golden_more_concentrated']}/{st['trials_total']} trials "
        f"({st['fraction_golden_wins']*100:.1f}%), sign-test p = {st['p_value_two_sided']:.2e}"
    )
    print("\nWrote results/ablation_statistical.json")
