"""
TURING Discovery Engine v1 — searching construction space, not constants.
==========================================================================
Implements the loop:

    hypothesis -> construct geometry -> simulate -> measure ->
    induce rules -> holdout-validate -> feed best back downstream

Construction space: (alpha, divisor, power) triples. The lattice phase for
basis index j is 2*pi*alpha*frac(j^power / divisor). Prior phi-Weyl is the
special case (1/phi-divisor... alpha=INV_PHI, divisor=PHI, power=2).

The engine measures, per construction: star discrepancy D* of the ACTUAL
device phase set, unique-phase fraction (rationality collapse detector),
effective rank, condition number, alignment. It then tests which measured
property explains kernel geometry, induces threshold rules on a training
split of constructions, validates on held-out constructions, and feeds the
best discovered construction into a downstream task comparison against the
human-chosen phi prior and no-lattice baseline.
"""

import os
import time
import json
import math


import numpy as np

from phi_science import (
    PHI,
    INV_PHI,
    effective_rank,
    condition_number,
    kernel_target_alignment,
    engine_on,
    PhiKernelPipeline,
)
from phi_science import (
    PHI,
    INV_PHI,
    effective_rank,
    condition_number,
    kernel_target_alignment,
    engine_on,
    PhiKernelPipeline,
    _get_engine,
    train_test_split_idx,
    kernel_ridge_accuracy,
)

DIVISORS = {
    "phi": PHI,
    "sqrt2": math.sqrt(2),
    "sqrt3": math.sqrt(3),
    "e": math.e,
    "pi": math.pi,
    "plastic": 1.3247179572447460,  # plastic number, x^3 = x + 1
}

ALPHAS = {
    "one": 1.0,
    "inv_phi": INV_PHI,
    "half": 0.5,
    "sqrt2m1": math.sqrt(2) - 1,
    "third": 1 / 3,
    "golden2": 1 / (PHI**2),
    "rand_a": 0.37192834,
    "rand_b": 0.81263541,
}


def star_discrepancy(points):
    p = np.sort(np.mod(np.asarray(points, dtype=float), 1.0))
    p.size
    edges = np.concatenate(([0.0], p))
    left = np.abs(p - edges[:-1])
    right = np.abs(edges[1:] - p)
    return float(max(left.max(), right.max(), abs(1.0 - p[-1])))


def construction_properties(alpha, divisor, power, n_points):
    """Analytic properties of the device-phase set {alpha*frac(j^p/div)}."""
    j = np.arange(n_points, dtype=float)
    q = np.mod(j**power / divisor, 1.0)  # divisor-stage points
    phases = np.mod(alpha * q, 1.0)  # final device phases
    return {
        "d_star": star_discrepancy(phases),
        "unique_frac": float(np.unique(np.round(phases, 12)).size) / n_points,
        "q_d_star": star_discrepancy(q),  # pre-alpha coverage
    }


def _spearman(x, y):
    """Spearman rank correlation, returning NaN when either input is constant.

    The previous implementation ranked with argsort(argsort(v)) and correlated
    the ranks unconditionally. For a CONSTANT input that is not merely
    imprecise, it is wrong in a way that manufactures signal: argsort breaks
    ties by index, so a constant vector ranks as 0,1,2,...,n-1 -- the row
    order -- and the "correlation" returned is between the ORDER IN WHICH
    CONSTRUCTIONS WERE EVALUATED and the metric.

    That is not hypothetical here. `unique_frac` is identically 1.0 for all 96
    constructions (which is itself Discovery 1: the irrational divisor
    universalizes equidistribution, so no construction ever collapses), and
    this function reported rho = -0.1218 for it. Fed to a rule inducer, that
    becomes a threshold rule on search order dressed as a geometric law.

    Correlation with a constant is undefined. Say so.
    """
    xa = np.asarray(x, dtype=float)
    ya = np.asarray(y, dtype=float)
    if xa.size < 3 or ya.size < 3:
        return float("nan")
    if np.ptp(xa) == 0.0 or np.ptp(ya) == 0.0:
        return float("nan")
    rx = np.argsort(np.argsort(xa))
    ry = np.argsort(np.argsort(ya))
    with np.errstate(invalid="ignore"):
        rho = float(np.corrcoef(rx, ry)[0, 1])
    return rho


# ===========================================================================
# Search: evaluate every construction on real hardware
# ===========================================================================


def construction_space():
    out = []
    for dname, div in DIVISORS.items():
        for aname, alpha in ALPHAS.items():
            for power in (1, 2):
                out.append((f"a={aname}/d={dname}/p={power}", alpha, div, power))
    return out


def run_search(m=48, n_qubits=8, seeds=2, engine=None, constructions=None):
    pipe = PhiKernelPipeline(n_qubits, engine=engine)
    dim = pipe.dim
    cons = constructions or construction_space()
    rows = []
    datasets = []
    for s in range(seeds):
        rng = np.random.default_rng(5000 + s)
        X = rng.uniform(0, 2 * np.pi, size=(m, n_qubits))
        y = np.sign(np.sin(X[:, 0]) * np.cos(X[:, 1] / PHI))
        y[y == 0] = 1.0
        tr, te = train_test_split_idx(m, seed=s)
        datasets.append((X, y, tr, te, pipe.encode(X)))

    t0 = time.perf_counter()
    for name, alpha, div, power in cons:
        inv_div = 1.0 / div
        props = construction_properties(alpha, div, power, dim)
        accs, ranks, conds = [], [], []
        for X, y, tr, te, phis_enc in datasets:
            if engine_on(engine, phis_enc.shape):
                phis = engine.apply_phi_lattice_batch(
                    phis_enc, alpha=alpha, quadratic=(power == 2), inv_divisor=inv_div
                )
                phis = engine.apply_unitary_batch(pipe.h_n, phis)
            else:
                q = np.mod(np.arange(dim, dtype=float) ** power / div, 1.0)
                phis = phis_enc * np.exp(2j * np.pi * alpha * q)[None, :]
                phis = (pipe.h_n @ phis.T).T
            final = pipe.apply_feature_layer(X, phis)
            K = pipe.gram(final)
            accs.append(kernel_target_alignment(K[np.ix_(tr, tr)], y[tr]))
            ranks.append(effective_rank(K[np.ix_(tr, tr)]))
            conds.append(condition_number(K[np.ix_(tr, tr)]))
        rows.append(
            {
                "name": name,
                "alpha": float(alpha),
                "divisor": float(div),
                "power": power,
                "d_star": props["d_star"],
                "unique_frac": props["unique_frac"],
                "eff_rank": float(np.mean(ranks)),
                "cond": float(np.mean(conds)),
                "alignment": float(np.mean(accs)),
            }
        )
    search_seconds = time.perf_counter() - t0
    return {"rows": rows, "n_constructions": len(rows), "search_seconds": search_seconds}


# ===========================================================================
# Rule induction: what property explains kernel geometry?
# ===========================================================================


def induce_rules(search_results, holdout_frac=0.3):
    """Split constructions into train/holdout. On TRAIN, find the property
    (d_star, unique_frac) with the strongest monotone relationship to
    effective rank; induce a threshold rule; validate on HOLDOUT."""
    rows = search_results["rows"]
    rng = np.random.default_rng(31337)
    idx = rng.permutation(len(rows))
    cut = int((1 - holdout_frac) * len(rows))
    tr_rows = [rows[i] for i in idx[:cut]]
    ho_rows = [rows[i] for i in idx[cut:]]

    # Feature selection over candidate explanatory properties.
    #
    # The sentinel was `best_rho = -2.0` compared as `abs(rho) > abs(best_rho)`.
    # Spearman rho is bounded to [-1, 1], so abs(rho) can never exceed 2.0 and
    # the branch was unreachable: best_feature stayed None and the next line
    # raised KeyError(None). The intent was "weaker than any real correlation",
    # which under an absolute-value comparison is magnitude 0, not -2.
    best_feature, best_rho = None, 0.0
    rejected: list[str] = []
    for feature in ("d_star", "unique_frac"):
        values = [r[feature] for r in tr_rows]
        rho = _spearman(values, [r["eff_rank"] for r in tr_rows])
        if math.isnan(rho):
            # Constant (or degenerate) feature: carries no information about
            # anything. Excluded explicitly and reported, rather than silently
            # ranked by tie-break order.
            rejected.append(f"{feature} (constant or degenerate -- no signal)")
            continue
        if abs(rho) > abs(best_rho):
            best_feature, best_rho = feature, rho

    if best_feature is None:
        # An honest null. No candidate property explained the geometry on the
        # training split, so no rule is induced. Returning a rule here would
        # be fabricating one.
        return {
            "rule": None,
            "feature": None,
            "verdict": "NO_USABLE_FEATURE",
            "rejected_features": rejected,
            "note": (
                "No candidate property showed a usable monotone "
                "relationship to effective rank on the training split. "
                "No rule induced -- this is a null result, not a failure."
            ),
            "train_rows": len(tr_rows),
            "holdout_rows": len(ho_rows),
        }

    # threshold at the training median of the chosen feature
    vals = sorted(r[best_feature] for r in tr_rows)
    tau = vals[len(vals) // 2]
    high_geom_train = [r for r in tr_rows if r[best_feature] <= tau]

    def apply_rule(dataset):
        tp = sum(1 for r in dataset if r[best_feature] <= tau and r["eff_rank"] >= 30)
        fp = sum(1 for r in dataset if r[best_feature] <= tau and r["eff_rank"] < 30)
        fn = sum(1 for r in dataset if r[best_feature] > tau and r["eff_rank"] >= 30)
        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        return {"precision": round(precision, 3), "recall": round(recall, 3)}

    return {
        "rule": f"if {best_feature} <= {tau:.4f} then eff_rank >= 30 "
        f"(well-conditioned geometry)",
        "feature": best_feature,
        "rejected_features": rejected,
        "train_spearman_vs_effrank": round(best_rho, 4),
        "threshold": round(tau, 5),
        "train_fit": apply_rule(high_geom_train + [r for r in tr_rows if r[best_feature] > tau]),
        "holdout_validation": apply_rule(ho_rows),
    }


# ===========================================================================
# Feedback loop: feed the best discovered construction downstream
# ===========================================================================


def feedback_demo(search_results, engine=None, m=48, n_qubits=8, seeds=5):
    pipe = PhiKernelPipeline(n_qubits, engine=engine)
    rows = search_results["rows"]
    # discovered champion: highest alignment among low-D* constructions
    eligible = [r for r in rows if r["d_star"] <= 0.05] or rows
    champ = max(eligible, key=lambda r: r["alignment"])
    tasks = {
        "sin_cos": lambda X: np.sign(np.sin(X[:, 0]) * np.cos(X[:, 1] / PHI)),
        "xor_quad": lambda X: np.sign(np.sin(X[:, 0]) * np.sin(X[:, 1])),
    }
    out = {"champion": champ}
    from phi_mechanism import target_functions

    tf_map = target_functions()
    for task_name in ("sin_cos", "xor_quad", "circle"):
        tf = tf_map.get(task_name, tasks.get(task_name))
        acc = {"discovered": [], "phi_prior": [], "none": []}
        for s in range(seeds):
            rng = np.random.default_rng(8000 + s)
            X = rng.uniform(0, 2 * np.pi, size=(m, n_qubits))
            y = tf(X)
            y[y == 0] = 1.0
            tr, te = train_test_split_idx(m, seed=s)
            phis_enc = pipe.encode(X)

            def finish(phs):
                final = pipe.apply_feature_layer(X, phs)
                K = pipe.gram(final)
                return kernel_ridge_accuracy(K[np.ix_(tr, tr)], y[tr], K[np.ix_(te, tr)], y[te])

            if engine_on(engine, phis_enc.shape):
                d_phis = engine.apply_phi_lattice_batch(
                    phis_enc,
                    alpha=champ["alpha"],
                    quadratic=(champ["power"] == 2),
                    inv_divisor=1.0 / champ["divisor"],
                )
                d_phis = engine.apply_unitary_batch(pipe.h_n, d_phis)
                p_phis = engine.apply_phi_lattice_batch(phis_enc, alpha=INV_PHI)
                p_phis = engine.apply_unitary_batch(pipe.h_n, p_phis)
                n_phis = engine.apply_unitary_batch(pipe.h_n, phis_enc)
            else:
                j = np.arange(pipe.dim, dtype=float)
                q_d = np.mod(j ** champ["power"] / champ["divisor"], 1.0)
                d_phis = phis_enc * np.exp(2j * np.pi * champ["alpha"] * q_d)[None, :]
                d_phis = (pipe.h_n @ d_phis.T).T
                q_p = np.mod(j**2 / PHI, 1.0)
                p_phis = phis_enc * np.exp(2j * np.pi * INV_PHI * q_p)[None, :]
                p_phis = (pipe.h_n @ p_phis.T).T
                n_phis = (pipe.h_n @ phis_enc.T).T
            acc["discovered"].append(finish(d_phis))
            acc["phi_prior"].append(finish(p_phis))
            acc["none"].append(finish(n_phis))
        out[task_name] = {k: round(float(np.mean(v)), 4) for k, v in acc.items()}
    return out


# ===========================================================================
# Main
# ===========================================================================


def main():
    engine = _get_engine()
    print("ENGINE:", engine.info() if engine else "CPU fallback only")

    print("\n[1/3] Searching construction space (alpha x divisor x power)...")
    search = run_search(engine=engine)
    rows = sorted(search["rows"], key=lambda r: -r["alignment"])
    for r in rows[:8]:
        print(
            f"  {r['name']:28s} align={r['alignment']:.4f} "
            f"eff_rank={r['eff_rank']:.2f} cond={r['cond']:.3f} "
            f"D*={r['d_star']:.4f} uniq={r['unique_frac']:.3f}"
        )
    print(f"  ... {search['n_constructions']} constructions in " f"{search['search_seconds']:.1f}s")

    print("\n[2/3] Rule induction + holdout validation...")
    rules = induce_rules(search)
    for k, v in rules.items():
        print(f"  {k}: {v}")

    print("\n[3/3] Feedback loop: discovered champion vs human prior...")
    demo = feedback_demo(search, engine=engine)
    champ = demo.pop("champion")
    print(
        f"  champion construction: {champ['name']} "
        f"(alpha={champ['alpha']:.4f}, D*={champ['d_star']:.4f})"
    )
    for task, accs in demo.items():
        print(
            f"  {task:9s}: discovered={accs['discovered']} "
            f"phi_prior={accs['phi_prior']} none={accs['none']}"
        )

    report = {
        "search": {
            "rows": search["rows"],
            "n_constructions": search["n_constructions"],
            "search_seconds": search["search_seconds"],
        },
        "rules": rules,
        "feedback": demo,
    }
    out_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "TURING_DISCOVERY_RESULTS.json"
    )
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nResults written to {os.path.abspath(out_path)}")


if __name__ == "__main__":
    main()
