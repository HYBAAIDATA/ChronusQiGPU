"""One governed facade over the existing PYTHIA and experience learners."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from hyba_substrate.memory_preservation import verified_atomic_json_write

from .contracts import Experience, RewardAuthority, domain_hash
from .evidence import EvidenceChain, load_json
from .memory_database import MemoryDatabase, MemoryScope

REPLAY_JOURNAL_SCHEMA = "euclid.replay-journal/1"


class LearningService:
    """Coordinates existing learners without silently manufacturing reward.

    Replay protection is durable: a replay journal (sealed JSON, written
    atomically) and/or the scoped ``MemoryDatabase`` record every applied
    ``replay_id``.  Re-recording an identical replay after restart is
    rejected before any learner mutation; a replay_id arriving with
    conflicting content fails closed the same way.
    """

    def __init__(
        self,
        *,
        pythia: Any | None = None,
        memory: Any | None = None,
        store: Any | None = None,
        experience_learner: Any | None = None,
        memory_database: MemoryDatabase | None = None,
        evidence: EvidenceChain | None = None,
        replay_journal_path: str | Path | None = None,
    ) -> None:
        self.pythia = pythia
        self.memory = memory
        self.store = store
        self.experience_learner = experience_learner
        self.memory_database = memory_database
        self.evidence = evidence or EvidenceChain()
        self.replay_journal_path = (
            Path(replay_journal_path) if replay_journal_path else None
        )
        self._seen: set[str] = set()
        self._journal: dict[str, dict[str, Any]] = {}
        self._load_journal()

    def _load_journal(self) -> None:
        if self.replay_journal_path is None:
            return
        path = self.replay_journal_path
        if not path.exists():
            return
        payload = load_json(path)
        if payload.get("schema") != REPLAY_JOURNAL_SCHEMA:
            raise ValueError("unsupported replay journal schema")
        body = {
            "schema": payload.get("schema"),
            "entries": payload.get("entries"),
        }
        if payload.get("seal") != domain_hash(
            "euclid.replay-journal.seal.v1", body
        ):
            raise ValueError("replay journal seal mismatch")
        entries = dict(body["entries"] or {})
        self._journal = entries
        self._seen.update(entries.keys())

    def _persist_journal(self) -> None:
        if self.replay_journal_path is None:
            return
        body = {
            "schema": REPLAY_JOURNAL_SCHEMA,
            "entries": self._journal,
        }
        payload = {
            **body,
            "seal": domain_hash("euclid.replay-journal.seal.v1", body),
        }
        verified_atomic_json_write(self.replay_journal_path.resolve(), payload)

    @staticmethod
    def _content_hash(experience: Experience) -> str:
        return domain_hash(
            "euclid.experience.content.v1",
            {
                "mission_id": experience.mission_id,
                "domain": experience.domain,
                "observation": dict(experience.observation),
                "action": experience.action,
                "outcome": dict(experience.outcome),
                "reward": experience.reward,
            },
        )

    def _check_replay(self, experience: Experience, digest: str) -> None:
        replay_id = experience.replay_id
        existing = self._journal.get(replay_id)
        if existing is not None:
            if existing.get("digest") != digest or existing.get(
                "content_hash"
            ) != self._content_hash(experience):
                raise ValueError(
                    "conflicting experience replay identity/content"
                )
            raise ValueError("duplicate experience replay")
        if replay_id in self._seen:
            raise ValueError("duplicate experience replay")
        if (
            self.memory_database is not None
            and self.memory_database.has_replay_id(replay_id)
        ):
            raise ValueError("duplicate experience replay")

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

    def _mark_replay(self, experience: Experience, digest: str) -> None:
        self._journal[experience.replay_id] = {
            "digest": digest,
            "content_hash": self._content_hash(experience),
            "recorded_at": time.time(),
        }
        self._persist_journal()
        self._seen.add(experience.replay_id)

    def record(self, experience: Experience) -> str:
        digest = experience.digest()
        self._check_replay(experience, digest)
        if experience.reward_authority is RewardAuthority.NONE:
            self._persist_experience(experience)
            self.evidence.append(
                "experience-observed",
                {"digest": digest, "reward_applied": False, "domain": experience.domain},
            )
            self._mark_replay(experience, digest)
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
        self._mark_replay(experience, digest)
        self.evidence.append(
            "experience-learned",
            {"digest": digest, "engines": applied, "reward_applied": True},
        )
        return digest

    def replay_state(self) -> dict[str, Any]:
        """Durable dedup/watermark state for checkpoint manifests."""
        state: dict[str, Any] = {
            "journal_entries": len(self._journal),
            "process_replay_ids": len(self._seen),
            "replay_journal_path": (
                str(self.replay_journal_path) if self.replay_journal_path else None
            ),
            "journal_sha256": None,
            "durable": self.replay_journal_path is not None
            or self.memory_database is not None,
        }
        if self.replay_journal_path is not None and self.replay_journal_path.is_file():
            state["journal_sha256"] = hashlib.sha256(
                self.replay_journal_path.read_bytes()
            ).hexdigest()
        if self.memory_database is not None:
            verification = self.memory_database.verify()
            state["memory_database"] = {
                "valid": bool(verification.get("valid")),
                "memories": verification.get("memories"),
                "event_chain_head": verification.get("event_chain_head"),
            }
        else:
            state["memory_database"] = None
        return state

    def status(self) -> dict[str, Any]:
        replay = self.replay_state()
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
            "replay_journal": {
                "path": replay["replay_journal_path"],
                "entries": replay["journal_entries"],
                "durable_replay_protection": replay["durable"],
            },
            "evidence_head": self.evidence.head,
        }
