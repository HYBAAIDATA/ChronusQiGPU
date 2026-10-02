"""Deterministic, single-operator, local Kairos world runtime."""
from __future__ import annotations

import copy
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from .contracts import domain_hash
from .evidence import EvidenceChain, atomic_write, load_json


class Role(str, Enum):
    CREATOR = "creator"
    OPERATOR = "operator"
    OBSERVER = "observer"


@dataclass(frozen=True)
class Session:
    session_id: str
    actor_id: str
    role: Role


@dataclass
class World:
    world_id: str
    creator_id: str
    state: dict[str, Any] = field(default_factory=dict)
    revision: int = 0
    active: bool = True


class KairosRuntime:
    def __init__(self, creator_id: str, evidence: EvidenceChain | None = None) -> None:
        if not creator_id:
            raise ValueError("creator_id is required")
        self.creator_id = creator_id
        self.evidence = evidence or EvidenceChain()
        self.session: Session | None = None
        self.worlds: dict[str, World] = {}

    def open_session(self, actor_id: str, role: Role) -> Session:
        if self.session is not None:
            raise RuntimeError("exactly one active operator session is permitted")
        if role is Role.CREATOR and actor_id != self.creator_id:
            raise PermissionError("creator identity mismatch")
        self.session = Session(uuid.uuid4().hex, actor_id, role)
        self.evidence.append("session-opened", asdict(self.session))
        return self.session

    def close_session(self) -> None:
        if self.session is None:
            raise RuntimeError("no active session")
        self.evidence.append("session-closed", asdict(self.session))
        self.session = None

    def _require_mutation(self) -> Session:
        if self.session is None:
            raise PermissionError("an active session is required")
        if self.session.role not in (Role.CREATOR, Role.OPERATOR):
            raise PermissionError("observer cannot mutate world state")
        return self.session

    def create_world(self, world_id: str, initial: Mapping[str, Any] | None = None) -> World:
        self._require_mutation()
        if not world_id or world_id in self.worlds:
            raise ValueError("world_id must be new and non-empty")
        world = World(world_id, self.creator_id, copy.deepcopy(dict(initial or {})))
        self.worlds[world_id] = world
        self.evidence.append("world-created", {"world": asdict(world)})
        return world

    def dispatch(self, command: Mapping[str, Any]) -> dict[str, Any]:
        session = self._require_mutation()
        allowed = {"schema", "world_id", "op", "key", "value"}
        if set(command) - allowed or command.get("schema") != "kairos.command/1":
            raise ValueError("invalid command schema")
        world_id, operation = command.get("world_id"), command.get("op")
        if world_id not in self.worlds:
            raise ValueError("unknown world")
        world = self.worlds[world_id]
        if not world.active:
            raise RuntimeError("world is inactive")
        before = copy.deepcopy(world.state)
        if operation == "set":
            key = command.get("key")
            if not isinstance(key, str) or not key:
                raise ValueError("set requires a non-empty string key")
            world.state[key] = copy.deepcopy(command.get("value"))
        elif operation == "delete":
            key = command.get("key")
            if not isinstance(key, str) or key not in world.state:
                raise ValueError("delete requires an existing key")
            del world.state[key]
        elif operation == "deactivate":
            world.active = False
        else:
            raise ValueError("unsupported operation")
        world.revision += 1
        payload = {
            "session_id": session.session_id,
            "command": dict(command),
            "before": before,
            "after": copy.deepcopy(world.state),
            "revision": world.revision,
            "active": world.active,
        }
        self.evidence.append("world-command", payload)
        return payload

    def snapshot(self) -> dict[str, Any]:
        body = {
            "schema": "kairos.checkpoint/1",
            "creator_id": self.creator_id,
            "worlds": {key: asdict(value) for key, value in sorted(self.worlds.items())},
            "evidence": self.evidence.to_payload(),
        }
        return {**body, "seal": domain_hash("kairos.checkpoint.seal.v1", body)}

    def save(self, path: Path) -> None:
        atomic_write(Path(path), self.snapshot())

    @classmethod
    def restore(cls, path: Path) -> "KairosRuntime":
        payload = load_json(Path(path))
        body = {
            "schema": payload.get("schema"),
            "creator_id": payload.get("creator_id"),
            "worlds": payload.get("worlds", {}),
            "evidence": payload.get("evidence"),
        }
        if body["schema"] != "kairos.checkpoint/1":
            raise ValueError("unsupported Kairos checkpoint schema")
        if payload.get("seal") != domain_hash("kairos.checkpoint.seal.v1", body):
            raise ValueError("Kairos checkpoint seal mismatch")
        evidence = EvidenceChain.from_payload(body["evidence"])
        runtime = cls(str(body["creator_id"]), evidence)
        runtime.worlds = {
            key: World(**value) for key, value in dict(body["worlds"]).items()
        }
        return runtime

    def replay_verify(self) -> bool:
        self.evidence.verify()
        expected: dict[str, dict[str, Any]] = {}
        for record in self.evidence.records:
            if record.kind == "world-created":
                world = dict(record.payload["world"])
                expected[world["world_id"]] = dict(world["state"])
            elif record.kind == "world-command":
                command = dict(record.payload["command"])
                world_id = command["world_id"]
                if expected.get(world_id) != dict(record.payload["before"]):
                    raise ValueError("non-deterministic world replay")
                expected[world_id] = dict(record.payload["after"])
        actual = {key: world.state for key, world in self.worlds.items()}
        if expected != actual:
            raise ValueError("checkpoint state differs from replay")
        return True
