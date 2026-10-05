"""Child process for the EUCLID cognition cross-process restart test.

Run as ``python tests/euclid_cognition_child.py <mode> <state_dir>``.

Restart evidence must come from a genuinely separate interpreter: an
in-process "reload" proves nothing about durable state, because the same
process may still hold live objects that the next read quietly trusts.

Modes: write | read | tamper_replay | tamper_memory
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "chronus" / "mla1517_platform" / "python"))

from euclid.contracts import RewardAuthority  # noqa: E402
from euclid.memory_database import MemoryScope  # noqa: E402
from euclid.runtime import EuclidRuntime  # noqa: E402

CREATOR = "restart-probe"

#: What the environment would plausibly observe for each composed action,
#: mirroring the ``explanations`` table in ``EuclidRuntime._compose_cognition``.
#: Reporting a token no hypothesis predicted would refute every competing
#: hypothesis and the loop would (correctly) refuse to plan.
_OBSERVED_BY_ACTION = {
    "inspect": "dependency-evidence",
    "test": "test-evidence",
    "verify": "test-evidence",
}


INTERVENTION_OBSERVATIONS = {"inspect": "dependency-evidence", "test": "test-evidence"}


class DeterministicExecutor:
    """Deterministic stand-in for the repository organ.

    The executor is a declared, governed seam of the composition root.  The
    restart test exercises durable cognition state, so it needs an executor
    whose observation is a pure function of the action; the real repository
    organ costs ~30s per audit and is covered by its own test.
    """

    def __init__(self, *, meet_goal: bool = False) -> None:
        self.meet_goal = meet_goal
        self.calls: list[str] = []

    def execute(self, action: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls.append(str(action))
        return {
            # Discriminating interventions observe a token from the declared
            # explanation space; an alien token refutes every hypothesis and
            # the episode aborts fail-closed before planning.
            "observation": INTERVENTION_OBSERVATIONS.get(
                str(action), f"observed:{action}"
            ),
            "goal_met": self.meet_goal,
            "cycle": payload.get("cycle"),
            # No measured reward: authority stays NONE so absent reward can
            # never become positive reward downstream.
            "reward_authority": RewardAuthority.NONE.value,
        }


PROBLEM: dict[str, Any] = {
    "problem_id": "restart-child-1",
    "goal": "diagnose the wiring",
    "problem_class": "repository-wiring",
    "structure": ["rel:dependency-chain", "rel:action-outcome"],
    "observations": ["an import boundary is under review"],
}


def build(state_dir: str) -> EuclidRuntime:
    return EuclidRuntime.production(creator_id=CREATOR, state_dir=state_dir)


def mode_write(state_dir: str) -> dict[str, Any]:
    runtime = build(state_dir)
    try:
        runtime.cognition.executor = DeterministicExecutor()
        state = runtime.solve_repository_problem(PROBLEM)
        replay = runtime.learning.replay_state()
        memory = runtime.learning.memory_database.verify()
        return {
            "mode": "write",
            "ok": True,
            "pid": os.getpid(),
            "problem_id": state.problem_id,
            "outcome": state.outcome.value if state.outcome else None,
            "state_digest": state.transitions[-1].digest,
            "memory_valid": memory.get("valid"),
            "memories": memory.get("memories"),
            "event_chain_head": memory.get("event_chain_head"),
            "replay_entries": replay.get("journal_entries"),
            "replay_sha256": replay.get("journal_sha256"),
            "experiences_seen": len(runtime.learning._seen),
            "learning_updates": [dict(u) for u in state.learning_updates],
        }
    finally:
        runtime.close()


def mode_read(state_dir: str) -> dict[str, Any]:
    runtime = build(state_dir)
    try:
        memory_error = None
        try:
            memory = runtime.learning.memory_database.verify()
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            memory, memory_error = {}, f"{type(exc).__name__}: {exc}"

        records = runtime.learning.memory_database.query(
            scope=MemoryScope(CREATOR, "euclid-cognition", "repository"), limit=500,
        )
        scopes = sorted({(r.scope.tenant_id, r.scope.mission_id, r.scope.domain)
                         for r in records})

        runtime.cognition.executor = DeterministicExecutor()
        state = runtime.solve_repository_problem(
            {**PROBLEM, "problem_id": "restart-child-2"}
        )
        stage = runtime.reachability.stage("euclid.memory_database")
        return {
            "mode": "read",
            "ok": True,
            "pid": os.getpid(),
            "memory_valid": memory.get("valid"),
            "memory_error": memory_error,
            "memories": memory.get("memories"),
            "event_chain_head": memory.get("event_chain_head"),
            "replay_entries": runtime.learning.replay_state().get("journal_entries"),
            "record_count": len(records),
            "scopes": [list(s) for s in scopes],
            "provenances": sorted({r.provenance for r in records})[:4],
            "retrieved": len(state.retrieved_memory_refs),
            "memory_database_stage": stage.name if stage else None,
            "experiences_seen": len(runtime.learning._seen),
        }
    finally:
        runtime.close()


def mode_tamper_replay(state_dir: str) -> dict[str, Any]:
    journal = Path(state_dir) / "replay_journal.json"
    payload = json.loads(journal.read_text(encoding="utf-8"))
    payload["entries"] = {}
    journal.write_text(json.dumps(payload), encoding="utf-8")
    try:
        build(state_dir).close()
    except ValueError as exc:
        return {"mode": "tamper_replay", "ok": True, "refused": True, "error": str(exc)}
    return {"mode": "tamper_replay", "ok": True, "refused": False}


def mode_tamper_memory(state_dir: str) -> dict[str, Any]:
    runtime = build(state_dir)
    try:
        connection = runtime.learning.memory_database._connection
        connection.execute("UPDATE memories SET provenance = 'tampered' WHERE 1=1")
        connection.commit()
        try:
            runtime.learning.memory_database.verify()
        except Exception as exc:  # noqa: BLE001 - the detection is the outcome
            return {"mode": "tamper_memory", "ok": True, "detected": True,
                    "error": f"{type(exc).__name__}: {exc}"}
        return {"mode": "tamper_memory", "ok": True, "detected": False}
    finally:
        runtime.close()


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(json.dumps({"ok": False, "error": "usage: mode state_dir"}))
        return 2
    mode, state_dir = argv[1], argv[2]
    handlers = {
        "write": mode_write,
        "read": mode_read,
        "tamper_replay": mode_tamper_replay,
        "tamper_memory": mode_tamper_memory,
    }
    handler = handlers.get(mode)
    if handler is None:
        print(json.dumps({"ok": False, "error": f"unknown mode {mode}"}))
        return 2
    print(json.dumps(handler(state_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
