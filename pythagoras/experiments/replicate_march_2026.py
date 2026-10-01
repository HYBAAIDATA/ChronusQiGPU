"""
Replication of the 21 March 2026 A/B experiment (Executive Impact Report, HYBA Research)
=======================================================================================
Conditions (one engine per condition per seed; files processed in sequence as one
session, so discovered primitives and surrogate state carry across files under meta=ON):

    A  meta=OFF   fixed base operators, frozen surrogate priors, fixed CGP-inspired geometry
    B  meta=ON    surrogate learning, geometry evolution, discovery/promotion, transfer
    C  meta=OFF, budget-matched (ENH-05 interpretation): A given at least as many
                  evaluated candidates as B, to separate "adaptation" from "more search"

Reported per condition, mirroring the report's table: Total Δφ, avg final φ,
auto-discovered primitives, geometry evolution steps, surrogate RMSE, accept rate,
meta-steps — as mean ± sd across seeds — plus ENH-09 phase transitions and barrier
crossings, and the ENH-02 sensitivity verdict for every file.

Usage:
    python3 -m pythagoras.experiments.replicate_march_2026 [--seeds 10] [--generations 10]
            [--metric v12_1|v12_0] [--corpus benchmarks|stdlib4] [--no-euclid-gate]
            [--no-budget-matched] [--out results.json]
"""
import argparse
import glob
import json
import os
import statistics
from typing import Any, Dict, List

from pythagoras.core.diagnostics import phi_sensitivity
from pythagoras.core.phi_metric import PhiResonanceCalculator
from pythagoras.engine.evolution import PythagorasEvolutionEngine
from pythagoras.engine.primitive_repository import CrossFilePrimitiveRepository
from pythagoras.experiments.reference_metrics import phi_v12_0

BENCH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "benchmarks")
# Four structurally distinct real modules (CPython stdlib), for runs beyond the toy benchmarks
STDLIB4 = ["colorsys.py", "fnmatch.py", "graphlib.py", "textwrap.py"]

# Documented in the report, for side-by-side display (single dry run, 21 March 2026)
REPORTED = {
    "A": {"total_delta_phi": 0.1493, "avg_final_phi": 0.6665, "auto_discovered_primitives": 0,
          "geometry_evolution_steps": 0, "surrogate_rmse": 0.0817, "accept_rate": 0.000, "meta_steps": 0},
    "B": {"total_delta_phi": 0.1949, "avg_final_phi": 0.6779, "auto_discovered_primitives": 1,
          "geometry_evolution_steps": 2, "surrogate_rmse": 0.0803, "accept_rate": 0.400, "meta_steps": 2},
}


class _V12_0Calculator(PhiResonanceCalculator):
    def compute_phi(self, code_str: str) -> float:
        return phi_v12_0(code_str)


def _engine(meta: bool, seed: int, metric: str, gate: bool) -> PythagorasEvolutionEngine:
    eng = PythagorasEvolutionEngine(repository=CrossFilePrimitiveRepository(), seed=seed,
                                    euclid_gate=gate, meta_evolution=meta)
    if metric == "v12_0":
        eng.calculator = _V12_0Calculator()
    return eng


def run_session(files: Dict[str, str], meta: bool, seed: int, generations, metric: str, gate: bool) -> Dict[str, Any]:
    eng = _engine(meta, seed, metric, gate)
    per_file = {}
    for name, code in files.items():
        gens = generations[name] if isinstance(generations, dict) else generations
        per_file[name] = eng.run_optimization(name, code, gens)
    runs = list(per_file.values())
    total_delta = round(sum(r["total_delta_phi"] for r in runs), 6)
    evaluations = sum(r["total_evals_attempted"] for r in runs)
    deltas = [s["delta_phi"] for r in runs for s in r["accepted_steps"] if s["delta_phi"] > 0]
    rolling = [statistics.mean(deltas[max(0, i - 2):i + 1]) for i in range(len(deltas))]
    return {
        "total_delta_phi": total_delta,
        "avg_final_phi": round(statistics.mean(r["final_phi"] for r in runs), 6),
        "auto_discovered_primitives": sum(len(r["promoted_primitives"]) for r in runs),
        "geometry_evolution_steps": sum(len(r["geometry_evolution_steps"]) for r in runs),
        "surrogate_rmse": round(statistics.mean(r["surrogate_rmse"] for r in runs), 6),
        "accept_rate": round(statistics.mean(r["accept_rate"] for r in runs), 4),
        "meta_steps": sum(r["meta_steps"] for r in runs),
        "evaluations": evaluations,
        # ENH-08: compare conditions on an equal evaluation denominator and expose
        # a rolling three-win gain that is not distorted by different step counts.
        "gain_per_100_evaluations": round(100.0 * total_delta / max(evaluations, 1), 6),
        "rolling_3_win_gain": round(statistics.mean(rolling), 6) if rolling else 0.0,
        "phase_transitions": sum(len(r["phase_transitions"]) for r in runs),
        "barrier_crossings": sum(1 for r in runs for s in r["accepted_steps"] if s["is_barrier_crossing"]),
        "per_file": {n: {"initial_phi": r["initial_phi"], "final_phi": r["final_phi"],
                         "evals": r["total_evals_attempted"],
                         "generation_reached_final": max([s["generation"] for s in r["accepted_steps"]] or [0]),
                         "steps": [(s["generation"], s["winning_operator"], s["delta_phi"],
                                    s["is_phase_transition"], s["is_barrier_crossing"]) for s in r["accepted_steps"]]}
                     for n, r in per_file.items()},
    }


def _summary(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    keys = ["total_delta_phi", "avg_final_phi", "auto_discovered_primitives", "geometry_evolution_steps",
            "surrogate_rmse", "accept_rate", "meta_steps", "evaluations", "gain_per_100_evaluations",
            "rolling_3_win_gain", "phase_transitions", "barrier_crossings"]
    out = {}
    for k in keys:
        vals = [s[k] for s in sessions]
        mean = statistics.mean(vals)
        sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
        margin = (
            _t95(len(vals) - 1) * sd / (len(vals) ** 0.5)
            if len(vals) > 1
            else 0.0
        )
        out[k] = {"mean": round(statistics.mean(vals), 6),
                  "sd": round(sd, 6),
                  "ci95": [round(mean - margin, 6), round(mean + margin, 6)]}
    return out


def _paired_summary(left: List[Dict[str, Any]], right: List[Dict[str, Any]],
                    key: str) -> Dict[str, Any]:
    vals = [a[key] - b[key] for a, b in zip(left, right)]
    mean = statistics.mean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    margin = (
        _t95(len(vals) - 1) * sd / (len(vals) ** 0.5)
        if len(vals) > 1
        else 0.0
    )
    return {"mean": round(mean, 6), "sd": round(sd, 6),
            "ci95": [round(mean - margin, 6), round(mean + margin, 6)]}


def _t95(df: int) -> float:
    """Two-sided 95% Student-t critical values; normal approximation above 30."""
    table = {
        1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
        6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
        16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
        21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
        26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
    }
    return table.get(df, 1.96)


def load_corpus(corpus: str) -> Dict[str, str]:
    if corpus == "stdlib4":
        import sysconfig
        paths = [os.path.join(sysconfig.get_paths()["stdlib"], m) for m in STDLIB4]
    else:
        paths = sorted(glob.glob(os.path.join(BENCH, "*.py")))
    files = {}
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            files[os.path.basename(p)] = fh.read()
    return files


def replicate(seeds: int = 10, generations: int = 10, metric: str = "v12_1", gate: bool = True,
              corpus: str = "benchmarks", budget_matched: bool = True) -> Dict[str, Any]:
    files = load_corpus(corpus)

    score = phi_v12_0 if metric == "v12_0" else PhiResonanceCalculator().compute_phi
    diagnostics = {}
    for n, c in files.items():
        d = phi_sensitivity(c, score)
        diagnostics[n] = {k: d[k] for k in ("phi", "distinct_variants", "distinct_scores", "plateau_fraction", "verdict")}

    A, B, C = [], [], []
    for sd in range(seeds):
        a = run_session(files, False, sd, generations, metric, gate)
        b = run_session(files, True, sd, generations, metric, gate)
        # C: per-file generation budget raised until A's evaluations reach B's (cap 5x)
        budget = {}
        for n in files:
            g = generations
            while a["per_file"][n]["evals"] * g / max(generations, 1) < b["per_file"][n]["evals"] and g < 5 * generations:
                g += 1
            budget[n] = g
        A.append(a); B.append(b)
        if budget_matched:
            C.append(run_session(files, False, sd, budget, metric, gate))

    result = {
        "protocol": {"seeds": seeds, "generations": generations, "metric": metric, "euclid_gate": gate,
                     "corpus": corpus, "files": list(files)},
        "reported_21_march": REPORTED,
        "conditions": {"A_meta_off": _summary(A), "B_meta_on": _summary(B),
                       **({"C_budget_matched_off": _summary(C)} if C else {})},
        "identical_final_phi_A_vs_B": sum(
            all(A[i]["per_file"][n]["final_phi"] == B[i]["per_file"][n]["final_phi"] for n in files)
            for i in range(seeds)),
        "sensitivity_diagnostic": diagnostics,
        "example_session_seed0": {"A": A[0]["per_file"], "B": B[0]["per_file"]},
    }
    if C:
        result["primary_B_vs_C"] = {
            "total_delta_phi": _paired_summary(B, C, "total_delta_phi"),
            "gain_per_100_evaluations": _paired_summary(
                B, C, "gain_per_100_evaluations"
            ),
        }
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--generations", type=int, default=10)
    ap.add_argument("--metric", choices=["v12_1", "v12_0"], default="v12_1")
    ap.add_argument("--no-euclid-gate", action="store_true")
    ap.add_argument("--corpus", choices=["benchmarks", "stdlib4"], default="benchmarks")
    ap.add_argument("--no-budget-matched", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    res = replicate(args.seeds, args.generations, args.metric, not args.no_euclid_gate,
                    args.corpus, not args.no_budget_matched)
    text = json.dumps(res, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(json.dumps({k: res[k] for k in ("protocol", "conditions", "identical_final_phi_A_vs_B",
                                          "sensitivity_diagnostic")}, indent=2))


if __name__ == "__main__":
    main()
