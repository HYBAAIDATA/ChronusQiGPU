"""EUCLID composition root: the only supported general runtime startup."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .contracts import domain_hash
from .evidence import EvidenceChain, atomic_write, load_json
from .governance import Delegator, Organ, OrganRegistry
from .kairos_runtime import KairosRuntime, World
from .learning_service import LearningService
from .memory_database import MemoryDatabase
from .rights import RightsLedger


class EuclidRuntime:
    def __init__(
        self,
        *,
        creator_id: str,
        state_dir: str | Path,
        pythia: Any | None = None,
        memory: Any | None = None,
        store: Any | None = None,
        experience_learner: Any | None = None,
        memory_database: MemoryDatabase | None = None,
    ) -> None:
        self.creator_id = creator_id
        self.state_dir = Path(state_dir)
        self.evidence = EvidenceChain()
        self.registry = OrganRegistry()
        self.rights = RightsLedger(creator_id, self.evidence)
        self.delegator = Delegator(self.registry, self.evidence, self.rights)
        self.learning = LearningService(
            pythia=pythia,
            memory=memory,
            store=store,
            experience_learner=experience_learner,
            memory_database=memory_database,
            evidence=self.evidence,
        )
        self.kairos = KairosRuntime(creator_id, self.evidence)

    @classmethod
    def production(
        cls,
        *,
        creator_id: str,
        state_dir: str | Path,
        pythia: Any | None = None,
        memory: Any | None = None,
        store: Any | None = None,
        experience_learner: Any | None = None,
    ) -> "EuclidRuntime":
        root = Path(state_dir)
        root.mkdir(parents=True, exist_ok=True)
        database = MemoryDatabase(root / "euclid_memory.sqlite3")
        return cls(
            creator_id=creator_id,
            state_dir=root,
            pythia=pythia,
            memory=memory,
            store=store,
            experience_learner=experience_learner,
            memory_database=database,
        )

    def register_organ(self, organ: Organ) -> None:
        self.registry.register(organ)
        self.evidence.append("organ-registered", {
            "organ_id": organ.organ_id,
            "capabilities": sorted(organ.capabilities),
            "authority": organ.authority.value,
        })

    def close(self) -> None:
        database = self.learning.memory_database
        if database is not None:
            database.close()

    def startup_report(self) -> dict[str, Any]:
        return {
            "schema": "euclid.startup/1",
            "creator_id": self.creator_id,
            "network_enabled": False,
            "federation_enabled": False,
            "multi_user_enabled": False,
            "organs": self.registry.report(),
            "learning": self.learning.status(),
            "authority_boundary": {
                "mining": "HOLD/REDUCE/RESTORE dispatch breadth only",
                "forbidden": [
                    "bitcoin-header", "nonce-semantics", "sha256d", "target",
                    "credentials", "share-validation", "submission",
                    "pool-acknowledgement",
                ],
            },
            "evidence_head": self.evidence.head,
            "memory_database": (
                self.learning.memory_database.verify()
                if self.learning.memory_database is not None
                else {"valid": False, "reason": "not configured"}
            ),
        }

    def snapshot(self) -> dict[str, Any]:
        body = {
            "schema": "euclid.runtime-checkpoint/1",
            "creator_id": self.creator_id,
            "worlds": {
                key: {
                    "world_id": world.world_id,
                    "creator_id": world.creator_id,
                    "state": world.state,
                    "revision": world.revision,
                    "active": world.active,
                }
                for key, world in sorted(self.kairos.worlds.items())
            },
            "rights": self.rights.snapshot(),
            "evidence": self.evidence.to_payload(),
        }
        return {**body, "seal": domain_hash("euclid.runtime-checkpoint.seal.v1", body)}

    def save(self, path: str | Path) -> None:
        atomic_write(Path(path), self.snapshot())

    @classmethod
    def restore(cls, path: str | Path, *, state_dir: str | Path) -> "EuclidRuntime":
        payload = load_json(Path(path))
        body = {
            "schema": payload.get("schema"),
            "creator_id": payload.get("creator_id"),
            "worlds": payload.get("worlds", {}),
            "rights": payload.get("rights"),
            "evidence": payload.get("evidence"),
        }
        if body["schema"] != "euclid.runtime-checkpoint/1":
            raise ValueError("unsupported EUCLID runtime checkpoint schema")
        if payload.get("seal") != domain_hash("euclid.runtime-checkpoint.seal.v1", body):
            raise ValueError("EUCLID runtime checkpoint seal mismatch")
        runtime = cls(creator_id=str(body["creator_id"]), state_dir=state_dir)
        runtime.evidence = EvidenceChain.from_payload(body["evidence"])
        runtime.kairos = KairosRuntime(runtime.creator_id, runtime.evidence)
        runtime.kairos.worlds = {
            key: World(**value) for key, value in dict(body["worlds"]).items()
        }
        runtime.rights = RightsLedger.restore(
            runtime.evidence,
            dict(body["rights"]),
            creator_id=runtime.creator_id,
        )
        if runtime.rights.creator_id != runtime.creator_id:
            raise ValueError("rights creator differs from runtime creator")
        runtime.registry = OrganRegistry()
        runtime.delegator = Delegator(
            runtime.registry, runtime.evidence, runtime.rights
        )
        runtime.learning.evidence = runtime.evidence
        runtime.kairos.replay_verify()
        return runtime
