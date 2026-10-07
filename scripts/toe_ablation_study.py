"""Held-out ablation study: does each TOE capability change outcomes?

Seven randomized task families with known ground truth. For each, full TOE
is compared with the same machine minus one capability. Nothing is tuned:
every threshold in TOE is a declared constant. Development seeds (0..19)
were used while writing this script; the reported numbers use the disjoint
held-out seeds (1000+). A capability that works but shows no measured
benefit is reported as such.

Usage: python scripts/toe_ablation_study.py [--n 60] [--report PATH]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from toe.causal_stack import futures_env  # noqa: E402
from toe.geometry import routing_study  # noqa: E402
from toe.machine import ACQUIRE_EVIDENCE, TOEMachine  # noqa: E402
from toe.planning import OperatorSpec  # noqa: E402
from toe.policy import Objective  # noqa: E402
from toe.problem import Problem, Structure  # noqa: E402

PHI = (1 + 5 ** 0.5) / 2
HELD_OUT = 1000


class _Rung2Machine(TOEMachine):
    """Ablation: counterfactual (rung-3) futures removed."""

    def _futures_fn(self, problem, scm, noise):
        env = futures_env(scm, noise)
        return (lambda state, action: env(action)), 2, "ablation: interventional only"


def _rate(xs: List[bool]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def _wilson(k: int, n: int) -> List[float]:
    if n == 0:
        return [float("nan"), float("nan")]
    z = 1.96
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [max(0.0, c - h), min(1.0, c + h)]


# -- F1 confounded choice: causal structure vs association -------------------


def family_confounding(seeds: List[int], control: bool = False) -> Dict[str, Any]:
    m = TOEMachine(lens_policy="measured")
    full, ablated = [], []
    for seed in seeds:
        rng = random.Random(seed)
        w_sx, w_sy = rng.uniform(1, 3), rng.uniform(1, 3) * rng.choice((-1, 1))
        w_xy = rng.uniform(0.2, 1.0) * rng.choice((-1, 1))
        if control:  # no confounding path: association is then causal
            w_sx = 0.0
        rows = []
        for _ in range(300):
            s = rng.gauss(0, 1)
            x = w_sx * s + rng.gauss(0, 0.5)
            rows.append((s, x, w_xy * x + w_sy * s + rng.gauss(0, 0.5)))
        p = Problem(
            domain="ablation.confounding",
            state={"S": 0.0, "X": 0.0, "Y": 0.0},
            structure=Structure.of([("S", "X"), ("S", "Y"), ("X", "Y")]),
            samples={"S": [r[0] for r in rows], "X": [r[1] for r in rows], "Y": [r[2] for r in rows]},
            operators=(OperatorSpec("set_X", "X", (-1.0, 1.0)),),
            objective=Objective("Y"),
        )
        best = "set_X=1.0" if w_xy > 0 else "set_X=-1.0"
        ep = m.run(replace(p, domain=f"ablation.confounding.{seed}"))
        full.append(ep["decision"]["selected_action"] == best)
        ablated.append(m._associational_pick(p) == best)
    return _arms("confounded choice", "causal structure", full, ablated)


# -- F2 unit-level decisions: counterfactual vs interventional ---------------


def family_counterfactual(seeds: List[int], control: bool = False) -> Dict[str, Any]:
    full_m, abl_m = TOEMachine(lens_policy="measured"), _Rung2Machine(lens_policy="measured")
    full, ablated = [], []
    for seed in seeds:
        rng = random.Random(seed)
        wx, wz = rng.uniform(0.5, 2.0), rng.uniform(0.5, 2.0)
        ux, uz, uy = (rng.gauss(0, 1) for _ in range(3))
        if control:  # unit at the mean: its factual values carry no extra information
            ux = uz = 0.0
        x0, z0 = PHI * ux, PHI * uz
        y0 = wx * x0 + wz * z0 + PHI * uy
        lift = rng.uniform(0.5, 1.5)
        # Two candidate interventions on the SAME unit: raise x or raise z.
        truth_x = wx * (x0 + lift) + wz * z0 + PHI * uy
        truth_z = wx * x0 + wz * (z0 + lift) + PHI * uy
        best = "raise_x" if truth_x > truth_z else "raise_z"
        p = Problem(
            domain=f"ablation.counterfactual.{seed}",
            state={"x": x0, "z": z0, "y": y0},
            structure=Structure.of([("x", "y", wx), ("z", "y", wz)]),
            operators=(OperatorSpec("raise_x", "x", (x0 + lift,)), OperatorSpec("raise_z", "z", (z0 + lift,))),
            objective=Objective("y"),
        )
        full.append(full_m.run(p)["decision"]["selected_action"].startswith(best))
        ablated.append(abl_m.run(p)["decision"]["selected_action"].startswith(best))
    return _arms("unit-level choice", "counterfactual futures (abduction)", full, ablated)


# -- F3 navigation: multi-representation vs coordinates only -----------------


def family_navigation(seeds: List[int], control: bool = False) -> Dict[str, Any]:
    full, ablated, stretch = [], [], []
    for seed in seeds:
        rng = random.Random(seed)
        w = h = 7
        walls = set()
        for col in rng.sample(range(1, w - 1, 2), 2):  # non-adjacent: always connected
            gap = rng.randrange(h)
            walls |= {(col, y) for y in range(h) if y != gap}
        if control:  # open grid: coordinates are not misleading
            walls = set()
        nodes = [(x, y) for x in range(w) for y in range(h) if (x, y) not in walls]
        keep = set(nodes)
        edges = [((x, y), (x + dx, y + dy)) for x, y in nodes for dx, dy in ((1, 0), (0, 1)) if (x + dx, y + dy) in keep]
        study = routing_study(edges, euclidean={n: (float(n[0]), float(n[1])) for n in nodes}, tau=2.0)
        full.append(study["hyperbolic"]["delivery_rate"])
        ablated.append(study["euclidean"]["delivery_rate"])
        stretch.append(study["hyperbolic"]["mean_stretch"])
    return {
        "family": "navigation through walled grids",
        "removed": "multi-representation (geometry/topology beyond coordinates)",
        "metric": "all-pairs greedy delivery rate",
        "full_mean": _mean(full),
        "ablated_mean": _mean(ablated),
        "full_mean_stretch": _mean(stretch),
        "tasks": len(seeds),
        "benefit": _mean(full) > _mean(ablated),
        "note": "topological BFS also always delivers (global knowledge); the comparison is local greedy routing",
    }


# -- F4 learning: world-model revision vs frozen prior -----------------------


def family_learning(seeds: List[int], control: bool = False) -> Dict[str, Any]:
    full, ablated = [], []
    for seed in seeds:
        rng = random.Random(seed)
        true_x, true_z = rng.uniform(0.1, 0.9), rng.uniform(1.1, 1.9)
        if control:  # the prior already orders the levers correctly
            true_x, true_z = rng.uniform(1.6, 2.4), rng.uniform(0.6, 1.4)
        p = Problem(
            domain=f"ablation.learning.{seed}",
            state={"x": 0.0, "z": 0.0},
            structure=Structure.of([("x", "y", 2.0), ("z", "y", 1.0)]),
            operators=(OperatorSpec("raise_x", "x", (1.0,)), OperatorSpec("raise_z", "z", (1.0,))),
            objective=Objective("y"),
            noise_sd={"x": 1.0, "z": 1.0, "y": 0.1},
        )
        m = TOEMachine(lens_policy="measured")
        ep = m.run(p)
        rows = []
        for _ in range(6):
            z = PHI * rng.gauss(0, 1)
            rows.append({"x": 1.0, "z": z, "y": true_x + true_z * z + PHI * rng.gauss(0, 0.1)})
        m.learn(ep, rows, persist=False)
        best = "raise_x" if true_x > true_z else "raise_z"
        full.append(m.run(p)["decision"]["selected_action"].startswith(best))
        ablated.append(TOEMachine(lens_policy="measured").run(p)["decision"]["selected_action"].startswith(best))
    return _arms("misspecified prior", "world-model revision + memory", full, ablated)


# -- F5 value of information: ask-before-act vs act-now ----------------------


def family_voi(seeds: List[int], control: bool = False) -> Dict[str, Any]:
    full, ablated, asked, asked_needed = [], [], 0, 0
    for seed in seeds:
        rng = random.Random(seed)
        true_x = rng.uniform(0.2, 2.0)
        prior = 1.4
        span = (0.2, 1.0, 2.0)
        if control:  # the plausible range cannot flip the decision
            true_x, prior, span = rng.uniform(1.5, 2.5), 2.0, (1.5, 2.0, 2.5)
        p = Problem(
            domain=f"ablation.voi.{seed}",
            state={"x": 0.0, "z": 0.0},
            structure=Structure.of([("x", "y", prior), ("z", "y", 1.0)]),
            operators=(OperatorSpec("raise_x", "x", (1.0,)), OperatorSpec("raise_z", "z", (1.0,))),
            objective=Objective("y"),
            uncertain={"edge:x->y": span},
            noise_sd={"x": 1.0, "z": 1.0, "y": 0.1},
        )
        best = "raise_x" if true_x > 1.0 else "raise_z"
        m = TOEMachine(lens_policy="measured")
        ep = m.run(p)
        ablated.append(ep["decision"]["selected_action"].startswith(best))
        if ep["status"] == ACQUIRE_EVIDENCE:
            asked += 1
            asked_needed += (ep["decision"]["selected_action"].startswith(best)) is False
            rows = []
            for _ in range(6):
                z = PHI * rng.gauss(0, 1)
                rows.append({"x": 1.0, "z": z, "y": true_x + z + PHI * rng.gauss(0, 0.1)})
            m.learn(ep, rows, persist=False)
            ep = m.run(p)
        full.append(ep["decision"]["selected_action"].startswith(best))
    out = _arms("uncertain lever strength", "value-of-information gate", full, ablated)
    out.update({"evidence_requests": asked, "requests_where_prior_choice_was_wrong": asked_needed,
                "cost_note": "the full arm pays one 6-observation experiment per request; act-now pays none"})
    return out


# -- F6 precision: exact escalation vs float-only ----------------------------


def family_precision(seeds: List[int], control: bool = False) -> Dict[str, Any]:
    m = TOEMachine(lens_policy="measured")
    full, ablated = [], []
    for seed in seeds:
        rng = random.Random(seed)
        big = float(2 ** rng.randint(53, 60))
        if control:  # well-separated magnitudes: float64 is exact enough
            big = 1.0
        small = float(rng.choice((1, -1)))
        p = Problem(
            domain=f"ablation.precision.{seed}",
            structure=Structure.of([("a", "b", 1.0), ("a", "c", 1.0), ("a", "y", big), ("b", "y", small), ("c", "y", -big)]),
            operators=(OperatorSpec("do_a", "a", (0.0, 1.0)),),
            objective=Objective("y"),
        )
        best = "do_a=1.0" if small > 0 else "do_a=0.0"
        ep = m.run(p)
        full.append(ep["decision"]["selected_action"] == best)
        ablated.append(ep["decision"]["policy"]["selected_action"] == best)
    return _arms("cancellation near-ties", "adaptive precision (exact Q(phi) escalation)", full, ablated)


# -- F7 planning: futures-backed plan vs greedy -------------------------------


def family_planning(seeds: List[int], control: bool = False) -> Dict[str, Any]:
    m = TOEMachine(lens_policy="measured")
    full, ablated = [], []
    for seed in seeds:
        rng = random.Random(seed)
        d1 = rng.uniform(1.0, 3.0)
        d2 = rng.uniform(d1 * 1.05, d1 * 1.95)
        w = rng.uniform(0.5, 2.0)
        p = Problem(
            domain=f"ablation.planning.{seed}",
            state={"x": 0.0, "y": 0.0},
            structure=Structure.of([("x", "y", w)]),
            operators=(
                (OperatorSpec("small", "x", (d1,), (), 1.0), OperatorSpec("big", "x", (d2,), (), 2.0))
                if control  # absolute levels, no budget: a linear model gives plan == greedy
                else (OperatorSpec("small", "x", (), (d1,), 1.0), OperatorSpec("big", "x", (), (d2,), 2.0))
            ),
            objective=Objective("y"),
            horizon=2,
            budget=None if control else 2.0,
            noise_sd={"x": 0.1, "y": 0.1},
        )
        ep = m.run(p)
        pl = ep["plan"]
        full.append(pl["plan"]["objective_value"])
        ablated.append(pl["greedy"]["objective_value"])
    gains = [f - a for f, a in zip(full, ablated)]
    return {
        "family": "budgeted multi-step improvement",
        "removed": "multi-step planning over the futures model (greedy one-step instead)",
        "metric": "expected objective reached",
        "full_mean": _mean(full),
        "ablated_mean": _mean(ablated),
        "mean_gain": _mean(gains),
        "tasks_where_plan_better": sum(g > 1e-12 for g in gains),
        "tasks": len(seeds),
        "benefit": _mean(gains) > 0,
    }


def _arms(family: str, removed: str, full: List[bool], ablated: List[bool]) -> Dict[str, Any]:
    kf, ka, n = sum(full), sum(ablated), len(full)
    return {
        "family": family,
        "removed": removed,
        "metric": "correct-decision rate against ground truth",
        "full_rate": kf / n,
        "full_ci95": _wilson(kf, n),
        "ablated_rate": ka / n,
        "ablated_ci95": _wilson(ka, n),
        "tasks": n,
        "benefit": _wilson(kf, n)[0] > _wilson(ka, n)[1],
        "benefit_rule": "full CI lower bound above ablated CI upper bound",
    }


FAMILIES: Dict[str, Callable[[List[int]], Dict[str, Any]]] = {
    "causal_structure": family_confounding,
    "counterfactuals": family_counterfactual,
    "multi_representation": family_navigation,
    "world_model_revision": family_learning,
    "meta_reasoning_voi": family_voi,
    "adaptive_precision": family_precision,
    "planning": family_planning,
}


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--report")
    args = ap.parse_args(argv)
    seeds = list(range(HELD_OUT, HELD_OUT + args.n))
    t0 = time.time()
    results = {
        name: {"capability_relevant": fn(seeds), "negative_control": fn(seeds, control=True)}
        for name, fn in FAMILIES.items()
    }
    try:
        sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        sha = "UNAVAILABLE"
    report = {
        "schema": "toe.ablation_study/v1",
        "source_sha": sha,
        "seeds": {"development": [0, 19], "held_out": [seeds[0], seeds[-1]]},
        "tuning": "none — every TOE threshold is a declared constant",
        "results": results,
        "summary": {
            k: {
                "benefit_when_relevant": bool(v["capability_relevant"].get("benefit")),
                "benefit_in_negative_control": bool(v["negative_control"].get("benefit")),
            }
            for k, v in results.items()
        },
        "scope": (
            "each relevant family is constructed so the capability's precondition holds; "
            "the negative control removes it. The study shows whether a capability changes "
            "outcomes when relevant — not how often such situations occur in practice."
        ),
        "elapsed_s": time.time() - t0,
    }
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
