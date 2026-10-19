"""Shared hermetic environment for the EUCLID adversarial review harness.

Deterministic fake repo engineer, scripted measured executors, pinned clocks,
persistent (non-tempdir) state dirs under ``eval_harness/artifacts/tmp`` so
Windows sqlite-handle behaviour is observable instead of flaky.  Nothing here
patches production code paths; every probe runs the real composed runtime.
"""

from __future__ import annotations

import gc
import json
import shutil
import sys
import time
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from euclid.contracts import RewardAuthority  # noqa: E402

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
TMP_ROOT = ARTIFACTS / "tmp"


class FakeRepoEngineer:
    """Deterministic read-only stand-in for RepoEngineer.ask()."""

    def __init__(self, *args, **kwargs):
        self.calls = []

    def ask(self, prompt):
        self.calls.append(prompt)
        return {
            "task_id": f"task-{len(self.calls)}",
            "routes": ["repository_map", "import_audit", "focused_tests"],
            "evidence": {"import_audit": {"finding_count": 0, "files_audited": 1}},
        }


class ScriptedExecutor:
    """Deterministic executor: maps action_id -> scripted result dict."""

    def __init__(self, results):
        self.results = dict(results)
        self.calls = []

    def execute(self, action, payload):
        self.calls.append((action, dict(payload)))
        key = action if action in self.results else "default"
        return dict(self.results.get(key, self.results["default"]))


def measured_result(goal_met=True, reward=1.0, improvement=None):
    result = {
        "observation": "measured-pass",
        "goal_met": bool(goal_met),
        "reward": float(reward),
        "reward_authority": RewardAuthority.MEASURED_ENVIRONMENT.value,
    }
    if improvement is not None:
        result["measured_improvement"] = float(improvement)
    return result


def neutral_result(goal_met=False):
    return {
        "observation": "observed-neutral",
        "goal_met": bool(goal_met),
        # deliberately no reward keys -> RewardAuthority.NONE path
    }


def intervention_result(observation):
    """A discriminating observation for the explanation-space interventions.

    The declared explanation space predicts ``dependency-evidence`` /
    ``source-evidence`` for ``inspect`` and ``test-evidence`` for ``test``;
    an observation matching a hypothesis legitimately resolves competition,
    while an alien observation (e.g. "measured-pass") refutes every
    hypothesis and correctly aborts planning before compose.
    """
    return {
        "observation": str(observation),
        "goal_met": True,
        "reward": 0.0,
        "reward_authority": RewardAuthority.NONE.value,
    }


# Executor maps for scripted episodes: interventions must observe a
# hypothesis-consistent token or every hypothesis is refuted and the episode
# aborts before compose (fail-closed hypothesis exhaustion).
INTERVENTION_RESULTS = {
    "inspect": intervention_result("dependency-evidence"),
    "test": intervention_result("test-evidence"),
}


def regression_result():
    return {
        "observation": "measured-regress",
        "goal_met": False,
        "reward": -1.0,
        "measured_improvement": -0.25,
        "reward_authority": RewardAuthority.MEASURED_ENVIRONMENT.value,
    }


def state_dir(name, *, clean=True):
    """A persistent, inspectable state dir under eval_harness/artifacts/tmp."""
    path = TMP_ROOT / name
    if clean and path.exists():
        for _ in range(5):
            try:
                shutil.rmtree(path)
                break
            except Exception:
                time.sleep(0.05)
        else:
            import uuid
            path = TMP_ROOT / f"{name}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def production_runtime(directory, creator="adversary"):
    from euclid.runtime import EuclidRuntime

    with patch("Intelligence.repo_engineer.RepoEngineer", FakeRepoEngineer):
        return EuclidRuntime.production(creator_id=creator, state_dir=directory)


def problem(problem_id, strategy=None, problem_class="repository-wiring", **extra):
    p = {
        "problem_id": problem_id,
        "goal": "diagnose and verify repository wiring",
        "problem_class": problem_class,
        "structure": ["rel:dependency-chain", "rel:action-outcome"],
        "observations": ["an integration import is under review"],
        "initial_code": "def candidate(x):\n    return x\n",
    }
    if strategy is not None:
        p["strategy"] = strategy
    p.update(extra)
    return p


def pinned_clock(start=1_700_000_000.0, step=0.001):
    """Deterministic monotonic clock for seal-stability probes."""
    tick = {"t": start}

    def clock():
        tick["t"] += step
        return tick["t"]

    return clock


def close_runtime(runtime):
    """Close a runtime tolerantly, incl. the restore() handle leak.

    EuclidRuntime.restore() leaves the first MemoryDatabase connection wired
    inside cognition (reported finding); this releases it explicitly so the
    state dir can be cleaned on Windows.
    """
    errors = []
    try:
        runtime.close()
    except Exception as exc:  # noqa: BLE001 - record, do not raise
        errors.append(f"close: {exc}")
    try:
        cognition_db = getattr(getattr(runtime, "cognition", None), "memory", None)
        db = getattr(cognition_db, "database", None)
        if db is not None:
            db.close()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"cognition-db-close: {exc}")
    del runtime
    gc.collect()
    return errors


def episode_summary(state):
    """Machine-readable episode metrics from a CognitiveState."""
    transitions = list(state.transitions)
    phases = [t.phase for t in transitions]
    execute_rows = [
        dict(t.details) for t in transitions if t.phase == "execute" and "action" in t.details
    ]
    rank_rows = [dict(t.details) for t in transitions if t.phase == "rank"]
    objectives_rows = [dict(t.details) for t in transitions if t.phase == "objectives"]
    return {
        "problem_id": state.problem_id,
        "outcome": state.outcome.value if state.outcome else None,
        "outcome_detail": state.outcome_detail,
        "cycles": phases.count("cycle"),
        "executed_actions": [row["action"] for row in execute_rows],
        "execute_results": [row.get("result") for row in execute_rows],
        "candidate_ranking": [c.action_id for c in state.candidates],
        "candidate_origins": [c.origin for c in state.candidates],
        "last_ranking": rank_rows[-1].get("ranking") if rank_rows else None,
        "selected_strategy": state.selected_strategy,
        "alternative_strategies": list(state.alternative_strategies),
        "plan_nodes": [n.node_id for n in state.plan],
        "replanning_events": len(state.replanning_events),
        "objective_applications": [row.get("objective_ids") for row in objectives_rows],
        "prediction_errors": list(state.prediction_errors),
        "retrieved_memory_refs": list(state.retrieved_memory_refs),
        "learning_updates": [dict(u) for u in state.learning_updates],
        "control_decisions": [d.get("action") for d in state.control_decisions],
        "ablations": list(state.ablations),
        "transitions": len(transitions),
        "seal": state.to_payload()["seal"],
    }


def write_artifact(name, payload):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / f"{name}.json"
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return path


def finding(verdict, detail):
    return {"verdict": verdict, "detail": detail, "checked_at": time.time()}
