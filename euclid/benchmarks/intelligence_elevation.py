"""Held-out comparative benchmark for the intelligence-elevation work.

Conditions (identical tasks, budgets matched as closely as each engine
allows; actual evaluation counts are always reported):

  A  random-baseline         seeded uniform random operators
  B  v16-evolutionary        merged v16 evolutionary engine (surrogate greedy)
  C  v16-mcts                merged v16 MCTS (root-level PUCT)
  D  elevated-loop           deep MCTS + learned world-model priors +
                             cross-task repository transfer
  E1 elevated-no-world-model (ablation)
  E2 elevated-no-transfer    (ablation: cold repository)
  E3 elevated-shallow        (ablation: max_depth=1)

D and E* train on the train split first (that is what memory/transfer mean);
A/B/C run cold on every task.  Improvement is the sandbox-gated
multi-objective fitness delta — functional tests dominate; phi is never the
objective.  Results report mean +/- sample std across seeds.  No superiority
is asserted by construction; the numbers stand as measured.
"""
from __future__ import annotations

import json
import math
import random
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from euclid.core.phi_metric import PhiResonanceCalculator
from euclid.core.primitives import ASTPrimitives
from euclid.search.deep_mcts import DeepMCTSEngine, SearchBudget
from euclid.search.evolutionary_search import EvolutionarySearchEngine
from euclid.search.mcts_search import MCTSSearchEngine
from euclid.transfer.persistent_repository import PersistentPrimitiveRepository
from euclid.validation.process_sandbox import IsolatedProcessEvaluator
from euclid.cognition.program_domain import ProgramWorldModel, program_signature

TASKS: tuple[dict[str, str], ...] = (
    {
        "name": "train_list_builder",
        "split": "train",
        "code": "def build_pairs(values):\n    pairs = []\n    for value in values:\n        pairs.append((value, value))\n    return pairs\n",
        "test": "assert build_pairs([1, 2]) == [(1, 1), (2, 2)]",
    },
    {
        "name": "train_accumulator",
        "split": "train",
        "code": "def total_price(items):\n    total = 0\n    for item in items:\n        total = total + item\n    return total\n",
        "test": "assert total_price([1, 2, 3]) == 6",
    },
    {
        "name": "heldout_collector",
        "split": "held-out",
        "code": "def collect_names(rows):\n    names = []\n    for row in rows:\n        names.append(row)\n    return names\n",
        "test": "assert collect_names(['a']) == ['a']",
    },
    {
        "name": "heldout_nested_guard",
        "split": "held-out",
        "code": "def classify(x):\n    if x > 0:\n        if x < 10:\n            return 'small'\n    return 'other'\n",
        "test": "assert classify(5) == 'small'\nassert classify(50) == 'other'",
    },
)

EVAL_BUDGET = 8
SEEDS = (3, 17, 29)


def _fitness_delta(calculator: PhiResonanceCalculator, before: str, after: str) -> float:
    nodes = int(calculator.extract_features(before).get("node_count", 50))
    base = calculator.compute_multi_objective_fitness(before, initial_node_count=nodes)
    final = calculator.compute_multi_objective_fitness(after, initial_node_count=nodes)
    return round(final - base, 6)


def _run_random(task: Mapping[str, str], seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    evaluator = IsolatedProcessEvaluator(timeout_sec=2.0)
    calculator = PhiResonanceCalculator()
    operators = ASTPrimitives.get_all_operators()
    code = task["code"]
    best = code
    evals = 0
    for _ in range(EVAL_BUDGET):
        name, func = operators[rng.randrange(len(operators))]
        candidate, _ = func(best, seed + evals)
        evals += 1
        p_v, c_v, t_v, _ = evaluator.evaluate_validity(candidate, None, task["test"])
        if p_v and c_v and t_v:
            if _fitness_delta(calculator, task["code"], candidate) > _fitness_delta(
                calculator, task["code"], best
            ):
                best = candidate
    return {"improvement": _fitness_delta(calculator, task["code"], best),
            "evals": evals}


def _run_v16_evolutionary(task: Mapping[str, str], seed: int) -> dict[str, Any]:
    engine = EvolutionarySearchEngine(seed=seed)
    result = engine.run_optimization(
        task["name"], task["code"], max_generations=max(1, EVAL_BUDGET // 10),
        external_test_code=task["test"],
    )
    return {"improvement": result["total_delta_phi"],
            "evals": result["total_evals_attempted"]}


def _run_v16_mcts(task: Mapping[str, str], seed: int) -> dict[str, Any]:
    engine = MCTSSearchEngine(seed=seed)
    result = engine.run_mcts_search(
        task["name"], task["code"], max_generations=2,
        num_simulations_per_gen=max(1, EVAL_BUDGET // 2),
        external_test_code=task["test"],
    )
    return {"improvement": result["total_delta_phi"],
            "evals": result["total_evals_attempted"]}


def _run_elevated(
    task: Mapping[str, str],
    seed: int,
    *,
    world_model: Optional[ProgramWorldModel],
    repository: Optional[PersistentPrimitiveRepository],
    max_depth: int = 4,
) -> dict[str, Any]:
    engine = DeepMCTSEngine(
        repository=repository, seed=seed, world_model=world_model,
    )
    result = engine.search(
        task["name"], task["code"],
        budget=SearchBudget(max_evaluations=EVAL_BUDGET, max_depth=max_depth,
                            max_wall_seconds=20.0),
        signature=program_signature(task["code"]),
        external_test_code=task["test"],
    )
    return {"improvement": result["measured_improvement"],
            "evals": result["evaluations_used"],
            "max_depth": result["max_depth_reached"],
            "transpositions": result["transposition_hits"]}


def _stats(values: Sequence[float]) -> dict[str, float]:
    mean = sum(values) / len(values) if values else 0.0
    if len(values) > 1:
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        std = math.sqrt(variance)
    else:
        std = 0.0
    return {"mean": round(mean, 6), "std": round(std, 6), "n": len(values)}


def run_benchmark(
    *,
    seeds: Sequence[int] = SEEDS,
    smoke: bool = False,
) -> dict[str, Any]:
    conditions = ("A-random", "B-v16-evolutionary", "C-v16-mcts",
                  "D-elevated", "E1-no-world-model", "E2-no-transfer",
                  "E3-shallow")
    if smoke:
        conditions = ("A-random", "C-v16-mcts", "D-elevated")
        seeds = seeds[:1]

    tasks = TASKS[:2] if smoke else TASKS
    started = time.monotonic()
    runs: list[dict[str, Any]] = []

    for seed in seeds:
        # Shared knowledge accumulated on the train split (D / E1 / E3 only).
        import tempfile as _tempfile

        _repo_dir = _tempfile.mkdtemp(prefix="euclid-bench-repo-")
        shared_repository = PersistentPrimitiveRepository(
            storage_path=str(Path(_repo_dir) / "repo.json")
        )
        world_model = ProgramWorldModel()
        for task in tasks:
            if task["split"] != "train":
                continue
            trained = _run_elevated(task, seed, world_model=world_model,
                                    repository=shared_repository)
            runs.append({"condition": "D-train", "task": task["name"], "seed": seed,
                         **trained})

        for task in tasks:
            signature = program_signature(task["code"])
            for condition in conditions:
                if condition == "A-random":
                    outcome = _run_random(task, seed)
                elif condition == "B-v16-evolutionary":
                    outcome = _run_v16_evolutionary(task, seed)
                elif condition == "C-v16-mcts":
                    outcome = _run_v16_mcts(task, seed)
                elif condition == "D-elevated":
                    outcome = _run_elevated(task, seed, world_model=world_model,
                                            repository=shared_repository)
                elif condition == "E1-no-world-model":
                    outcome = _run_elevated(task, seed, world_model=None,
                                            repository=shared_repository)
                elif condition == "E2-no-transfer":
                    cold_dir = _tempfile.mkdtemp(prefix="euclid-bench-cold-")
                    cold_repo = PersistentPrimitiveRepository(
                        storage_path=str(Path(cold_dir) / "repo.json")
                    )
                    outcome = _run_elevated(task, seed, world_model=ProgramWorldModel(),
                                            repository=cold_repo)
                elif condition == "E3-shallow":
                    outcome = _run_elevated(task, seed, world_model=world_model,
                                            repository=shared_repository,
                                            max_depth=1)
                else:  # pragma: no cover - defensive
                    raise ValueError(condition)
                runs.append({"condition": condition, "task": task["name"],
                             "split": task["split"], "seed": seed, **outcome})

    summary: dict[str, Any] = {}
    for condition in conditions:
        for split in ("train", "held-out"):
            subset = [r for r in runs
                      if r.get("condition") == condition and r.get("split") == split]
            if not subset:
                continue
            summary.setdefault(condition, {})[split] = {
                "improvement": _stats([r["improvement"] for r in subset]),
                "evaluations": _stats([r["evals"] for r in subset]),
            }

    elevated = [r["improvement"] for r in runs
                if r.get("condition") == "D-elevated" and r.get("split") == "held-out"]
    cold = [r["improvement"] for r in runs
            if r.get("condition") == "E2-no-transfer" and r.get("split") == "held-out"]
    transfer_gain = None
    if elevated and cold:
        transfer_gain = round(
            sum(elevated) / len(elevated) - sum(cold) / len(cold), 6
        )

    return {
        "schema": "euclid.intelligence-elevation.benchmark/1",
        "shared_knowledge_diagnostics": {
            "world_model_transition_entries": len(world_model.to_dict()["table"]),
            "repository_primitives": len(shared_repository.repository),
            "note": (
                "confirms transfer/world-model machinery was actually engaged; "
                "identical ablation scores mean the knowledge did not change "
                "outcomes on these saturating tasks, not that it was absent"
            ),
        },
        "eval_budget_per_run": EVAL_BUDGET,
        "seeds": list(seeds),
        "smoke": smoke,
        "tasks": [{"name": t["name"], "split": t["split"]} for t in tasks],
        "conditions": list(conditions),
        "summary": summary,
        "transfer_gain_held_out": transfer_gain,
        "runs": runs,
        "budget_note": (
            "v16 engines accept generation budgets, not evaluation budgets; "
            "generations were chosen to approximate the evaluation budget and "
            "actual evaluation counts are reported per run."
        ),
        "claim_boundary": {
            "internal_benchmark_only": True,
            "no_superiority_asserted": True,
            "phi_is_diagnostic_not_objective": True,
            "external_validation": False,
        },
        "wall_time_seconds": round(time.monotonic() - started, 2),
    }


__all__ = ["EVAL_BUDGET", "SEEDS", "TASKS", "run_benchmark"]
