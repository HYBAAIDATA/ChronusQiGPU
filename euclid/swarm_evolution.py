"""EUCLID governed agent-swarm activation and execution.

The activating agent is the leader only if its *own* leadership capabilities
were already promoted by the independently attested capability registry.
No skill promotion, model training, authority inheritance, remote spawning,
or external side effects occur inside this module.

Runtime execution remains host-owned. Caller-supplied executors must implement
their own authorization at the action boundary; this scheduler only reduces
(not expands) the set of tasks they may receive.
"""
from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from euclid.capability_qualification import CapabilityQualificationRegistry

LEADER_SKILLS = frozenset({
    "swarm.plan", "swarm.delegate", "swarm.verify",
    "swarm.recover", "swarm.budget",
})
MAX_TASKS = 32
MAX_AGENTS = 16
MAX_BUDGET_UNITS = 1_000_000
MAX_RESULT_BYTES = 65536


class SwarmRefused(PermissionError):
    """Activation or execution lacks a mandatory authority or invariant."""


@dataclass(frozen=True)
class VerificationAttestation:
    verifier_id: str
    signature: str


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise SwarmRefused("non-JSON or non-finite data") from exc


def _text(value: Any, name: str) -> str:
    if type(value) is not str or not 1 <= len(value) <= 128 or not value.isascii() \
            or not all(c.isalnum() or c in "._:-" for c in value):
        raise SwarmRefused(f"invalid {name}")
    return value


def verification_payload(
    mission: "SwarmMission", task: "SwarmTask", result: Mapping[str, Any]
) -> bytes:
    """Canonical body that a separately trusted verifier must sign."""
    return _canonical({
        "mission_id": mission.mission_id,
        "scope": mission.scope,
        "task_id": task.task_id,
        "agent_id": task.agent_id,
        "required_skill": task.required_skill,
        "result_sha256": hashlib.sha256(_canonical(dict(result))).hexdigest(),
    })


def _positive(value: Any, name: str, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise SwarmRefused(f"{name} must be a bounded positive integer")
    return value


@dataclass(frozen=True)
class QualifiedAgent:
    agent_id: str
    source_revision: str
    mission_scope: str
    skills: tuple[str, ...]
    capability_claims: Mapping[str, str]

    def __post_init__(self) -> None:
        _text(self.agent_id, "agent_id")
        _text(self.mission_scope, "mission_scope")
        if type(self.source_revision) is not str or len(self.source_revision) != 40 \
                or any(c not in "0123456789abcdef" for c in self.source_revision):
            raise SwarmRefused("agent source_revision must be a 40-character Git SHA")
        if type(self.skills) is not tuple or not self.skills or len(self.skills) > 32 \
                or len(set(self.skills)) != len(self.skills):
            raise SwarmRefused("unique, nonempty agent skills required")
        for skill in self.skills:
            _text(skill, "skill")
            if skill not in self.capability_claims:
                raise SwarmRefused("each skill needs a qualification claim")
            _text(self.capability_claims[skill], "claim_id")


@dataclass(frozen=True)
class SwarmTask:
    task_id: str
    agent_id: str
    required_skill: str
    budget_units: int
    dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.task_id, "task_id")
        _text(self.agent_id, "agent_id")
        _text(self.required_skill, "required_skill")
        _positive(self.budget_units, "task budget", MAX_BUDGET_UNITS)
        if type(self.dependencies) is not tuple or len(set(self.dependencies)) != len(self.dependencies):
            raise SwarmRefused("dependencies must be unique tuples")
        for dep in self.dependencies:
            _text(dep, "dependency")


@dataclass(frozen=True)
class SwarmMission:
    mission_id: str
    leader_id: str
    scope: str
    budget_units: int
    deadline_ns: int
    tasks: tuple[SwarmTask, ...]

    def __post_init__(self) -> None:
        _text(self.mission_id, "mission_id")
        _text(self.leader_id, "leader_id")
        _text(self.scope, "scope")
        _positive(self.budget_units, "mission budget", MAX_BUDGET_UNITS)
        _positive(self.deadline_ns, "deadline_ns", 2**63 - 1)
        if type(self.tasks) is not tuple or not 1 <= len(self.tasks) <= MAX_TASKS:
            raise SwarmRefused("mission needs 1 to 32 tasks")
        if any(type(t) is not SwarmTask for t in self.tasks):
            raise SwarmRefused("mission requires validated SwarmTask instances")
        ids = {t.task_id for t in self.tasks}
        if len(ids) != len(self.tasks):
            raise SwarmRefused("duplicate task identifiers")
        if sum(t.budget_units for t in self.tasks) > self.budget_units:
            raise SwarmRefused("aggregate task budgets exceed mission budget")
        if len({t.agent_id for t in self.tasks} | {self.leader_id}) > MAX_AGENTS:
            raise SwarmRefused("too many agents")
        if any(t.task_id in t.dependencies or not set(t.dependencies) <= ids for t in self.tasks):
            raise SwarmRefused("invalid dependency reference")
        # Deterministic topological cycle rejection before any execution.
        pending = {t.task_id: set(t.dependencies) for t in self.tasks}
        completed: set[str] = set()
        while pending:
            ready = [key for key, deps in pending.items() if deps <= completed]
            if not ready:
                raise SwarmRefused("cyclic task dependencies")
            for key in ready:
                completed.add(key)
                del pending[key]


class SwarmJournal:
    """SQLite WAL execution journal; unique mission IDs prevent replay on restart.

    Mission admission and event recording use transactional writes. A crashed
    mission remains non-replayable until separately reconciled by an operator.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if not self.path or self.path == ":memory:":
            raise SwarmRefused("swarm journal must be durable")
        parent = Path(self.path).resolve().parent
        if not parent.is_dir():
            raise SwarmRefused("journal parent must exist")
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, timeout=10, check_same_thread=False, isolation_level=None)
        mode = self._db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        if mode.lower() != "wal":
            self._db.close()
            raise SwarmRefused("journal requires SQLite WAL mode")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS missions ("
            "id TEXT PRIMARY KEY, digest TEXT NOT NULL, status TEXT NOT NULL, "
            "event_count INTEGER NOT NULL DEFAULT 0, event_head TEXT NOT NULL DEFAULT '')"
        )
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(missions)")}
        if "event_count" not in columns:
            self._db.execute(
                "ALTER TABLE missions ADD COLUMN event_count INTEGER NOT NULL DEFAULT 0"
            )
        if "event_head" not in columns:
            self._db.execute(
                "ALTER TABLE missions ADD COLUMN event_head TEXT NOT NULL DEFAULT ''"
            )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS events (mission_id TEXT NOT NULL, "
            "seq INTEGER NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL, "
            "payload TEXT NOT NULL, PRIMARY KEY(mission_id,seq))"
        )

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def admit(self, mission: SwarmMission) -> None:
        data = {
            "mission_id": mission.mission_id, "leader": mission.leader_id,
            "scope": mission.scope, "budget": mission.budget_units,
            "deadline_ns": mission.deadline_ns,
            "tasks": [
                {"task": t.task_id, "agent": t.agent_id,
                 "skill": t.required_skill, "budget": t.budget_units,
                 "dependencies": list(t.dependencies)} for t in mission.tasks
            ],
        }
        digest = hashlib.sha256(_canonical(data)).hexdigest()
        with self._lock:
            try:
                self._db.execute("BEGIN IMMEDIATE")
                self._db.execute(
                    "INSERT INTO missions(id,digest,status) VALUES(?,?,'running')",
                    (mission.mission_id, digest),
                )
                self._db.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                self._db.execute("ROLLBACK")
                raise SwarmRefused("mission replay or duplicate activation") from exc
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    def append(self, mission_id: str, event: Mapping[str, Any]) -> str:
        _text(mission_id, "mission_id")
        data = _canonical(dict(event))
        if len(data) > MAX_RESULT_BYTES:
            raise SwarmRefused("journal event exceeds maximum size")
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                mission_row = self._db.execute(
                    "SELECT status FROM missions WHERE id=?", (mission_id,)
                ).fetchone()
                if mission_row is None or mission_row[0] != "running":
                    raise SwarmRefused("mission is not in running state")
                previous_row = self._db.execute(
                    "SELECT seq,hash FROM events WHERE mission_id=? ORDER BY seq DESC LIMIT 1",
                    (mission_id,),
                ).fetchone()
                seq = previous_row[0] + 1 if previous_row else 1
                previous = previous_row[1] if previous_row else "0" * 64
                digest = hashlib.sha256(
                    _canonical({"mission": mission_id, "seq": seq,
                                "previous": previous, "payload": json.loads(data)})
                ).hexdigest()
                self._db.execute(
                    "INSERT INTO events VALUES(?,?,?,?,?)",
                    (mission_id, seq, previous, digest, data.decode("utf-8")),
                )
                self._db.execute("UPDATE missions SET event_count=?, event_head=? WHERE id=?", (seq, digest, mission_id))
                self._db.execute("COMMIT")
                return digest
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    def finish(self, mission_id: str, status: str) -> None:
        if status not in {"completed", "failed"}:
            raise SwarmRefused("invalid terminal status")
        with self._lock:
            changed = self._db.execute(
                "UPDATE missions SET status=? WHERE id=? AND status='running'",
                (status, mission_id),
            ).rowcount
            if changed != 1:
                raise SwarmRefused("mission terminal state not available")

    def verify(self, mission_id: str) -> bool:
        with self._lock:
            rows = self._db.execute(
                "SELECT seq,previous,hash,payload FROM events WHERE mission_id=? ORDER BY seq",
                (mission_id,),
            ).fetchall()
        mission_row = self._db.execute("SELECT status,event_count,event_head FROM missions WHERE id=?", (mission_id,)).fetchone()
        if mission_row is None or not rows or len(rows) != mission_row[1]:
            return False
        previous = "0" * 64
        for expected, (seq, prev, digest, payload) in enumerate(rows, start=1):
            try:
                data = json.loads(payload)
                computed = hashlib.sha256(
                    _canonical({"mission": mission_id, "seq": seq,
                                "previous": previous, "payload": data})
                ).hexdigest()
            except (TypeError, ValueError, SwarmRefused):
                return False
            if seq != expected or prev != previous or digest != computed:
                return False
            previous = digest
        if previous != mission_row[2]:
            return False
        if mission_row[0] in {"completed", "failed"}:
            return json.loads(rows[-1][3]).get("kind") == mission_row[0]
        return mission_row[0] == "running"


class SwarmActivator:
    """Fail-closed leadership qualification, scoped dispatch and verification.

    Independent, signed training/acceptance evidence must have been promoted
    into CapabilityQualificationRegistry before any skills become available.
    """

    def __init__(
        self,
        *,
        qualification: CapabilityQualificationRegistry,
        journal: SwarmJournal,
        agents: Sequence[QualifiedAgent],
        clock_ns: Callable[[], int] = time.time_ns,
    ) -> None:
        if not isinstance(qualification, CapabilityQualificationRegistry):
            raise SwarmRefused("signed capability qualification registry required")
        self.qualification = qualification
        self.journal = journal
        self.clock_ns = clock_ns
        self.agents = {agent.agent_id: agent for agent in agents}
        if len(self.agents) != len(agents):
            raise SwarmRefused("duplicate agent identities")

    def _authorize(self, agent: QualifiedAgent, skill: str, scope: str) -> None:
        if agent.mission_scope != scope or skill not in agent.skills:
            raise SwarmRefused("skill not acquired for mission scope")
        claim_id = agent.capability_claims.get(skill)
        if not claim_id:
            raise SwarmRefused("missing acquired skill certificate")
        if claim_id != f"{agent.agent_id}.{skill}":
            raise SwarmRefused("qualification claim is not bound to the agent identity")
        try:
            self.qualification.authorize(
                claim_id=claim_id, source_revision=agent.source_revision,
                domain="euclid.agent.skill", task_scope=scope, authority=skill,
            )
        except PermissionError as exc:
            raise SwarmRefused("skill has no independently promoted qualification") from exc

    def activate(
        self,
        mission: SwarmMission,
        *,
        dispatch: Callable[[SwarmTask], Mapping[str, Any]],
        verify: Callable[[SwarmMission, SwarmTask, Mapping[str, Any]], VerificationAttestation],
    ) -> dict[str, Any]:
        """Activate one bounded swarm; never report completion without verified tasks.

        The host dispatch function must enforce AL HARAS action-time policy,
        sandboxing, deadlines and cancellation for its own external effects.
        """
        now = self.clock_ns()
        if type(now) is not int or now >= mission.deadline_ns:
            raise SwarmRefused("mission deadline expired")
        leader = self.agents.get(mission.leader_id)
        if leader is None:
            raise SwarmRefused("unknown swarm leader")
        # Leader skills must already be acquired, all together, before dispatch.
        for skill in sorted(LEADER_SKILLS):
            self._authorize(leader, skill, mission.scope)
        for task in mission.tasks:
            agent = self.agents.get(task.agent_id)
            if agent is None:
                raise SwarmRefused("unknown worker agent")
            self._authorize(agent, task.required_skill, mission.scope)
        if not callable(dispatch) or not callable(verify):
            raise SwarmRefused("authorized dispatcher and trusted verifier required")

        self.journal.admit(mission)
        consumed = 0
        completed: set[str] = set()
        outcomes: dict[str, Any] = {}
        try:
            self.journal.append(mission.mission_id, {
                "kind": "activated", "leader": leader.agent_id,
                "acquired_leadership_skills": sorted(LEADER_SKILLS),
                "source_revision": leader.source_revision,
            })
            remaining = {task.task_id: task for task in mission.tasks}
            while remaining:
                ready = sorted(
                    (task for task in remaining.values()
                     if set(task.dependencies) <= completed),
                    key=lambda task: task.task_id,
                )
                if not ready:
                    raise SwarmRefused("dependencies cannot be satisfied")
                for task in ready:
                    if self.clock_ns() >= mission.deadline_ns:
                        raise SwarmRefused("mission deadline exceeded")
                    # Recheck at dispatch to make revocation effective mid-swarm.
                    for leadership_skill in sorted(LEADER_SKILLS):
                        self._authorize(leader, leadership_skill, mission.scope)
                    self._authorize(self.agents[task.agent_id], task.required_skill, mission.scope)
                    if consumed + task.budget_units > mission.budget_units:
                        raise SwarmRefused("mission budget exceeded")
                    consumed += task.budget_units  # reserve before dispatch
                    self.journal.append(mission.mission_id, {
                        "kind": "dispatch", "task": task.task_id, "agent": task.agent_id,
                        "reserved_units": task.budget_units, "spent_upper_bound": consumed,
                    })
                    if self.clock_ns() >= mission.deadline_ns:
                        raise SwarmRefused("mission deadline exceeded before dispatch")
                    result = dispatch(task)
                    if not isinstance(result, Mapping) or len(_canonical(dict(result))) > MAX_RESULT_BYTES:
                        raise SwarmRefused("unbounded or invalid worker result")
                    self._authorize(leader, "swarm.verify", mission.scope)
                    result_snapshot = json.loads(_canonical(dict(result)))
                    attestation = verify(
                        mission, task, deepcopy(result_snapshot)
                    )
                    if type(attestation) is not VerificationAttestation:
                        raise SwarmRefused("trusted verification attestation required")
                    self.qualification.verify_attestation(
                        verifier_id=attestation.verifier_id,
                        payload=verification_payload(mission, task, result_snapshot),
                        signature=attestation.signature,
                    )
                    if self.clock_ns() >= mission.deadline_ns:
                        raise SwarmRefused("mission deadline exceeded after verification")
                    self.journal.append(mission.mission_id, {
                        "kind": "verified", "task": task.task_id,
                        "output_sha256": hashlib.sha256(_canonical(result_snapshot)).hexdigest(),
                    })
                    completed.add(task.task_id)
                    outcomes[task.task_id] = result_snapshot
                    del remaining[task.task_id]
            if self.clock_ns() >= mission.deadline_ns:
                raise SwarmRefused("mission deadline exceeded before completion")
            self.journal.append(mission.mission_id, {
                "kind": "completed", "verified_tasks": sorted(completed),
                "reserved_budget_units": consumed,
            })
            self.journal.finish(mission.mission_id, "completed")
            return {
                "status": "completed", "mission_id": mission.mission_id,
                "leader_id": leader.agent_id, "verified_tasks": sorted(completed),
                "reserved_budget_units": consumed,
                "journal_verified": self.journal.verify(mission.mission_id),
                "outcomes": outcomes,
            }
        except BaseException:
            # Preserve the originating exception if the journal itself is unavailable.
            try:
                self.journal.append(mission.mission_id, {
                    "kind": "failed", "verified_tasks": sorted(completed),
                    "reserved_budget_units": consumed,
                })
                self.journal.finish(mission.mission_id, "failed")
            except Exception:
                pass
            raise
