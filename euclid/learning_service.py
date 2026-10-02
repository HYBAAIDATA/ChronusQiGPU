"""One governed facade over the existing PYTHIA and experience learners."""
from __future__ import annotations

import hashlib
from typing import Any

from .contracts import Experience, RewardAuthority, canonical_json
from .evidence import EvidenceChain
from .memory_database import MemoryDatabase, MemoryScope


class LearningService:
    """Coordinates existing learners without silently manufacturing reward."""

    def __init__(
        self,
        *,
        pythia: Any | None = None,
        memory: Any | None = None,
        store: Any | None = None,
        experience_learner: Any | None = None,
        memory_database: MemoryDatabase | None = None,
        evidence: EvidenceChain | None = None,
    ) -> None:
        self.pythia = pythia
        self.memory = memory
        self.store = store
        self.experience_learner = experience_learner
        self.memory_database = memory_database
        self.evidence = evidence or EvidenceChain()
        self._seen: set[str] = set()

    def _persist_experience(self, experience: Experience) -> None:
        if self.memory_database is None:
            return
        self.memory_database.put(
            scope=MemoryScope("local", experience.mission_id, experience.domain),
            tier="episodic",
            content={
                "observation": dict(experience.observation),
                "action": experience.action,
                "outcome": dict(experience.outcome),
                "reward": experience.reward,
            },
            provenance=experience.provenance,
            reward_authority=experience.reward_authority,
            uncertainty=experience.uncertainty,
            replay_id=experience.replay_id,
            memory_id=experience.experience_id,
        )

    def record(self, experience: Experience) -> str:
        digest = experience.digest()
        if experience.replay_id in self._seen:
            raise ValueError("duplicate experience replay")
        if (
            self.memory_database is not None
            and self.memory_database.has_replay_id(experience.replay_id)
        ):
            raise ValueError("duplicate experience replay")
        if experience.reward_authority is RewardAuthority.NONE:
            self._persist_experience(experience)
            self.evidence.append(
                "experience-observed",
                {"digest": digest, "reward_applied": False, "domain": experience.domain},
            )
            self._seen.add(experience.replay_id)
            return digest

        applied: list[str] = []
        if self.experience_learner is not None:
            task = experience.domain
            actions = tuple(getattr(self.experience_learner.tasks.get(task), "actions", ()))
            if not actions:
                self.experience_learner.register_task(
                    task, (experience.action,), reward_range=(-1.0, 1.0)
                )
            elif experience.action not in actions:
                raise ValueError("experience action is outside registered task contract")
            self.experience_learner.observe(
                task,
                dict(experience.observation),
                experience.action,
                float(experience.reward),
                dict(experience.outcome),
                metadata={
                    "provenance": experience.provenance,
                    "replay_id": experience.replay_id,
                    "reward_authority": experience.reward_authority.value,
                },
            )
            applied.append("experience-superlearner")

        if self.store is not None and hasattr(self.store, "record_run"):
            self.store.record_run("governed-experience", {
                "digest": digest, "domain": experience.domain,
                "reward_authority": experience.reward_authority.value,
                "uncertainty": experience.uncertainty,
            })
            applied.append("pythia-store")

        self._persist_experience(experience)
        self._seen.add(experience.replay_id)
        self.evidence.append(
            "experience-learned",
            {"digest": digest, "engines": applied, "reward_applied": True},
        )
        return digest

    def status(self) -> dict[str, Any]:
        return {
            "schema": "euclid.learning-service/1",
            "engines": {
                "pythia": self.pythia is not None,
                "memory": self.memory is not None,
                "store": self.store is not None,
                "experience_superlearner": self.experience_learner is not None,
                "durable_memory_database": self.memory_database is not None,
            },
            "experiences_seen": len(self._seen),
            "evidence_head": self.evidence.head,
        }
