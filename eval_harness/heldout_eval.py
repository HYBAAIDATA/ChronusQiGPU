"""Held-out deterministic evaluation for EUCLID intelligence readiness.

Partitions (fixed seeds, equal budgets — solve_repository_problem fixes
max_cycles=2 for every solve):

  train:        problems solved first, intended to warm learned state
  validation:   same problem class, distinct ids/code
  temporal:     a distinct problem class presented after train
  irrelevant:   seeded irrelevant memory; decision must equal the null run
  absent-reward: executor returns observation only (RewardAuthority.NONE)
  cold:         fresh runtime (no prior state)
  warm:         restarted runtime on the train state dir

Measures: terminal outcome, cycles/actions, prediction error, selected
strategy, candidate ranking, plan/objective changes, relevant and irrelevant
retrieval, decision difference vs controls, measured gain/zero/regression.
No improvement is required; negative results are preserved verbatim.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from environment import (  # noqa: E402
    INTERVENTION_RESULTS,
    ScriptedExecutor,
    close_runtime,
    episode_summary,
    measured_result,
    neutral_result,
    pinned_clock,
    problem,
    production_runtime,
    regression_result,
    state_dir,
)

from euclid.cognition.interfaces import MemoryItem
from euclid.cognition.state import MemoryKind  # noqa: E402

TRAIN_TASKS = [
    problem("train-1", problem_class="train-class", initial_code="def f(x):\n    return x + 1\n"),
    problem("train-2", problem_class="train-class", initial_code="def g(y):\n    return y * 2\n"),
]
VALIDATION_TASKS = [
    problem("val-1", problem_class="train-class", initial_code="def h(z):\n    return z - 3\n"),
    problem("val-2", problem_class="train-class", initial_code="def k(w):\n    return w / 4\n"),
]
TEMPORAL_TASKS = [
    problem(
        "temporal-1",
        problem_class="temporal-class",
        structure=["rel:holdout-signal", "rel:time-shift"],
        initial_code="def t(u):\n    return u\n",
    ),
]
CONTROL_TASK = problem("ctl-1", problem_class="ctl-class")

IRRELEVANT_MEMORY = MemoryItem(
    memory_id="irrelevant-null-1",
    kind=MemoryKind.EPISODIC,
    payload={"prior_outcome": "unrelated", "note": "noise"},
    provenance="adversarial-seed",
    structural_features=frozenset({"rel:noise", "rel:unrelated"}),
    transfer_value=0.1,
)


def _solve_set(runtime, tasks, result=None):
    executor = ScriptedExecutor({**INTERVENTION_RESULTS, "default": result or measured_result()})
    runtime.cognition.executor = executor
    rows = []
    for task in tasks:
        state = runtime.solve_repository_problem(task)
        rows.append(episode_summary(state))
    return rows


def run_all():
    report = {"schema": "euclid.adversarial.heldout-eval/1", "runs": {}}

    # -- cold runtime: fresh state, measured executor -----------------------
    root = state_dir("he-cold")
    cold = production_runtime(root)
    try:
        cold.cognition.clock = pinned_clock()
        cold_rows = _solve_set(cold, VALIDATION_TASKS)
    finally:
        close_runtime(cold)
    report["runs"]["cold_runtime"] = {
        "tasks": cold_rows,
        "note": "fresh runtime, no prior learned state",
    }

    # -- train + warm restart: learned state must persist -------------------
    root = state_dir("he-warm")
    warm = production_runtime(root)
    try:
        warm.cognition.clock = pinned_clock()
        _solve_set(warm, TRAIN_TASKS)  # training partition
    finally:
        close_runtime(warm)
    warm2 = production_runtime(root)
    try:
        warm2.cognition.clock = pinned_clock(9_000_000_000.0)
        warm_rows = _solve_set(warm2, VALIDATION_TASKS)
        temporal_rows = _solve_set(warm2, TEMPORAL_TASKS)
    finally:
        close_runtime(warm2)
    report["runs"]["warm_runtime"] = {
        "validation_tasks": warm_rows,
        "temporal_holdout": temporal_rows,
        "note": "second production() boot on the trained state dir",
    }

    # -- irrelevant-memory null control -------------------------------------
    root = state_dir("he-irrelevant")
    rt = production_runtime(root)
    try:
        rt.cognition.clock = pinned_clock()
        rt.cognition.memory.store(IRRELEVANT_MEMORY)
        irrelevant_rows = _solve_set(rt, [CONTROL_TASK])
    finally:
        close_runtime(rt)
    report["runs"]["irrelevant_memory_control"] = {"tasks": irrelevant_rows}

    # -- absent-reward control ----------------------------------------------
    root = state_dir("he-absent-reward")
    rt = production_runtime(root)
    try:
        rt.cognition.clock = pinned_clock()
        absent_rows = _solve_set(rt, [CONTROL_TASK], result=neutral_result())
        learner = rt.learning.experience_learner
        absent_transitions = len(getattr(learner, "transitions", []))
    finally:
        close_runtime(rt)
    report["runs"]["absent_reward_control"] = {
        "tasks": absent_rows,
        "superlearner_transitions": absent_transitions,
        "note": "executor returns observation only; no reward authority",
    }

    # -- regression control (measured negative gain) ------------------------
    root = state_dir("he-regress")
    rt = production_runtime(root)
    try:
        rt.cognition.clock = pinned_clock()
        regress_rows = _solve_set(rt, [CONTROL_TASK], result=regression_result())
    finally:
        close_runtime(rt)
    report["runs"]["regression_control"] = {"tasks": regress_rows}

    # -- derived comparisons --------------------------------------------------
    cold_ranking = cold_rows[0]["candidate_ranking"] if cold_rows else None
    warm_ranking = warm_rows[0]["candidate_ranking"] if warm_rows else None
    irr_ranking = irrelevant_rows[0]["candidate_ranking"] if irrelevant_rows else None
    absent_ranking = absent_rows[0]["candidate_ranking"] if absent_rows else None
    report["comparisons"] = {
        "cold_vs_warm_ranking_equal": cold_ranking == warm_ranking,
        "cold_vs_irrelevant_ranking_equal": cold_ranking == irr_ranking,
        "cold_vs_absent_reward_ranking_equal": cold_ranking == absent_ranking,
        "warm_learned_state_differs_from_cold": {
            "cold_strategy": cold_rows[0]["selected_strategy"] if cold_rows else None,
            "warm_strategy": warm_rows[0]["selected_strategy"] if warm_rows else None,
        },
        "absent_reward_learner_transitions": absent_transitions,
    }
    report["note"] = (
        "No improvement is asserted. Rows are evidence; comparisons record "
        "whether learned/seeded state changed any recorded decision."
    )
    return report


if __name__ == "__main__":
    import json

    print(json.dumps(run_all(), indent=2, sort_keys=True, default=str))
