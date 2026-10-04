"""Reachability-evidence audit: recorded stages vs executable evidence.

For every component the runtime ledger records, this recomputes the stage the
component honestly earned in the episode, then emits a capability matrix:

  recorded_stage   — what runtime.py's grant rules wrote
  assessed_stage   — the highest stage supported by executable evidence
  assessment_basis — the executable evidence considered
  verdict          — MATCH / INFLATED / UNDERSTATED / ABSENT
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
    measured_result,
    pinned_clock,
    problem,
    production_runtime,
    state_dir,
)

from euclid.cognition.reachability import ReachabilityStage  # noqa: E402

STAGE_NAMES = [stage.name for stage in ReachabilityStage]


def _assess(component, runtime, state, artifacts):
    """Return (assessed_stage_name, basis) from executable evidence."""
    phases = {t.phase for t in state.transitions}
    executed_actions = {
        str(t.details.get("action")) for t in state.transitions if t.phase == "execute"
    }
    files = {
        "reachability": (artifacts / "cognition_reachability.json").is_file(),
        "memory_db": (artifacts / "euclid_memory.sqlite3").is_file(),
        "superlearner": (artifacts / "experience_superlearner.json").is_file(),
        "strategy": (artifacts / "strategy_learning.json").is_file(),
        "pythia_journal": (artifacts / "pythia" / "journal.jsonl").is_file(),
    }
    measured = False
    for t in state.transitions:
        if t.phase == "execute" and isinstance(t.details.get("result"), dict):
            if t.details["result"].get("reward_authority") == ("measured-environment"):
                measured = True

    rules = {
        "toe.world_model": (
            "FEEDBACK_CLOSED" if "compare" in phases else "REACHABLE",
            "compare phase ran; world model updated from observed outcome "
            "(TOEWorldModelAdapter holds state in memory, not persisted)",
        ),
        "toe.planning": (
            (
                "CHANGES_DECISION"
                if (state.replanning_events or any(a.startswith("plan-") for a in executed_actions))
                else "USED_IN_EPISODE"
            ),
            "CHANGES_DECISION requires a replan or an executed plan-node "
            "candidate; a plan composed but never consumed only ran",
        ),
        "toe.meta_reasoning": (
            (
                "CHANGES_DECISION"
                if (
                    state.replanning_events
                    or any(
                        t.phase == "metacontrol" and t.details.get("action") == "halt_stalled"
                        for t in state.transitions
                    )
                )
                else "USED_IN_EPISODE"
            ),
            "non-continue metacontrol actions are applied: replan rewrites "
            "the plan, halt_stalled ends the episode early",
        ),
        "euclid.representation_controller": (
            (
                "CHANGES_DECISION"
                if any(
                    t.phase == "represent"
                    and (t.details.get("representation_trial") or {}).get("accepted")
                    for t in state.transitions
                )
                else "USED_IN_EPISODE"
            ),
            "accepted restructuring changes representation consumed " "downstream",
        ),
        "euclid.objective_controller": (
            ("CHANGES_DECISION" if "objective-applied" in phases else "USED_IN_EPISODE"),
            "derived objectives are applied to planning_goal and passed "
            "to the rank evaluator's context",
        ),
        "euclid.strategy_meta_learning": (
            (
                "FEEDBACK_CLOSED"
                if any(
                    u.get("kind") in {"strategy", "executed-arm"} for u in state.learning_updates
                )
                else "USED_IN_EPISODE"
            ),
            "a strategy/executed-arm update banks the outcome under a key "
            "the selection machinery reads (select_strategy or composer "
            "scoring)",
        ),
        "euclid.learning_service": (
            "PERSISTED",
            "canonical learning-service record wrote durably",
        ),
        "euclid.memory_database": (
            (
                "TRANSFER_VERIFIED"
                if "memory-influence" in phases
                else ("PERSISTED" if files["memory_db"] else "USED_IN_EPISODE")
            ),
            "TRANSFER_VERIFIED only when a durable record observably biased "
            "candidate scoring (memory-influence transition); otherwise "
            "PERSISTED once the sqlite store wrote durably and verify() "
            "passes; restart verification is self-certified (no verify() on "
            "boot)",
        ),
        "pythia.memory": (
            "PERSISTED" if files["memory_db"] else "PRESENT",
            "the durable cognition memory adapter writes episode records "
            "into the sqlite store covered by verify()",
        ),
        "pythia.store": (
            "PERSISTED" if files["pythia_journal"] else "PRESENT",
            "store.record_run appends journal rows only when a " "reward-bearing experience flows",
        ),
        "experience_superlearner": (
            "PERSISTED" if (measured and files["superlearner"]) else "PRESENT",
            "observe() runs only for reward-bearing experiences",
        ),
        "repository.engineer": (
            "OUTCOME_OBSERVED" if "execute" in phases else "REACHABLE",
            "governed executor ran and the observation was recorded",
        ),
        "euclid.v16.search": (
            (
                "CHANGES_DECISION"
                if any(a.startswith("search:") for a in executed_actions)
                else (
                    "USED_IN_EPISODE"
                    if any(c.action_id.startswith("search:") for c in state.candidates)
                    else "REACHABLE"
                )
            ),
            "v16 search changes the decision only when a search candidate "
            "was the executed action; composed-but-not-executed is used",
        ),
        "euclid.v16.primitives": (
            (
                "CHANGES_DECISION"
                if any(a.startswith("primitive:") for a in executed_actions)
                else (
                    "USED_IN_EPISODE"
                    if any(c.action_id.startswith("primitive:") for c in state.candidates)
                    else "REACHABLE"
                )
            ),
            "primitives change the decision only when a primitive "
            "candidate was the executed action; composed-but-not-executed "
            "is used",
        ),
    }
    return rules.get(
        component,
        ("REACHABLE", "composed at startup; no episode evidence"),
    )


def run_all():
    root = state_dir("reach-audit")
    rt = production_runtime(root)
    try:
        rt.cognition.clock = pinned_clock()
        rt.cognition.executor = ScriptedExecutor({**INTERVENTION_RESULTS, "default": measured_result()})
        rt.solve_repository_problem(problem("reach-audit"))
        recorded = {}
        for entry in rt.reachability._entries:
            recorded[entry.component] = entry.stage
    finally:
        close_runtime(rt)

    # --- measured executor is required for the honest PERSISTED rows --------
    root2 = state_dir("reach-audit-measured")
    rt2 = production_runtime(root2)
    try:
        rt2.cognition.executor = ScriptedExecutor({**INTERVENTION_RESULTS, "default": measured_result()})
        state2 = rt2.solve_repository_problem(problem("reach-audit-2"))
    finally:
        close_runtime(rt2)

    matrix = {}
    for component, recorded_stage in sorted(recorded.items()):
        assessed, basis = _assess(component, rt2, state2, root)
        recorded_idx = STAGE_NAMES.index(recorded_stage)
        assessed_idx = STAGE_NAMES.index(assessed)
        if recorded_idx > assessed_idx:
            verdict = "INFLATED"
        elif recorded_idx < assessed_idx:
            verdict = "UNDERSTATED"
        else:
            verdict = "MATCH"
        matrix[component] = {
            "recorded_stage": recorded_stage,
            "assessed_stage": assessed,
            "assessment_basis": basis,
            "verdict": verdict,
        }
    return {
        "schema": "euclid.adversarial.capability-matrix/1",
        "ladder": STAGE_NAMES,
        "matrix": matrix,
        "note": (
            "assessed_stage is the highest stage supported by executable "
            "episode evidence; every grant rule requires the episode "
            "transition it records"
        ),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run_all(), indent=2, sort_keys=True, default=str))
