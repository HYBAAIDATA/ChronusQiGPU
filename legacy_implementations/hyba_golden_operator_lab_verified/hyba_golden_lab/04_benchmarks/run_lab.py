#!/usr/bin/env python3
"""HYBA Golden Operator Laboratory — evidence machine. No mining. No O(I) claims."""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "01_mathematics"),
    str(ROOT / "02_quantum"),
    str(ROOT / "03_structure"),
]

from golden_transform import (  # noqa: E402
    PHI,
    PSI,
    all_identities_hold,
    apply_Mn,
    coherence,
    fib,
    lucas,
    pisano,
    project,
    verify_identities,
)
from core import (  # noqa: E402
    born,
    entanglement_spectrum,
    grover,
    qaoa_ising,
    qft,
    superposition,
)
from operators import fold_to_distribution, metrics, normalize_prob  # noqa: E402
from coherence_measurement import pair_born, score_pairs, verify_fib_amplification  # noqa: E402

OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(exist_ok=True)
COMMIT = "lab-freeze-1"


def record(experiment_id: str, operator: str, baseline: str, params: Dict, meas: Dict) -> Dict:
    return {
        "experiment_id": experiment_id,
        "commit": COMMIT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "parameters": params,
        "baseline": baseline,
        "operator": operator,
        "input_dimension": meas.get("input_dimension"),
        "effective_dimension": meas.get("effective_dimension"),
        "entropy": meas.get("entropy"),
        "coherence": meas.get("mean_pair_coherence", meas.get("coherence")),
        "entanglement": meas.get("entanglement"),
        "candidate_count": meas.get("candidate_count"),
        "verified_operations": meas.get("verified_operations"),
        "wall_time": meas.get("wall_time"),
        "success": meas.get("success"),
        "marked_probability": meas.get("marked_probability"),
        "max_probability": meas.get("max_probability"),
        "phi_overlap": meas.get("phi_overlap"),
        "energy": meas.get("energy"),
        "gap": meas.get("gap"),
        "notes": meas.get("notes"),
    }


def experiment_identities() -> List[Dict]:
    t0 = time.perf_counter()
    ok = True
    for n in range(1, 21):
        ok = ok and all(verify_identities(n).values())
    return [record(
        "identity_Mn", "M^n integer", "classical arithmetic",
        {"n": list(range(1, 21))},
        {
            "verified_operations": 20,
            "success": ok,
            "wall_time": time.perf_counter() - t0,
            "notes": "integer Cassini/Lucas/Binet; float only secondary",
            "input_dimension": 2,
            "effective_dimension": 2,
        },
    )]


def experiment_coherence() -> List[Dict]:
    rows = []
    groups = {
        "structured_fib": [(fib(k + 1), fib(k)) for k in (5, 8, 10, 15)],
        "unstructured": [(1.0, 1.0), (math.pi, math.e), (15.0, 15.0), (1.0, -1.0)],
        "anti_phi": [(PSI, 1.0)],
        "phi_aligned": [(PHI, 1.0)],
    }
    for label, pairs in groups.items():
        cohs = [coherence(x, y) for x, y in pairs]
        finite = [c for c in cohs if math.isfinite(c)]
        rows.append(record(
            f"coherence_{label}", "Phi/psi project", "raw pair",
            {"pairs": pairs, "label": label},
            {
                "coherence": float(np.mean(finite)) if finite else float("inf"),
                "success": True,
                "notes": f"values={cohs}",
                "input_dimension": 2,
                "effective_dimension": 1.0 if label == "phi_aligned" else 2.0,
            },
        ))
    return rows


def experiment_grover() -> List[Dict]:
    nq, marked = 6, [5, 12, 20, 33]
    t0 = time.perf_counter()
    base = grover(nq, marked)
    tb = time.perf_counter() - t0
    mb = metrics(base["distribution"], marked)
    mb.update({
        "success": base["success"], "wall_time": tb,
        "candidate_count": 2 ** nq, "verified_operations": base["iterations"],
        "entanglement": entanglement_spectrum(base["state"], 3)["entropy"],
    })
    rows = [record("grover_baseline", "standard Grover", "uniform+oracle",
                   {"n_qubits": nq, "marked": marked}, mb)]
    t0 = time.perf_counter()
    folded = fold_to_distribution(base["distribution"], 3)
    mt = metrics(folded, marked)
    mt.update({
        "success": int(np.argmax(folded)) in marked,
        "wall_time": time.perf_counter() - t0,
        "candidate_count": 2 ** nq,
        "verified_operations": base["iterations"],
        "notes": "fold is representation; Grover itself unchanged",
    })
    rows.append(record("grover_folded_Mn3", "M^3 fold of Born", "standard Grover",
                       {"n_qubits": nq, "marked": marked, "fold_n": 3}, mt))
    return rows


def experiment_qaoa() -> List[Dict]:
    n, p = 3, 3
    J = np.zeros((n, n))
    J[0, 1] = J[1, 0] = J[1, 2] = J[2, 1] = 1.0
    beta_b = np.array([math.pi * (k + 1) / (p + 1) for k in range(p)])
    gamma_b = np.array([2 * math.pi * (k + 1) / (p + 1) for k in range(p)])
    beta_a = np.array([math.pi * (1 / PHI) * (k + 1) / (p + 1) for k in range(p)])
    gamma_a = np.array([
        2 * math.pi * ((k * PHI) % 1.0) * (lucas(k + 1) / (lucas(k + 1) + PHI ** k))
        for k in range(p)
    ])
    rows = []
    for name, beta, gamma, op in (
        ("qaoa_baseline", beta_b, gamma_b, "uniform angles"),
        ("qaoa_pisot_lucas", beta_a, gamma_a, "Pisot x Lucas angles"),
    ):
        t0 = time.perf_counter()
        r = qaoa_ising(n, J, beta, gamma)
        m = metrics(r["distribution"])
        m.update({
            "energy": r["energy"], "gap": r["gap"], "success": r["gap"] < 1.5,
            "wall_time": time.perf_counter() - t0, "verified_operations": p,
            "entanglement": entanglement_spectrum(r["state"], 1)["entropy"],
        })
        rows.append(record(name, op, "path Ising p=3", {"n": n, "p": p}, m))
    return rows


def experiment_qft_pisano() -> List[Dict]:
    nq = 4
    psi = superposition(2 ** nq)
    t0 = time.perf_counter()
    p = born(qft(psi))
    m = metrics(p)
    m.update({"wall_time": time.perf_counter() - t0, "success": True,
              "notes": f"pisano(16)={pisano(16)}"})
    rows = [record("qft_uniform", "exact QFT", "uniform", {"n_qubits": nq}, m)]
    pi = pisano(2 ** nq)
    folded = np.zeros(pi)
    for i, v in enumerate(p):
        folded[i % pi] += v
    mf = metrics(folded)
    mf.update({"success": True, "notes": "bin fold is representation, not a faster QFT"})
    rows.append(record("qft_pisano_fold", "Pisano bin fold", "exact QFT",
                       {"n_qubits": nq, "pisano": pi}, mf))
    return rows


def experiment_search_structure() -> List[Dict]:
    N = 64
    target = 21
    t0 = time.perf_counter()
    found_b = next(i for i in range(N) if i == target)
    tb = time.perf_counter() - t0
    p_b = np.ones(N) / N
    mb = metrics(p_b, [target])
    mb.update({"success": found_b == target, "wall_time": tb, "candidate_count": N,
               "verified_operations": N, "notes": "uniform scan"})
    t0 = time.perf_counter()
    scores = np.array([abs(coherence(float((i + 1) or 1), float(i or 1))) for i in range(N)])
    order = np.argsort(-np.nan_to_num(scores, nan=0.0, posinf=1e9))
    evals = int(np.where(order == target)[0][0]) + 1
    ts = time.perf_counter() - t0
    p_s = normalize_prob(np.nan_to_num(scores, nan=0.0, posinf=1e6))
    ms = metrics(p_s, [target])
    ms.update({"success": True, "wall_time": ts, "candidate_count": N,
               "verified_operations": evals,
               "notes": f"evaluations_to_target={evals} vs N={N}"})
    return [
        record("search_classical", "linear scan", "unsorted domain", {"N": N, "target": target}, mb),
        record("search_structured", "coherence rank", "unsorted domain", {"N": N, "target": target}, ms),
    ]


def experiment_ablation() -> List[Dict]:
    rng_budget = 16
    data = np.array([fib(i % 12 + 1) for i in range(rng_budget)], dtype=float)
    data = data / data.sum()
    variants = {
        "none": data.copy(),
        "phi_only": normalize_prob(data * np.array([PHI ** (i * 0.1) for i in range(rng_budget)])),
        "lucas_only": normalize_prob(data * np.array([lucas(i % 8 + 1) for i in range(rng_budget)])),
        "fibonacci_only": normalize_prob(data * np.array([fib(i % 8 + 1) for i in range(rng_budget)])),
        "Mn": fold_to_distribution(data, 5),
    }
    paired = data.copy()
    for i in range(0, rng_budget, 2):
        a, b = project(paired[i], paired[i + 1])
        paired[i], paired[i + 1] = abs(a), abs(b)
    variants["phi_psi_project"] = normalize_prob(paired)
    variants["all_combined"] = fold_to_distribution(variants["phi_psi_project"], 5)
    R = np.array([[2.0, 0.3], [0.1, -1.7]])
    rnd = data.copy()
    for i in range(0, rng_budget, 2):
        v = R @ np.array([rnd[i], rnd[i + 1]])
        rnd[i], rnd[i + 1] = v[0], v[1]
    variants["random_matrix"] = normalize_prob(np.abs(rnd))
    rows = []
    for name, dist in variants.items():
        m = metrics(dist)
        m.update({"success": True, "verified_operations": 1,
                  "notes": "ablation; lower N_eff is concentration, not automatically better"})
        rows.append(record(f"ablation_{name}", name, "fib-modulated vector",
                           {"budget": rng_budget, "component": name}, m))
    return rows


def experiment_adversarial() -> List[Dict]:
    rows = []
    n = 8
    states = {
        "phi_aligned": np.array([PHI, 1.0] * (n // 2)),
        "psi_aligned": np.array([PSI, 1.0] * (n // 2)),
        "unstructured": np.array([1.0] * n),
        "anti_mixed": np.array([PSI, PHI] * (n // 2)),
    }
    for name, vec in states.items():
        before = metrics(normalize_prob(np.abs(vec)))
        after = metrics(fold_to_distribution(vec, 8))
        before.update({"success": True, "notes": "pre-fold"})
        after.update({"success": True, "notes": "post M^8 fold"})
        rows.append(record(f"adv_{name}_before", "identity", name, {"n": n}, before))
        rows.append(record(f"adv_{name}_after_Mn8", "M^8", name, {"n": n}, after))
    return rows


def experiment_coherence_stats() -> List[Dict]:
    """M^n on exact Born pairs from Grover/QAOA — not random samples, not state vectors."""
    rows = []
    checks = verify_fib_amplification()
    rows.append(record(
        "mn_fib_identity", "M^n on (F_{k+1},F_k)", "integer Fibonacci",
        {"checks": checks},
        {
            "success": all(c["match"] for c in checks),
            "verified_operations": len(checks),
            "notes": "M^n [F_{k+1},F_k] = [F_{k+n+1},F_{k+n}] exact",
            "input_dimension": 2,
            "effective_dimension": 1,
        },
    ))
    g = grover(6, [5, 12, 20, 33])
    sg = score_pairs(pair_born(g["distribution"]))
    mg = metrics(g["distribution"], [5, 12, 20, 33])
    mg.update({
        "success": True,
        "coherence": sg["mean_coherence"],
        "notes": f"Born-pair M^n: align={sg['mean_phi_alignment']:.4f} amp={sg['phi_amplification_factor']:.4f}",
        "verified_operations": sg["applied_count"],
    })
    rows.append(record("coherence_grover_born_pairs", "M^n on Grover Born pairs",
                       "exact Grover distribution", {"n_qubits": 6}, mg))
    n, p = 3, 3
    J = np.zeros((n, n))
    J[0, 1] = J[1, 0] = J[1, 2] = J[2, 1] = 1.0
    beta = np.array([math.pi * (1 / PHI) * (k + 1) / (p + 1) for k in range(p)])
    gamma = np.array([2 * math.pi * ((k * PHI) % 1.0) for k in range(p)])
    q = qaoa_ising(n, J, beta, gamma)
    sq = score_pairs(pair_born(q["distribution"]))
    mq = metrics(q["distribution"])
    mq.update({
        "success": True,
        "energy": q["energy"],
        "gap": q["gap"],
        "coherence": sq["mean_coherence"],
        "notes": f"QAOA Born-pair align={sq['mean_phi_alignment']:.4f}",
        "verified_operations": sq["applied_count"],
    })
    rows.append(record("coherence_qaoa_born_pairs", "M^n on QAOA Born pairs",
                       "exact QAOA distribution", {"n": n, "p": p}, mq))
    return rows


def experiment_complexity() -> List[Dict]:
    rows = []
    for n_idx in (6, 8, 10, 12):
        target = fib(n_idx)
        N = 2 ** n_idx
        I = math.log2(max(n_idx, 2))
        t_class = N
        cap = min(N, 256)
        scores = [abs(coherence(float(i + 1), float(max(i, 1)))) for i in range(cap)]
        order = np.argsort(-np.array(scores))
        tgt = target % cap
        t_hyba = int(np.where(order == tgt)[0][0]) + 1
        m = {
            "input_dimension": float(cap),
            "effective_dimension": float(t_hyba),
            "candidate_count": cap,
            "verified_operations": t_hyba,
            "success": True,
            "notes": f"I={I:.4f} T_classical={t_class} T_hyba={t_hyba} N={N} — no complexity claim",
        }
        rows.append(record(
            f"complexity_n{n_idx}", "coherence rank", "linear scan",
            {"n_idx": n_idx, "I_bits": I, "N": N, "T_classical": t_class, "T_hyba": t_hyba},
            m,
        ))
    return rows


def main():
    print("HYBA GOLDEN OPERATOR LABORATORY")
    print("Pure quantum / algebraic evidence. No mining. No O(I) claims.")
    frozen = all_identities_hold()
    print(f"Identity battery frozen: {frozen}")
    if not frozen:
        print("REFUSING to emit operator measurements — identities failed.")
        return 1
    all_rows: List[Dict[str, Any]] = []
    for fn in (
        experiment_identities,
        experiment_coherence,
        experiment_grover,
        experiment_qaoa,
        experiment_qft_pisano,
        experiment_search_structure,
        experiment_ablation,
        experiment_adversarial,
        experiment_coherence_stats,
        experiment_complexity,
    ):
        print(f"  running {fn.__name__}...")
        all_rows.extend(fn())
    out_path = OUT / "battery.json"
    out_path.write_text(json.dumps(all_rows, indent=2, default=str))
    print(f"\nWrote {len(all_rows)} records → {out_path}")
    print(f"\n{'id':<28} {'operator':<24} {'N_eff':>8} {'H':>8} {'Pmax':>8} {'ok':>4}")
    for r in all_rows:
        ne, h, pm = r.get("effective_dimension"), r.get("entropy"), r.get("max_probability")
        def fmt(v):
            return "   n/a" if v is None else f"{float(v):.3f}"
        print(f"{r['experiment_id']:<28} {str(r['operator'])[:24]:<24} "
              f"{fmt(ne):>8} {fmt(h):>8} {fmt(pm):>8} {str(r.get('success')):>4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
