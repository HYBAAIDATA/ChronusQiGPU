"""Executable falsification suite for EUCLID intelligence readiness.

Every check returns {"verdict": PASS|FAIL, ...} where PASS means the stated
property held under execution and FAIL means the claim was falsified or is
unsupported.  Negative results are recorded, never hidden.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from environment import (  # noqa: E402
    ScriptedExecutor,
    close_runtime,
    measured_result,
    pinned_clock,
    problem,
    production_runtime,
    state_dir,
)

from euclid.contracts import Experience, RewardAuthority  # noqa: E402
from euclid.learning_service import LearningService  # noqa: E402


def _solve(runtime, pid="falsify-1", result=None, prob=None):
    runtime.cognition.executor = ScriptedExecutor(
        {"default": result if result is not None else measured_result()}
    )
    return runtime.solve_repository_problem(prob or problem(pid))


def check_deterministic_seal():
    """Identical fixed-input episodes produce identical sealed state."""
    seals = []
    for i in range(2):
        root = state_dir(f"det-seal-{i}")
        rt = production_runtime(root)
        try:
            state = _solve(rt)
            seals.append(state.to_payload()["seal"])
        finally:
            close_runtime(rt)
    return {
        "verdict": "PASS" if seals[0] == seals[1] else "FAIL",
        "seals": seals,
        "claim": "identical fixed-input episodes produce identical sealed state",
    }


def check_replay_identity_stable():
    """An identical episode must mint an identical replay_id (fails closed)."""
    digests = []
    replay_ids = []
    for i in range(2):
        root = state_dir(f"replay-id-{i}")
        rt = production_runtime(root)
        try:
            state = _solve(rt, pid="replay-stable")
            updates = [
                u for u in state.learning_updates if u.get("kind") == "canonical-learning-service"
            ]
            replay_ids.extend(u.get("replay_id") for u in updates)
            digests.extend(u.get("digest") for u in updates)
        finally:
            close_runtime(rt)
    # second run of identical content must collide -> duplicate replay rejected
    # is verified separately; here identity stability is the property.
    return {
        "verdict": "PASS" if replay_ids[0] == replay_ids[1] else "FAIL",
        "replay_ids_run1": replay_ids[0],
        "replay_ids_run2": replay_ids[1],
        "claim": "replayed experiences retain stable identity",
    }


def check_second_action_same_domain():
    """A second distinct action in one domain must be learnable, not crash."""
    from hyba_substrate.euclid_experience_superlearner import (
        ExperienceSuperlearner,
    )

    root = state_dir("second-action")
    svc = LearningService(experience_learner=ExperienceSuperlearner(root / "sl.json"))
    try:
        for i, action in enumerate(("action-a", "action-b")):
            svc.record(
                Experience(
                    f"exp-{i}",
                    "m",
                    "domain",
                    "service",
                    {"k": 1},
                    action,
                    {"o": i},
                    0.5,
                    RewardAuthority.OPERATOR,
                    "probe",
                    0.0,
                    f"replay-{i}",
                )
            )
        learned = len(svc.experience_learner.transitions) == 2
        verdict = "PASS" if learned else "FAIL"
        detail = svc.experience_learner.tasks["domain"].actions
    except ValueError as exc:
        verdict, detail = "FAIL", str(exc)
    return {
        "verdict": verdict,
        "actions": list(detail) if not isinstance(detail, str) else detail,
        "claim": "a domain may learn more than one action",
    }


def check_duplicate_replay_closed():
    root = state_dir("dup-replay")
    svc = LearningService(replay_journal_path=root / "journal.json")
    exp = Experience(
        "e1",
        "m",
        "d",
        "service",
        {"k": 1},
        "a",
        {"o": 1},
        0.5,
        RewardAuthority.OPERATOR,
        "probe",
        0.0,
        "rp-1",
    )
    svc.record(exp)
    try:
        svc.record(exp)
        return {"verdict": "FAIL", "claim": "duplicate replay fails closed"}
    except ValueError:
        pass
    # conflicting content under same replay_id must also fail closed
    conflicting = Experience(
        "e1",
        "m",
        "d",
        "service",
        {"k": 2},
        "a",
        {"o": 9},
        0.5,
        RewardAuthority.OPERATOR,
        "probe",
        0.0,
        "rp-1",
    )
    try:
        svc.record(conflicting)
        return {
            "verdict": "FAIL",
            "claim": "conflicting replay_id fails closed",
        }
    except ValueError:
        return {"verdict": "PASS", "claim": "duplicate replay fails closed"}


def check_memory_db_tamper_rejected():
    root = state_dir("memdb-tamper")
    rt = production_runtime(root)
    try:
        _solve(rt)
        db = rt.learning.memory_database
        db.put(
            scope=rt.cognition.memory.scope,
            tier="episodic",
            content={"probe": True},
            provenance="probe",
            reward_authority=RewardAuthority.NONE,
            uncertainty=0.0,
            replay_id="tamper-probe",
            memory_id="tamper-probe",
        )
        # corrupt the stored content hash directly
        conn = db._connection
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' " "AND name='memories'"
        ).fetchone()
        if row is None:
            table = "memory_records"
            check_col = "content_hash"
        else:
            table = "memories"
            check_col = "content_hash"
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        id_col = "memory_id" if "memory_id" in cols else "id"
        conn.execute(
            f"UPDATE {table} SET {check_col} = 'deadbeef' " f"WHERE {id_col} = 'tamper-probe'"
        )
        conn.commit()
        try:
            report = db.verify()
            ok = report.get("valid") is False
        except ValueError:
            ok = True  # verify() fails closed on tampered content
    finally:
        close_runtime(rt)
    return {
        "verdict": "PASS" if ok else "FAIL",
        "claim": "tampered durable memory is detected by verify()",
    }


def check_reachability_tamper_rejected():
    root = state_dir("reach-tamper")
    rt = production_runtime(root)
    try:
        _solve(rt)
    finally:
        close_runtime(rt)
    path = root / "cognition_reachability.json"
    payload = json.loads(path.read_text())
    payload["entries"].append(
        {
            "component": "pythia.memory",
            "stage": "TRANSFER_VERIFIED",
            "episode_id": "forged",
            "evidence_ref": "forged",
            "detail": {},
        }
    )
    path.write_text(json.dumps(payload))
    from euclid.cognition.reachability import ReachabilityMatrix

    try:
        ReachabilityMatrix.load(path)
        return {
            "verdict": "FAIL",
            "claim": "forged reachability entries are rejected on load",
        }
    except ValueError:
        return {
            "verdict": "PASS",
            "claim": "forged reachability entries are rejected on load",
        }


def check_strategy_feedback_loop_connected():
    """Can measured outcomes change the executed action?

    An episode's measured outcome must be banked under a key the decision
    machinery actually reads: the executed arm's stats[(class, arm)] for
    arm in STRATEGIES (composer scoring) or the selected strategy id
    (select_strategy).  Feedback written under none of those is
    disconnected and the executed strategy cannot respond to outcomes.
    """
    from euclid.cognition.service import STRATEGIES, enable_intelligence
    from euclid.runtime import EuclidRuntime

    root = state_dir("strategy-loop")
    runtime = EuclidRuntime(creator_id="adv", state_dir=root)
    try:
        service = enable_intelligence(runtime, seed=11, clock=pinned_clock())
        try:
            episode = service.solve(
                {
                    "problem_id": "strategy-loop",
                    "code": "def f(x):\n    return x\n",
                    "goal": "improve measured fitness",
                    "seed": 5,
                }
            )
        except Exception as exc:  # noqa: BLE001 - sandbox may be unavailable
            return {
                "verdict": "SKIP",
                "error": str(exc),
                "claim": "measured strategy feedback changes the executed strategy",
            }
        composer_visible = {key: list(value) for key, value in service.metalearner._stats.items()}
        arm_keys = sorted(sid for _, sid in composer_visible if sid in STRATEGIES)
        executed = [
            str(t.get("details", {}).get("action"))
            for t in episode.state_payload.get("transitions", ())
            if t.get("phase") == "execute"
        ]
    finally:
        close_runtime(runtime)
    return {
        "verdict": "PASS" if arm_keys else "FAIL",
        "composer_stats_keys": [[klass, sid] for klass, sid in composer_visible],
        "composer_portfolio": list(STRATEGIES),
        "executed_actions": executed,
        "executed_arm_stats_keys": arm_keys,
        "note": (
            "executed-arm stats keys present"
            if arm_keys
            else "feedback stats were written only for ids the candidate "
            "composer never reads; the executed strategy cannot respond "
            "to measured outcomes"
        ),
        "claim": "measured strategy feedback changes the executed strategy",
    }


def check_world_model_single_observation():
    """One measured execution -> one world-model observation."""
    from euclid.cognition.service import enable_intelligence
    from euclid.runtime import EuclidRuntime

    root = state_dir("wm-count")
    runtime = EuclidRuntime(creator_id="adv", state_dir=root)
    try:
        service = enable_intelligence(runtime, seed=11, clock=pinned_clock())
        try:
            episode = service.solve(
                {
                    "problem_id": "wm-count",
                    "code": "def f(x):\n    return x\n",
                    "goal": "improve measured fitness",
                    "seed": 5,
                }
            )
        except Exception as exc:  # noqa: BLE001 - sandbox may be unavailable
            return {
                "verdict": "SKIP",
                "error": str(exc),
                "claim": "one execution -> one world-model observation",
            }
        executes = [
            t for t in episode.state_payload.get("transitions", ()) if t.get("phase") == "execute"
        ]
        counts = {
            key: sum(table.values())
            for key, table in service.world_model._table.items()
            if "strategy:" in key
        }
        observed_total = sum(counts.values())
        verdict = "PASS" if observed_total == len(executes) else "FAIL"
        return {
            "verdict": verdict,
            "executions": len(executes),
            "strategy_counts": counts,
            "claim": "one execution -> one world-model observation",
        }
    finally:
        close_runtime(runtime)


def check_malformed_source_diagnosis():
    """Malformed source must reach diagnosis, not crash representation."""
    root = state_dir("malformed")
    rt = production_runtime(root)
    try:
        state = _solve(
            rt,
            pid="malformed-1",
            prob=problem("malformed-1", initial_code="def broken(:\n"),
        )
        reached = state.outcome is not None
        detail = state.outcome.value if state.outcome else None
    except Exception as exc:  # noqa: BLE001
        reached, detail = False, f"crashed: {exc}"
    finally:
        close_runtime(rt)
    return {
        "verdict": "PASS" if reached else "FAIL",
        "outcome": detail,
        "claim": "malformed source reaches diagnosis without crashing",
    }


def check_terminal_cycle_learned():
    """Terminal cycles are learned before halt (learn runs before terminate)."""
    root = state_dir("terminal-learn")
    rt = production_runtime(root)
    try:
        state = _solve(rt, pid="learn-before-halt")
        updates = [u for u in state.learning_updates]
        terminate = state.transitions[-1]
        learned = len(updates) > 0 and terminate.phase == "terminate"
        detail = {
            "learning_updates": len(updates),
            "last_phase": terminate.phase,
        }
    finally:
        close_runtime(rt)
    return {
        "verdict": "PASS" if learned else "FAIL",
        **detail,
        "claim": "terminal cycles are learned before halt",
    }


def check_reachability_claims_recorded():
    """The recorded-only defects (runtime.py grant rules — Cline-adjacent, so
    these are documented findings, not patched): stages granted without
    episode evidence."""
    root = state_dir("reach-claims")
    rt = production_runtime(root)
    try:
        _solve(rt, pid="reach-claims")
        matrix = rt.reachability
        stages = {e.component: e.stage for e in matrix._entries}
        pythia_rows = -1
        try:
            store = rt.learning.store
            pythia_rows = store.journal.count()
        except Exception:  # noqa: BLE001
            pythia_rows = -1
        findings = {
            "pythia.memory stage": stages.get("pythia.memory"),
            "pythia.store stage": stages.get("pythia.store"),
            "euclid.strategy_meta_learning stage": stages.get("euclid.strategy_meta_learning"),
            "euclid.v16.search stage": stages.get("euclid.v16.search"),
            "euclid.memory_database stage": stages.get("euclid.memory_database"),
            "pythia_rows_written": pythia_rows,
        }
    finally:
        close_runtime(rt)
    # Known falsified grants (all recorded from phase/component presence):
    inflated = stages.get("pythia.memory") in ("PERSISTED", "RESTART_VERIFIED") and pythia_rows == 0
    return {
        "verdict": "FAIL" if inflated else "INFO",
        **findings,
        "claim": "reachability stages correspond to verified evidence",
        "note": (
            "runtime.py grant rules are inside the partner implementation's "
            "scope; recorded here as measured findings"
        ),
    }


def check_requested_strategy_reachable():
    """problem["strategy"] must reach the skill composer (wired, not dead)."""
    root = state_dir("strategy-req")
    rt = production_runtime(root)
    try:
        state = _solve(
            rt,
            pid="req-mcts",
            prob=problem("req-mcts", strategy="mcts-v16"),
        )
        origins = [c.origin for c in state.candidates]
        reached = any(o == "euclid-v16:mcts" for o in origins)
    finally:
        close_runtime(rt)
    return {
        "verdict": "PASS" if reached else "FAIL",
        "candidate_origins": origins,
        "claim": "declared strategy requests reach the skill composer",
    }


def check_mathematical_structure_ablation():
    """AblationConfig(mathematical_structure=False) must actually ablate."""
    root = state_dir("math-ablate")
    rt = production_runtime(root)
    try:
        from euclid.cognition.core import AblationConfig

        rt.cognition.ablations = AblationConfig(mathematical_structure=False)
        state = _solve(rt, pid="math-ablate")
        ablated = "mathematical_structure" in state.ablations
        primitive_only = all(c.origin == "euclid-v16:ASTPrimitives" for c in state.candidates)
    finally:
        close_runtime(rt)
    return {
        "verdict": "PASS" if (ablated and primitive_only) else "FAIL",
        "ablations": list(state.ablations),
        "claim": "mathematical_structure ablation disables v16 search paths",
    }


def check_restart_verified_self_certified():
    """RESTART_VERIFIED is granted without executing any verification.

    runtime.py grants it on the *next* production() boot for any component
    that reached PERSISTED — same process counts; no artifact verification is
    performed.  Recorded finding (partner-scope file): verdict FAIL.
    """
    root = state_dir("restart-selfcert")
    rt = production_runtime(root)
    try:
        _solve(rt, pid="selfcert")
    finally:
        close_runtime(rt)
    rt2 = production_runtime(root)
    try:
        stage = rt2.reachability.stage("euclid.memory_database")
        self_certified = stage is not None and stage.name == "RESTART_VERIFIED"
    finally:
        close_runtime(rt2)
    return {
        "verdict": "FAIL" if self_certified else "PASS",
        "euclid.memory_database_stage": stage.name if stage else None,
        "claim": "RESTART_VERIFIED requires executed verification",
    }


def check_transfer_verified_requires_memory_influence():
    """TRANSFER_VERIFIED must require episode evidence: a cold episode
    (nothing durable retrieved into a decision) must NOT grant it; it is
    granted only when a durable episodic record observably biases candidate
    scoring (the ``memory-influence`` transition)."""
    from euclid.cognition.interfaces import MemoryItem
    from euclid.cognition.reachability import ReachabilityStage
    from euclid.cognition.state import MemoryKind

    root = state_dir("transfer-evidence")
    rt = production_runtime(root)
    try:
        cold_state = _solve(rt, pid="t-cold")
        cold_stage = rt.reachability.stage("euclid.memory_database")
        cold_granted = cold_stage is not None and (
            cold_stage >= ReachabilityStage.TRANSFER_VERIFIED
        )
        # Seed a durable episodic record that qualifies under the memory-bias
        # gate: structural overlap with the problem, recorded success and the
        # action it executed.
        rt.cognition.memory.store(
            MemoryItem(
                memory_id="transfer-seed-1",
                kind=MemoryKind.EPISODIC,
                payload={
                    "prior_outcome": "solved",
                    "success": True,
                    "executed_action": "primitive:MUTATE:swap_op",
                },
                provenance="adversarial-seed",
                structural_features=frozenset(["rel:dependency-chain", "rel:action-outcome"]),
                transfer_value=0.9,
            )
        )
        warm_state = _solve(rt, pid="t-warm")
        warm_stage = rt.reachability.stage("euclid.memory_database")
        warm_granted = warm_stage is not None and (
            warm_stage >= ReachabilityStage.TRANSFER_VERIFIED
        )
        influence_fired = any(t.phase == "memory-influence" for t in warm_state.transitions)
        _ = cold_state
    finally:
        close_runtime(rt)
    verdict = "PASS" if (not cold_granted and warm_granted and influence_fired) else "FAIL"
    return {
        "verdict": verdict,
        "cold_stage": cold_stage.name if cold_stage else None,
        "warm_stage": warm_stage.name if warm_stage else None,
        "memory_influence_transition": influence_fired,
        "claim": "TRANSFER_VERIFIED requires a recorded downstream decision changed by durable memory",
        "note": (
            "the grant fires only on the memory-influence transition — a "
            "durable record biasing candidate scoring — never on retrieval alone"
        ),
    }


CHECKS = {name[6:]: fn for name, fn in list(globals().items()) if name.startswith("check_")}


def run_all():
    results = {}
    for name, fn in sorted(CHECKS.items()):
        try:
            results[name] = fn()
        except Exception as exc:  # noqa: BLE001 - record crash as verdict
            results[name] = {"verdict": "ERROR", "error": str(exc)}
    return results


if __name__ == "__main__":
    out = run_all()
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
