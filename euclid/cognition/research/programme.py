"""EUCLID v17 scientific evaluation programme.

Protocol (fixed before any results were inspected):

1. For each seed, :func:`~..worlds.families.generate_suite` builds disjoint
   train / development / evaluation / held-out-family / adversarial / analogy
   partitions.
2. Every system learns online on the *train* partition only.
3. Its knowledge is then frozen; every held-out task is solved from the same
   frozen knowledge.  A digest of the knowledge before and after evaluation
   proves nothing was learned from held-out tasks.
4. Self-improvement may use the *development* partition only.
5. Systems are compared on identical tasks and world seeds (paired design);
   the seed is the unit of replication for intervals, and paired bootstrap
   over (seed, task) gives difference intervals.

Hidden truth is read only by this harness for scoring (identification
accuracy, optimal lengths) — never by an agent.
"""
from __future__ import annotations

import json
import statistics
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Sequence

from ...contracts import domain_hash
from ..state import Outcome
from ..worlds.families import FAMILIES, IN_DISTRIBUTION, SuiteTask, generate_suite
from ..worlds.world import WorldExecutor
from ..integrated.agent import SYSTEMS, IntegratedAgent
from ..integrated.context import AgentConfig
from ..integrated.memory import AgentKnowledge
from .stats import (
    brier,
    expected_calibration_error,
    paired_bootstrap,
    reliability_bins,
    t_interval,
    wilson,
)

EVAL_SLICES = ("evaluation", "held-out", "adversarial", "analogy")
INTEGRATION_MECHANISMS = {
    "analogy": "minus-analogy",
    "meta_learning": "minus-meta-learning",
    "learned_primitives": "minus-learned-primitives",
    "representation_restructuring": "minus-representation",
    "mathematical_structure": "minus-phi-lucas-manifold",
    "replanning": "minus-replanning",
}


@dataclass(frozen=True)
class ProgrammeConfig:
    seeds: tuple[int, ...] = (0, 1, 2, 3, 4)
    systems: tuple[str, ...] = tuple(SYSTEMS)
    workers: int = 6
    train_per_family: int = 6
    development_per_family: int = 3
    evaluation_per_family: int = 4
    held_out_per_family: int = 4
    adversarial_per_tag: int = 3
    analogy_pairs: int = 4
    agent: AgentConfig = field(default_factory=AgentConfig)
    #: pre-registered evaluation suites start at 2000 and were never used in
    #: development; development smokes must use a different base.
    suite_base: int = 2000

    def suite(self, seed: int) -> dict[str, list[SuiteTask]]:
        return generate_suite(
            self.suite_base + seed,
            train_per_family=self.train_per_family,
            development_per_family=self.development_per_family,
            evaluation_per_family=self.evaluation_per_family,
            held_out_per_family=self.held_out_per_family,
            adversarial_per_tag=self.adversarial_per_tag,
            analogy_pairs=self.analogy_pairs,
        )


# -- single episode --------------------------------------------------------------------------
def _identification(result: Any, task: SuiteTask) -> float | None:
    posterior = result.context.posterior
    if posterior is None or not task.truth.mechanisms:
        return None
    truth = dict(task.truth.mechanisms)
    if task.truth.shift and result.context.probes_used + result.context.submissions_used >= \
            task.truth.shift[0]:
        truth[task.truth.shift[1]] = task.truth.shift[2]
    correct = sum(1 for op, m in truth.items() if posterior.map_mechanism(op)[0] == m)
    return correct / len(truth)


def run_episode(agent: IntegratedAgent, task: SuiteTask, *, seed: int, system: str,
                phase: str) -> dict[str, Any]:
    world = task.world(seed=seed)
    started = time.perf_counter()
    result = agent.solve(task.spec, WorldExecutor(world), seed=seed)
    wall = time.perf_counter() - started
    ctx = result.context
    state = result.state
    solved = bool(world.solved)
    if solved != (state.outcome is Outcome.SOLVED):
        raise RuntimeError("agent outcome disagrees with the world ledger")
    value = ctx.value
    probe_predictions = []
    if ctx.posterior is not None:
        probe_predictions = [u["predicted_probability"] for u in ctx.posterior.updates]
    restructures = [t.details for t in state.transitions if t.phase == "restructure"]
    analogy_rows = [t.details for t in state.transitions if t.phase == "analogy-refresh"]
    adopted = set()
    for details in analogy_rows:
        for row in details.get("mappings", ()):
            if row.get("status") == "adopted":
                adopted.add(row["analogy_id"])
    rejected_superficial = sum(
        1 for a in state.analogies if a.status.value == "rejected" and a.surface_overlap > 0
    )
    first_failed = bool(ctx.submissions) and not ctx.submissions[0]["goal_met"]
    return {
        "system": system,
        "seed": seed,
        "phase": phase,
        "slice": task.slice,
        "family": task.truth.family,
        "task_id": task.spec.task_id,
        "tags": list(task.truth.tags),
        "objective": task.spec.objective,
        "held_out_family": FAMILIES[task.truth.family].held_out,
        "solved": solved,
        "cost": world.cost,
        "value": value,
        "normalised_cost": world.cost / value,
        "utility": (max(0.0, 1.0 - world.cost / value) if solved else 0.0),
        "probes": world.probes_used,
        "submissions": world.submissions_used,
        "interactions": world.interactions,
        "planning_expansions": ctx.planning_expansions,
        "wall_s": wall,
        "strategy": state.selected_strategy,
        "strategies_tried": [row["selected"] for row in state.strategy_history],
        "representation": ctx.representation,
        "representation_trials": restructures[-1].get("trials", []) if restructures else [],
        "calibration": [[float(p), int(y)] for p, y in ctx.calibration],
        "identification_accuracy": _identification(result, task),
        "probe_predictive_probability": (
            statistics.fmean(probe_predictions) if probe_predictions else None),
        "analogies_adopted": len(adopted),
        "analogies_abandoned": sum(1 for t in state.transitions if t.phase == "abandon-transfer"),
        "superficial_rejected": rejected_superficial,
        "proxy_detected": bool(ctx.audit.detached_proxy),
        "model_repairs": [r.get("resolution") for r in (
            ctx.posterior.rebuilds if ctx.posterior is not None else [])],
        "noise_posterior_exact": (ctx.posterior.model_posterior()[0]
                                  if ctx.posterior is not None else None),
        "skills_used": sorted({s for row in ctx.submissions for s in row.get("skills", ())}),
        "first_submission_failed": first_failed,
        "recovered_after_failure": solved and first_failed,
        "control_decisions": [d["action"] for d in state.control_decisions],
        "optimal_length": task.truth.optimal_length,
        "transitions": len(state.transitions),
    }


def _digest(knowledge: AgentKnowledge) -> str:
    """Everything an episode could write: sealed payload, memory, novelty."""
    memory = knowledge.memory
    return domain_hash("euclid.research.knowledge-digest.v1", {
        "payload": knowledge.to_payload(),
        "memory": sorted(memory.items),
        "deprecations": sorted(memory.deprecations.items()),
        "outcomes": sorted((k, list(v)) for k, v in memory.outcomes.items()),
        "novelty": [list(d) for d in knowledge.novelty.descriptors],
        "skill_occurrences": sorted(repr(k) for k in knowledge.skills.occurrences),
        "skill_corpus": sorted(knowledge.skills.corpus),
    })


def run_system_seed(job: tuple[str, int, ProgrammeConfig]) -> dict[str, Any]:
    """Train one system on one seed, then evaluate it frozen on every slice."""
    system, seed, config = job
    suite = config.suite(seed)
    agent = IntegratedAgent.for_system(system, config=replace(config.agent, seed=seed))
    rows = []
    started = time.perf_counter()
    for index, task in enumerate(suite["train"]):
        rows.append(run_episode(agent, task, seed=seed * 1000 + index, system=system,
                                phase="train"))
    frozen = agent.knowledge.freeze()
    before = _digest(frozen)
    evaluator = IntegratedAgent(knowledge=frozen, config=replace(config.agent, seed=seed),
                                ablations=SYSTEMS[system],
                                reference_v16=system == "v16.4-reference")
    for slice_name in EVAL_SLICES:
        for index, task in enumerate(suite[slice_name]):
            rows.append(run_episode(evaluator, task, seed=seed * 1000 + 500 + index,
                                    system=system, phase="eval"))
    after = _digest(frozen)
    return {
        "system": system,
        "seed": seed,
        "rows": rows,
        "knowledge": frozen.summary(),
        "knowledge_payload": frozen.to_payload() if system == "integrated" else None,
        "leakage_check": {"digest_before_evaluation": before,
                          "digest_after_evaluation": after,
                          "unchanged": before == after},
        "wall_s": time.perf_counter() - started,
    }


def run_fresh(job: tuple[str, int, ProgrammeConfig]) -> dict[str, Any]:
    """An untrained (fresh, frozen) agent on the held-out slices: transfer baseline."""
    system, seed, config = job
    suite = config.suite(seed)
    knowledge = AgentKnowledge().freeze()
    agent = IntegratedAgent(knowledge=knowledge, config=replace(config.agent, seed=seed),
                            ablations=SYSTEMS[system])
    rows = []
    for slice_name in EVAL_SLICES:
        for index, task in enumerate(suite[slice_name]):
            rows.append(run_episode(agent, task, seed=seed * 1000 + 500 + index,
                                    system=f"{system}:untrained", phase="eval"))
    return {"system": f"{system}:untrained", "seed": seed, "rows": rows}


def run_continual(job: tuple[str, int, ProgrammeConfig]) -> dict[str, Any]:
    """Sequential family curriculum; frozen evaluation on every family after each block."""
    system, seed, config = job
    suite = config.suite(seed)
    order = list(IN_DISTRIBUTION)
    agent = IntegratedAgent.for_system(system, config=replace(config.agent, seed=seed))
    by_family = {f: [t for t in suite["evaluation"] if t.truth.family == f] for f in order}

    def evaluate(knowledge: AgentKnowledge) -> dict[str, float]:
        frozen = knowledge.freeze()
        runner = IntegratedAgent(knowledge=frozen, config=replace(config.agent, seed=seed),
                                 ablations=SYSTEMS[system])
        scores = {}
        for family, tasks in by_family.items():
            utilities = [run_episode(runner, t, seed=seed * 1000 + 700 + i, system=system,
                                     phase="continual")["utility"]
                         for i, t in enumerate(tasks)]
            scores[family] = statistics.fmean(utilities) if utilities else 0.0
        return scores

    baseline = evaluate(AgentKnowledge())
    matrix = []
    for block, family in enumerate(order):
        for index, task in enumerate(t for t in suite["train"] if t.truth.family == family):
            run_episode(agent, task, seed=seed * 1000 + 100 * block + index, system=system,
                        phase="continual-train")
        matrix.append(evaluate(agent.knowledge))
    return {"system": system, "seed": seed, "order": order, "baseline": baseline,
            "matrix": matrix}


def run_negative_transfer(job: tuple[str, int, ProgrammeConfig]) -> dict[str, Any]:
    """Train on one family only; evaluate on a structurally different family.

    Compares against an untrained agent on the same tasks: a negative delta is
    measured negative transfer from a mis-matched curriculum.
    """
    system, seed, config = job
    suite = config.suite(seed)
    source, target = "symbolic-rewriting", "causal-circuit"
    agent = IntegratedAgent.for_system(system, config=replace(config.agent, seed=seed))
    for index, task in enumerate(t for t in suite["train"] if t.truth.family == source):
        run_episode(agent, task, seed=seed * 1000 + index, system=system, phase="nt-train")
    tasks = [t for t in suite["evaluation"] + suite["development"] if t.truth.family == target]
    trained = IntegratedAgent(knowledge=agent.knowledge.freeze(), ablations=SYSTEMS[system],
                              config=replace(config.agent, seed=seed))
    fresh = IntegratedAgent(knowledge=AgentKnowledge().freeze(), ablations=SYSTEMS[system],
                            config=replace(config.agent, seed=seed))
    rows = []
    for index, task in enumerate(tasks):
        a = run_episode(trained, task, seed=seed * 1000 + 900 + index, system=system,
                        phase="nt-eval")
        b = run_episode(fresh, task, seed=seed * 1000 + 900 + index, system=system,
                        phase="nt-eval")
        rows.append({"task_id": task.spec.task_id, "trained_utility": a["utility"],
                     "fresh_utility": b["utility"], "trained_probes": a["probes"],
                     "fresh_probes": b["probes"], "trained_solved": a["solved"],
                     "fresh_solved": b["solved"],
                     "trained_identification": a["identification_accuracy"],
                     "fresh_identification": b["identification_accuracy"]})
    return {"system": system, "seed": seed, "source": source, "target": target,
            "kind_prior": agent.knowledge.kind_prior(), "rows": rows}


def run_self_improvement(job: tuple[str, int, ProgrammeConfig, bool]) -> dict[str, Any]:
    from ..integrated.self_improvement import PolicySelfImprovement

    system, seed, config, golden = job
    suite = config.suite(seed)
    agent = IntegratedAgent.for_system(system, config=replace(config.agent, seed=seed))
    for index, task in enumerate(suite["train"]):
        run_episode(agent, task, seed=seed * 1000 + index, system=system, phase="train")
    development = suite["development"]
    evaluations = {"count": 0}

    def evaluate(params: Mapping[str, float]) -> list[tuple[str, float]]:
        evaluations["count"] += 1
        sandbox = agent.knowledge.freeze()
        sandbox.params = dict(params)
        runner = IntegratedAgent(knowledge=sandbox, ablations=SYSTEMS[system],
                                 config=replace(config.agent, seed=seed))
        return [(task.truth.family,
                 run_episode(runner, task, seed=seed * 1000 + 800 + i, system=system,
                             phase="dev")["utility"])
                for i, task in enumerate(development)]

    improver = PolicySelfImprovement(evaluate, golden=golden, seed=seed)
    accepted = improver.run(dict(agent.knowledge.params))
    return {"system": system, "seed": seed, "golden": golden,
            "initial": dict(agent.knowledge.params), "accepted": accepted,
            "ledger": [r.to_json() for r in improver.ledger],
            "sandbox_runs": evaluations["count"]}


# -- φ controlled experiments (no agent) ------------------------------------------------------
def phi_experiments(seed: int = 2026) -> dict[str, Any]:
    import random

    from ..integrated.phi_mechanisms import (
        SCHEDULES,
        difference_bisection,
        fibonacci_search,
        golden_weyl_points,
        iterative_deepening,
        ternary_search,
    )
    from ..worlds.families import _response_curve

    rng = random.Random(seed)
    methods = {"fibonacci": fibonacci_search, "difference-bisection": difference_bisection,
               "ternary": ternary_search}
    curves = []
    for _ in range(600):
        size = rng.randint(20, 300)
        curve = _response_curve(rng, size, False)
        curves.append(curve)
    evaluations = {name: [] for name in methods}
    for curve in curves:
        for name, method in methods.items():
            trace = method(curve.__getitem__, len(curve), 10 ** 6)
            evaluations[name].append(trace.evaluations)
    budgets = {}
    for budget in range(6, 15):
        row = {}
        for name, method in methods.items():
            hits = 0
            for curve in curves:
                best = max(range(len(curve)), key=curve.__getitem__)
                hits += method(curve.__getitem__, len(curve), budget).best == best
            row[name] = wilson(hits, len(curves))
        budgets[str(budget)] = row

    def van_der_corput(n: int) -> float:
        result, denominator = 0.0, 1.0
        while n:
            n, remainder = divmod(n, 2)
            denominator *= 2
            result += remainder / denominator
        return result

    coverage = {"golden-weyl": [], "van-der-corput": [], "uniform-random": []}
    size = 10_000
    for count in (5, 8, 13, 21, 34, 55):
        sequences = {
            "golden-weyl": golden_weyl_points(count, size),
            "van-der-corput": [int(van_der_corput(i + 1) * size) for i in range(count)],
            "uniform-random": [rng.randrange(size) for _ in range(count)],
        }
        for name, points in sequences.items():
            ordered = sorted(set(points))
            gaps = [b - a for a, b in zip(ordered, ordered[1:])] + [
                ordered[0] + size - ordered[-1]]
            coverage[name].append({"points": count, "max_gap_fraction": max(gaps) / size})

    schedules = {name: [] for name in SCHEDULES}
    suite = generate_suite(seed, train_per_family=4, development_per_family=0,
                           evaluation_per_family=0, held_out_per_family=4,
                           adversarial_per_tag=0, analogy_pairs=0)
    models = [t for t in suite["train"] + suite["held-out"] if t.spec.objective == "assign"]
    for task in models:
        limit = task.spec.max_program_length
        for name, schedule in SCHEDULES.items():
            outcome = iterative_deepening(task.truth.mechanisms, task.spec.operators,
                                          task.spec.initial_state, task.spec.goal,
                                          task.spec.domains, schedule=schedule(limit),
                                          node_budget=200_000)
            schedules[name].append({"task": task.spec.task_id, "expanded": outcome["expanded"],
                                    "length": outcome["length"],
                                    "optimal": task.truth.optimal_length})
    schedule_summary = {}
    for name, rows in schedules.items():
        solved = [r for r in rows if r["length"] is not None]
        schedule_summary[name] = {
            "solved": len(solved), "tasks": len(rows),
            "mean_expansions": statistics.fmean(r["expanded"] for r in rows),
            "mean_excess_length": statistics.fmean(r["length"] - r["optimal"] for r in solved)
            if solved else None,
        }
    return {
        "unimodal_search": {
            "curves": len(curves),
            "mean_evaluations": {k: t_interval(v) for k, v in evaluations.items()},
            "success_by_budget": budgets,
            "evidence_class": "known-theorem-operationalised (Kiefer 1953)",
        },
        "anytime_coverage": {"max_gap_fraction": coverage,
                             "evidence_class": "exploratory"},
        "iterative_deepening_schedules": {"summary": schedule_summary,
                                          "evidence_class": "exploratory"},
    }


# -- aggregation --------------------------------------------------------------------------------
def _per_seed(rows: Sequence[Mapping[str, Any]], metric: str) -> dict[int, float]:
    by_seed: dict[int, list[float]] = {}
    for row in rows:
        value = row.get(metric)
        if value is None:
            continue
        by_seed.setdefault(row["seed"], []).append(float(value))
    return {seed: statistics.fmean(v) for seed, v in by_seed.items() if v}


def summarise(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    metrics = ("solved", "utility", "normalised_cost", "probes", "submissions",
               "interactions", "planning_expansions", "wall_s", "identification_accuracy",
               "probe_predictive_probability")
    out: dict[str, Any] = {}
    for metric in metrics:
        out[metric] = t_interval(list(_per_seed(rows, metric).values()))
    pairs = [(p, y) for row in rows for p, y in row["calibration"]]
    out["calibration"] = {"submissions": len(pairs), "brier": brier(pairs),
                          "ece": expected_calibration_error(pairs)}
    out["tasks"] = len(rows)
    return out


def paired(rows_a: Sequence[Mapping[str, Any]], rows_b: Sequence[Mapping[str, Any]],
           metric: str, *, seed: int = 0) -> dict[str, Any]:
    index = {(r["seed"], r["task_id"]): r for r in rows_b}
    a, b = [], []
    for row in rows_a:
        other = index.get((row["seed"], row["task_id"]))
        if other is None or row.get(metric) is None or other.get(metric) is None:
            continue
        a.append(float(row[metric]))
        b.append(float(other[metric]))
    return paired_bootstrap(a, b, seed=seed)


def run_programme(config: ProgrammeConfig, *, progress=print) -> dict[str, Any]:
    started = time.time()
    jobs = [(system, seed, config) for seed in config.seeds for system in config.systems]
    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=config.workers) as pool:
        for result in pool.map(run_system_seed, jobs):
            results.append(result)
            progress(f"[main] {result['system']} seed {result['seed']} "
                     f"done in {result['wall_s']:.0f}s")
        fresh = list(pool.map(run_fresh, [("integrated", s, config) for s in config.seeds]))
        progress("[transfer] untrained baselines done")
        continual = list(pool.map(run_continual, [(name, s, config) for s in config.seeds
                                                  for name in ("integrated", "sysid-plan-pipeline")]))
        progress("[continual] done")
        negative = list(pool.map(run_negative_transfer,
                                 [("integrated", s, config) for s in config.seeds]))
        progress("[negative-transfer] done")
        improvement = list(pool.map(run_self_improvement,
                                    [("integrated", s, config, golden)
                                     for s in config.seeds[:3] for golden in (True, False)]))
        progress("[self-improvement] done")
    phi = phi_experiments()
    progress("[phi] done")
    report = analyse(config, results, fresh, continual, negative, improvement, phi)
    report["wall_clock_s"] = time.time() - started
    return report


def analyse(config: ProgrammeConfig, results, fresh, continual, negative, improvement,
            phi) -> dict[str, Any]:
    rows = [row for result in results for row in result["rows"]]
    eval_rows = [r for r in rows if r["phase"] == "eval"]
    by_system = {s: [r for r in eval_rows if r["system"] == s] for s in config.systems}
    systems = {}
    for system, system_rows in by_system.items():
        systems[system] = {
            "all": summarise(system_rows),
            "slices": {name: summarise([r for r in system_rows if r["slice"].split(":")[0]
                                        == name or r["slice"] == name])
                       for name in EVAL_SLICES},
        }
    integrated = by_system.get("integrated", [])
    comparisons = {}
    for system, system_rows in by_system.items():
        if system == "integrated":
            continue
        comparisons[system] = {
            "utility": paired(integrated, system_rows, "utility"),
            "solved": paired(integrated, system_rows, "solved"),
            "by_slice": {
                name: paired([r for r in integrated if r["slice"].startswith(name)],
                             [r for r in system_rows if r["slice"].startswith(name)],
                             "utility")
                for name in EVAL_SLICES
            },
        }
    leakage = [{"system": r["system"], "seed": r["seed"], **r["leakage_check"]}
               for r in results]
    report = {
        "schema": "euclid.v17-research-report/1",
        "protocol": {
            "seeds": list(config.seeds), "systems": list(config.systems),
            "suite_base": config.suite_base,
            "agent_config": config.agent.to_json(),
            "suite": {k: getattr(config, k) for k in (
                "train_per_family", "development_per_family", "evaluation_per_family",
                "held_out_per_family", "adversarial_per_tag", "analogy_pairs")},
            "evaluation": "frozen knowledge; paired tasks and world seeds",
        },
        "systems": systems,
        "paired_vs_integrated": comparisons,
        "leakage_checks": leakage,
        "leakage_free": all(row["unchanged"] for row in leakage),
        "transfer": analyse_transfer(integrated, [r for f in fresh for r in f["rows"]]),
        "continual": analyse_continual(continual),
        "negative_transfer": analyse_negative(negative, results),
        "adversarial": analyse_adversarial(eval_rows),
        "calibration": analyse_calibration(by_system),
        "representation": analyse_representation(integrated),
        "skills": analyse_skills(results),
        "self_improvement": improvement,
        "phi": phi,
        "synergy": analyse_synergy(by_system),
        "release_gate": release_gate(by_system),
        "recovery": {
            system: sum(1 for r in system_rows if r["recovered_after_failure"])
            for system, system_rows in by_system.items()
        },
        "skill_counts": {
            "promoted_mean": statistics.fmean(
                [r["knowledge"]["skills"]["by_status"].get("promoted", 0)
                 for r in results if r["system"] == "integrated"] or [0]),
            "rejected_mean": statistics.fmean(
                [r["knowledge"]["skills"]["by_status"].get("rejected", 0)
                 for r in results if r["system"] == "integrated"] or [0]),
        },
        "rows": rows,
    }
    return report


def analyse_transfer(trained: Sequence[Mapping[str, Any]], fresh: Sequence[Mapping[str, Any]]):
    out = {}
    for name in ("held-out", "analogy", "evaluation"):
        a = [r for r in trained if r["slice"].startswith(name)]
        b = [{**r, "system": "integrated"} for r in fresh if r["slice"].startswith(name)]
        out[name] = {"utility": paired(a, b, "utility"), "solved": paired(a, b, "solved"),
                     "probes": paired(a, b, "probes")}
    kinds = sorted({r["slice"] for r in trained if r["slice"].startswith("analogy")})
    out["analogy_kinds"] = {
        kind: {"utility": paired([r for r in trained if r["slice"] == kind],
                                 [r for r in fresh if r["slice"] == kind], "utility"),
               "probes": paired([r for r in trained if r["slice"] == kind],
                                [r for r in fresh if r["slice"] == kind], "probes"),
               "adopted_rate": statistics.fmean(
                   [r["analogies_adopted"] > 0 for r in trained if r["slice"] == kind] or [0]),
               "abandoned_rate": statistics.fmean(
                   [r["analogies_abandoned"] > 0 for r in trained if r["slice"] == kind] or [0])}
        for kind in kinds
    }
    held = [r for r in trained if r["slice"] == "held-out"]
    out["held_out_families"] = {
        family: {"utility": paired([r for r in held if r["family"] == family],
                                   [r for r in fresh if r["slice"] == "held-out"
                                    and r["family"] == family], "utility")}
        for family in sorted({r["family"] for r in held})
    }
    return out


def analyse_continual(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out = {}
    for system in sorted({r["system"] for r in results}):
        runs = [r for r in results if r["system"] == system]
        order = runs[0]["order"]
        t = len(order)
        bwt, fwt, forgetting, final = [], [], [], []
        for run in runs:
            matrix = run["matrix"]
            bwt.append(statistics.fmean(matrix[-1][order[j]] - matrix[j][order[j]]
                                        for j in range(t - 1)))
            fwt.append(statistics.fmean(matrix[j - 1][order[j]] - run["baseline"][order[j]]
                                        for j in range(1, t)))
            forgetting.append(statistics.fmean(
                max(matrix[k][order[j]] for k in range(j, t - 1)) - matrix[-1][order[j]]
                for j in range(t - 1)))
            final.append(statistics.fmean(matrix[-1].values()))
        mean_matrix = [{family: statistics.fmean(run["matrix"][i][family] for run in runs)
                        for family in order} for i in range(t)]
        out[system] = {"order": order, "mean_retention_matrix": mean_matrix,
                       "backward_transfer": t_interval(bwt), "forward_transfer": t_interval(fwt),
                       "forgetting": t_interval(forgetting),
                       "final_average_utility": t_interval(final)}
    return out


def analyse_negative(results: Sequence[Mapping[str, Any]], main: Sequence[Mapping[str, Any]]):
    rows = [row for r in results for row in r["rows"]]
    ledger_entries = []
    for result in main:
        if result["system"] != "integrated":
            continue
        ledger = result["knowledge"]["transfer_ledger"]
        ledger_entries.extend(ledger)
        negative_strategies = result["knowledge"]["strategies"]["negative_transfer"]
        ledger_entries.extend({"kind": "strategy-recognised", **e} for e in negative_strategies)
    return {
        "curriculum": {"source": "symbolic-rewriting", "target": "causal-circuit"},
        "utility": paired_bootstrap([r["trained_utility"] for r in rows],
                                    [r["fresh_utility"] for r in rows]),
        "probes": paired_bootstrap([r["trained_probes"] for r in rows],
                                   [r["fresh_probes"] for r in rows]),
        "identification": paired_bootstrap(
            [r["trained_identification"] or 0 for r in rows],
            [r["fresh_identification"] or 0 for r in rows]),
        "learned_kind_prior": [r["kind_prior"] for r in results],
        "ledger": {
            "analogy_positive": sum(1 for e in ledger_entries
                                    if e.get("kind") == "analogy" and e["outcome"] == "positive"),
            "analogy_negative": sum(1 for e in ledger_entries
                                    if e.get("kind") == "analogy" and e["outcome"] == "negative"),
            "strategy_negative_recognised": [e for e in ledger_entries
                                             if e.get("kind") == "strategy-recognised"],
        },
    }


def analyse_adversarial(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    adversarial = [r for r in rows if r["slice"].startswith("adversarial")]
    for tag in sorted({r["slice"].split(":", 1)[1] for r in adversarial}):
        subset = [r for r in adversarial if r["slice"] == f"adversarial:{tag}"]
        out[tag] = {}
        for system in sorted({r["system"] for r in subset}):
            mine = [r for r in subset if r["system"] == system]
            entry = {"success": wilson(sum(r["solved"] for r in mine), len(mine))}
            if tag == "proxy-reward":
                entry["proxy_detected_rate"] = statistics.fmean(r["proxy_detected"] for r in mine)
            if tag in ("mechanism-shift", "out-of-grammar"):
                entry["repairs"] = sum(len(r["model_repairs"]) for r in mine)
                entry["resolved_repairs"] = sum(
                    sum(1 for m in r["model_repairs"] if m != "unresolved") for r in mine)
            if tag == "noisy-observation":
                values = [r["noise_posterior_exact"] for r in mine
                          if r["noise_posterior_exact"] is not None]
                entry["mean_posterior_exact_readings"] = (statistics.fmean(values)
                                                          if values else None)
            if tag == "confounded-footprint":
                values = [r["identification_accuracy"] for r in mine
                          if r["identification_accuracy"] is not None]
                entry["identification_accuracy"] = statistics.fmean(values) if values else None
            out[tag][system] = entry
    analogy = [r for r in rows if r["slice"].startswith("analogy")]
    out["superficial-analogy"] = {
        system: {"success": wilson(sum(r["solved"] for r in mine), len(mine)),
                 "superficial_rejections": sum(r["superficial_rejected"] for r in mine),
                 "wrongly_adopted": sum(r["analogies_adopted"] > 0 for r in mine)}
        for system in sorted({r["system"] for r in analogy})
        for mine in [[r for r in analogy if r["system"] == system
                      and r["slice"] == "analogy:superficial"]]
    }
    out["memorisation-trap"] = {
        system: {"success": wilson(sum(r["solved"] for r in mine), len(mine))}
        for system in sorted({r["system"] for r in analogy})
        for mine in [[r for r in analogy if r["system"] == system
                      and r["slice"] == "analogy:memorisation-trap"]]
    }
    return out


def analyse_calibration(by_system: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    out = {}
    for system, rows in by_system.items():
        pairs = [(p, y) for row in rows for p, y in row["calibration"]]
        out[system] = {
            "submissions": len(pairs),
            "brier": brier(pairs),
            "ece": expected_calibration_error(pairs),
            "reliability": reliability_bins(pairs),
            "status": "measured" if pairs else "unavailable (no predictive model)",
        }
    return out


def analyse_representation(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    examples = []
    for row in rows:
        counts[row["representation"]] = counts.get(row["representation"], 0) + 1
        if row["representation"] != "literal" and row["representation_trials"] and \
                len(examples) < 8:
            examples.append({"task_id": row["task_id"], "family": row["family"],
                             "selected": row["representation"],
                             "trials": row["representation_trials"],
                             "solved": row["solved"]})
    return {"adopted_counts": counts, "examples": examples}


def analyse_skills(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out = {}
    for result in results:
        if result["system"] != "integrated":
            continue
        out[str(result["seed"])] = result["knowledge"]["skills"]
    usage = [r for result in results if result["system"] == "integrated"
             for r in result["rows"] if r["phase"] == "eval" and r["skills_used"]]
    return {"libraries": out,
            "eval_episodes_using_skills": len(usage),
            "eval_successes_using_skills": sum(r["solved"] for r in usage),
            "held_out_family_uses": sum(1 for r in usage if r["held_out_family"])}


def analyse_synergy(by_system: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    """Is the integration gain more than the sum of single-mechanism contributions?"""
    def mean_utility(name: str) -> float | None:
        rows = by_system.get(name)
        if not rows:
            return None
        return statistics.fmean(r["utility"] for r in rows)

    full = mean_utility("integrated")
    pipeline = mean_utility("sysid-plan-pipeline")
    if full is None or pipeline is None:
        return {"status": "unavailable"}
    contributions = {}
    for mechanism, system in INTEGRATION_MECHANISMS.items():
        value = mean_utility(system)
        if value is not None:
            contributions[mechanism] = full - value
    total = full - pipeline
    single_sum = sum(contributions.values())
    return {
        "integrated_utility": full,
        "pipeline_utility": pipeline,
        "integration_gain": total,
        "single_mechanism_contributions": contributions,
        "sum_of_single_contributions": single_sum,
        "synergy": total - single_sum,
        "interpretation": (
            "superadditive: removing everything costs more than the sum of single removals"
            if total - single_sum > 0 else
            "not superadditive: single removals account for at least the total gain"),
    }


def release_gate(by_system: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    integrated = by_system.get("integrated", [])
    reference = by_system.get("v16.4-reference", [])
    utility = paired(integrated, reference, "utility")
    solved = paired(integrated, reference, "solved")
    held = paired([r for r in integrated if r["slice"] == "held-out"],
                  [r for r in reference if r["slice"] == "held-out"], "solved")
    passed = bool(solved["low95"] is not None and solved["low95"] > 0
                  and held["low95"] is not None and held["low95"] > 0)
    return {
        "criterion": "integrated success exceeds v16.4 on all held-out slices and on "
                     "held-out families, 95% paired bootstrap interval excluding zero",
        "solved_difference": solved,
        "utility_difference": utility,
        "held_out_family_solved_difference": held,
        "passed": passed,
    }


def write_report(report: Mapping[str, Any], path: str) -> None:
    from pathlib import Path

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=1, sort_keys=True, default=str),
                      encoding="utf-8")


__all__ = [
    "EVAL_SLICES",
    "ProgrammeConfig",
    "analyse",
    "phi_experiments",
    "run_continual",
    "run_episode",
    "run_fresh",
    "run_negative_transfer",
    "run_programme",
    "run_self_improvement",
    "run_system_seed",
    "summarise",
    "write_report",
]
