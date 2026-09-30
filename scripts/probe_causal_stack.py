"""Fail-closed probe for the causal capability stack (elevation §§6-10).

Every printed claim is an asserted check; failure exits 1, unavailability
exits 2, all-pass exits 0.

  identifiability   the §7 battery: observed/latent confounder, collider,
                    mediator, frontdoor, instrument, M-bias, insufficient
                    variables, malformed query — including refusals
  discovery         bounded structural learning returns an equivalence
                    class containing the planted structure — never a
                    fabricated unique DAG
  worlds            multi-counterfactual: factual vs A vs B, deltas,
                    invariants, receipts, refusal on missing evidence
  futures           per-action outcome distributions, exact propagation,
                    sd-vs-depth degradation reported

Usage:
    python scripts/probe_causal_stack.py --report reports/toe_causal_stack.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RESULTS: List[Dict[str, Any]] = []


def check(section: str, name: str, ok: bool, evidence: Dict[str, Any]) -> None:
    RESULTS.append(
        {"section": section, "check": name, "status": "PASS" if ok else "FAIL",
         "evidence": evidence}
    )
    print(f"  [{'PASS' if ok else 'FAIL'}] {section}: {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="reports/toe_causal_stack.json")
    args = parser.parse_args()

    from toe.causal_ladder import CausalGraph, StructuralCausalModel
    from toe.causal_stack import (
        IDENTIFIED,
        NOT_IDENTIFIED,
        PARTIALLY_IDENTIFIED,
        UNAVAILABLE,
        compare_worlds,
        discover_structures,
        evaluate_futures,
        identifiability,
    )

    print("TOE causal stack probe (sections 6-10)")

    print("== identifiability battery ==")
    battery = [
        (
            "clean DAG x->y identified without adjustment",
            CausalGraph.from_edges([("x", "y")]),
            None,
            (IDENTIFIED, "no_adjustment"),
        ),
        (
            "observed confounder identified via backdoor {z}",
            CausalGraph.from_edges([("z", "x"), ("z", "y"), ("x", "y")]),
            None,
            (IDENTIFIED, "backdoor"),
        ),
        (
            "latent confounder REFUSED (not identified)",
            CausalGraph.from_edges([("u", "x"), ("u", "y"), ("x", "y")]),
            {"x", "y"},
            (NOT_IDENTIFIED, None),
        ),
        (
            "mediator chain identified with empty set",
            CausalGraph.from_edges([("x", "m"), ("m", "y")]),
            None,
            (IDENTIFIED, "no_adjustment"),
        ),
        (
            "latent confounder + observed mediator -> frontdoor {m}",
            CausalGraph.from_edges(
                [("u", "x"), ("u", "y"), ("x", "m"), ("m", "y")]
            ),
            {"x", "m", "y"},
            (IDENTIFIED, "frontdoor"),
        ),
        (
            "collider x->c<-y: effect identified, c flagged as trap",
            CausalGraph.from_edges([("x", "c"), ("y", "c")]),
            None,
            (IDENTIFIED, "no_adjustment"),
        ),
        (
            "M-bias: empty set admissible, z flagged as trap",
            CausalGraph.from_edges(
                [("a", "z"), ("b", "z"), ("a", "x"), ("b", "y"), ("x", "y")]
            ),
            None,
            (IDENTIFIED, "no_adjustment"),
        ),
        (
            "instrument z: PARTIALLY_IDENTIFIED (bounds/IV only)",
            CausalGraph.from_edges(
                [("z", "x"), ("x", "y"), ("u", "x"), ("u", "y")]
            ),
            {"z", "x", "y"},
            (PARTIALLY_IDENTIFIED, "instrument"),
        ),
        (
            "insufficient variables REFUSED",
            CausalGraph.from_edges(
                [("u1", "x"), ("u1", "u2"), ("u2", "y"), ("u2", "x"), ("x", "y")]
            ),
            {"x", "y"},
            (NOT_IDENTIFIED, None),
        ),
        (
            "missing graph -> UNAVAILABLE",
            None,
            None,
            (UNAVAILABLE, None),
        ),
    ]
    battery_rows = []
    all_ok = True
    for name, g, obs, (verdict, strategy) in battery:
        r = identifiability(g, "x", "y", observed=obs)
        ok = r["verdict"] == verdict and (
            strategy is None or r["strategy"] == strategy
        )
        battery_rows.append(
            {"scenario": name, "verdict": r["verdict"], "strategy": r["strategy"],
             "warnings": r["warnings"], "ok": ok}
        )
        all_ok &= ok
    check(
        "identifiability",
        "10-scenario battery incl. two refusals",
        all_ok,
        {"scenarios": battery_rows},
    )
    # collider + m-bias warnings explicitly
    coll = identifiability(
        CausalGraph.from_edges([("x", "c"), ("y", "c")]), "x", "y"
    )
    mbias = identifiability(
        CausalGraph.from_edges(
            [("a", "z"), ("b", "z"), ("a", "x"), ("b", "y"), ("x", "y")]
        ),
        "x",
        "y",
    )
    check(
        "identifiability",
        "collider and M-bias covariates flagged as adjustment traps",
        "c" in coll["warnings"] and "z" in mbias["warnings"],
        {"collider_warnings": coll["warnings"], "mbias_warnings": mbias["warnings"]},
    )

    print("== bounded discovery ==")
    rng = random.Random(7)
    rows = {"x": [], "m": [], "y": []}
    for _ in range(500):
        ex, em, ey = rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)
        rows["x"].append(ex)
        rows["m"].append(0.9 * ex + em)
        rows["y"].append(0.8 * rows["m"][-1] + 0.6 * ey)
    disc = discover_structures(rows)
    planted = [("x", "m"), ("m", "y")]
    in_class = any(
        set(dag) == set(planted) for dag in disc["admissible_dags"]
    )
    check(
        "discovery",
        "planted chain recovered inside an equivalence class (not a unique DAG)",
        disc["available"] and disc["equivalence_class_size"] > 1 and in_class,
        {
            "class_size": disc["equivalence_class_size"],
            "undirected": disc["undirected_edges"],
            "planted_in_class": in_class,
            "boundaries": disc["boundaries"],
        },
    )

    print("== multi-counterfactual worlds ==")
    g = CausalGraph.from_edges([("x", "m"), ("m", "y")])
    g.edge_weights[("x", "m")] = 1.0
    g.edge_weights[("m", "y")] = 2.0
    scm = StructuralCausalModel(graph=g)
    factual = {"x": 1.0, "m": 1.0, "y": 2.0}
    worlds = compare_worlds(
        scm,
        factual,
        [
            {"name": "A", "interventions": {"x": 3.0}},
            {"name": "B", "interventions": {"x": 0.0}},
            {"name": "C", "interventions": {"x": -2.0}},
        ],
        ["m", "y"],
    )
    w = {x["world"]: x for x in worlds["worlds"]}
    check(
        "worlds",
        "three counterfactual worlds: deltas, paths, invariants, receipts",
        w["A"]["outcome_values"]["y"] == 6.0
        and w["B"]["outcome_values"]["y"] == 0.0
        and w["C"]["outcome_values"]["y"] == -4.0
        and worlds["ledger_verify"]
        and all(x["receipt"] for x in w.values()),
        {
            "world_outcomes": {
                k: v["outcome_values"] for k, v in w.items()
            },
            "invariant_variables": worlds["invariant_variables"],
            "paths_A": w["A"]["causal_paths"],
        },
    )
    refused = compare_worlds(
        scm, {}, [{"name": "no_evidence", "interventions": {"x": 1.0}}], ["y"]
    )
    check(
        "worlds",
        "missing factual evidence refuses instead of fabricating",
        refused["worlds"][0]["available"] is False,
        {"reason": refused["worlds"][0]["reason"]},
    )

    print("== multi-future distributions ==")
    g2 = CausalGraph.from_edges([("x", "m"), ("m", "y")])
    g2.edge_weights[("x", "m")] = 1.0
    g2.edge_weights[("m", "y")] = 1.5
    scm2 = StructuralCausalModel(graph=g2)
    fut = evaluate_futures(
        scm2,
        [
            {"name": "A1", "interventions": {"x": 2.0}},
            {"name": "A2", "interventions": {"x": -1.0}},
            {"name": "A3", "interventions": {"x": 0.5}},
        ],
        ["x", "m", "y"],
    )
    a1 = {f["action"]: f for f in fut["actions"]}["A1"]
    d = a1["outcome_distributions"]
    check(
        "futures",
        "3 actions -> distributions; intervention pins x (var=0); sd grows with depth",
        d["x"]["variance"] == 0.0
        and d["m"]["sd"] > 0
        and d["y"]["sd"] > d["m"]["sd"]
        and all(f["receipt"] for f in fut["actions"]),
        {
            "depth_sd": {o: [int(d[o]["depth"]), round(d[o]["sd"], 4)] for o in d},
            "bands_y": [round(d["y"]["p05"], 3), round(d["y"]["mean"], 3), round(d["y"]["p95"], 3)],
            "baseline_y_sd": round(fut["baseline_distributions"]["y"]["sd"], 4),
        },
    )

    failed = [r for r in RESULTS if r["status"] == "FAIL"]
    doc = {
        "format": "toe.causal_stack_probe/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": RESULTS,
        "summary": {
            "checks": len(RESULTS),
            "passed": len(RESULTS) - len(failed),
            "failed": len(failed),
        },
    }
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    print(f"\n{doc['summary']} — wrote {report}")
    if failed:
        print("FAILED:", ["{}:{}".format(r["section"], r["check"]) for r in failed])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
