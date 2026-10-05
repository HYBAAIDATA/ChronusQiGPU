"""Downstream memory-use audit for EUCLID intelligence readiness.

A retrieved record counts as influential only if removing it changes a
recorded downstream decision under the same deterministic conditions.

Recorded decision fingerprint = executed action ids + candidate ranking +
selected strategy + plan node ids + terminal outcome.

Ablations:
  A relevant memory present;
  B relevant memory removed (nothing seeded);
  C irrelevant memory present only;
  D all memory disabled (empty memory system, fresh runtime).
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
    pinned_clock,
    problem,
    production_runtime,
    state_dir,
)

from euclid.cognition.interfaces import MemoryItem
from euclid.cognition.state import MemoryKind  # noqa: E402

PROBLEM_STRUCTURE = ["rel:dependency-chain", "rel:action-outcome"]


def _seed_memory(runtime, items):
    """Store pre-episode memory records into the runtime's durable memory."""
    memory = runtime.cognition.memory
    for item in items:
        memory.store(item)


def _decision_fingerprint(state):
    summary = episode_summary(state)
    return {
        "executed_actions": summary["executed_actions"],
        "candidate_ranking": summary["candidate_ranking"],
        "selected_strategy": summary["selected_strategy"],
        "plan_nodes": summary["plan_nodes"],
        "outcome": summary["outcome"],
    }


def _relevant_item():
    # Same shape a real producer writes: an executed action + recorded
    # success, keyed to structural features that overlap THIS problem.
    return MemoryItem(
        memory_id="relevant-episode-1",
        kind=MemoryKind.EPISODIC,
        payload={
            "prior_outcome": "solved",
            "success": True,
            "executed_action": "primitive:MUTATE:swap_op",
            "note": "same dependency-chain structure",
        },
        provenance="adversarial-seed",
        structural_features=frozenset(PROBLEM_STRUCTURE),
        transfer_value=0.9,
    )


def _irrelevant_item():
    # Identical bias content to the relevant item — a different executed
    # action — but zero structural overlap, so the gate must keep it inert.
    return MemoryItem(
        memory_id="irrelevant-episode-1",
        kind=MemoryKind.EPISODIC,
        payload={
            "prior_outcome": "solved",
            "success": True,
            "executed_action": "primitive:MUTATE:list_comp",
            "note": "unrelated unrelated unrelated",
        },
        provenance="adversarial-seed",
        structural_features=frozenset(["rel:cooking", "rel:unrelated", "rel:noise"]),
        transfer_value=0.1,
    )


def _run(name, items, result=None, prob=None):
    root = state_dir(f"mi-{name}")
    rt = production_runtime(root)
    try:
        rt.cognition.clock = pinned_clock()
        rt.cognition.executor = ScriptedExecutor({**INTERVENTION_RESULTS, "default": result or measured_result()})
        _seed_memory(rt, items)
        state = rt.solve_repository_problem(prob or problem("mi-probe"))
        return state
    finally:
        close_runtime(rt)


def run_all():
    prob = problem("mi-probe", structure=list(PROBLEM_STRUCTURE))
    state_relevant = _run("relevant", [_relevant_item()], prob=prob)
    state_removed = _run("removed", [], prob=prob)
    state_irrelevant = _run("irrelevant", [_irrelevant_item()], prob=prob)
    state_none = _run("none", [], prob=prob)

    fp_relevant = _decision_fingerprint(state_relevant)
    fp_removed = _decision_fingerprint(state_removed)
    fp_irrelevant = _decision_fingerprint(state_irrelevant)
    fp_none = _decision_fingerprint(state_none)

    def _retrieval(state, needle):
        return any(needle in ref for ref in state.retrieved_memory_refs)

    report = {
        "runs": {
            "A_relevant_present": {
                "fingerprint": fp_relevant,
                "retrieved_relevant": _retrieval(state_relevant, "relevant"),
                "retrieved_refs": list(state_relevant.retrieved_memory_refs),
                "episode": episode_summary(state_relevant),
            },
            "B_relevant_removed": {
                "fingerprint": fp_removed,
                "retrieved_refs": list(state_removed.retrieved_memory_refs),
            },
            "C_irrelevant_present": {
                "fingerprint": fp_irrelevant,
                "retrieved_irrelevant": _retrieval(state_irrelevant, "irrelevant"),
                "retrieved_refs": list(state_irrelevant.retrieved_memory_refs),
            },
            "D_all_disabled": {
                "fingerprint": fp_none,
                "retrieved_refs": list(state_none.retrieved_memory_refs),
            },
        },
        "influence_verdicts": {
            "relevant_influential": fp_relevant != fp_removed,
            "irrelevant_changes_decision": fp_irrelevant != fp_none,
            "relevant_vs_irrelevant_differ": fp_relevant != fp_irrelevant,
        },
        "claim": (
            "a retrieved record counts as influential only if removing it "
            "changes a recorded downstream decision"
        ),
        "measured_result": (
            "retrieval is RECORDED but has no channel into the executed "
            "decision under deterministic conditions"
            if fp_relevant == fp_removed
            else "retrieval demonstrably changed a recorded decision"
        ),
    }
    return report


if __name__ == "__main__":
    import json

    print(json.dumps(run_all(), indent=2, sort_keys=True, default=str))
