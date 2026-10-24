"""One governed facade over the existing PYTHIA and experience learners."""
from __future__ import annotations

import hashlib
from dataclasses import asdict
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
        governed_learning: Any | None = None,
        memory_database: MemoryDatabase | None = None,
        evidence: EvidenceChain | None = None,
        replay_journal_path: str | Path | None = None,
    ) -> None:
        self.pythia = pythia
        self.memory = memory
        self.store = store
        self.experience_learner = experience_learner
        self.governed_learning = governed_learning
        if experience_learner is not None and governed_learning is not None:
            existing = getattr(experience_learner, "learning_system", None)
            if existing is not None and existing is not governed_learning:
                raise ValueError("experience learner is attached to a different governed ledger")
            experience_learner.learning_system = governed_learning
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
            if existing.get("status") == "pending":
                raise ValueError("incomplete experience replay requires operator reconciliation")
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
            "status": "committed",
        }
        self._persist_journal()
        self._seen.add(experience.replay_id)

    def _pattern(self, experience: Experience) -> Any | None:
        """Only explicit numeric features enter PYTHIA; hashes are not features.

        Never infer mining success from a reward, an acceptance-shaped key,
        or a synthetic training score.
        """
        raw = experience.observation.get("learning_pattern")
        if raw is None or self.pythia is None:
            return None
        import numpy as np

        pattern = np.asarray(raw, dtype=float)
        if pattern.ndim != 1 or len(pattern) != int(self.pythia.n) or not np.isfinite(pattern).all():
            raise ValueError("learning_pattern must be a finite vector matching PYTHIA units")
        if "mining_success" in experience.outcome and not isinstance(experience.outcome["mining_success"], bool):
            raise ValueError("mining_success must be an explicit boolean")
        return pattern

    def _reserve(self, experience: Experience, digest: str) -> None:
        # Durable intent precedes every learner mutation. A crash/failure leaves
        # a pending entry: retry is blocked rather than applying reward twice.
        # This is fail-closed partial-application handling, not a distributed
        # transaction or an automatic claim of exactly-once completion.
        self._journal[experience.replay_id] = {
            "digest": digest, "content_hash": self._content_hash(experience),
            "recorded_at": time.time(), "status": "pending",
        }
        self._persist_journal()
        self._seen.add(experience.replay_id)

    def record(self, experience: Experience) -> str:
        digest = experience.digest()
        self._check_replay(experience, digest)
        pattern = self._pattern(experience)
        learner = self.experience_learner
        authorized = experience.reward_authority is not RewardAuthority.NONE
        if authorized and learner is not None:
            task = learner.tasks.get(experience.domain)
            low, high = (task.reward_min, task.reward_max) if task else (-1.0, 1.0)
            if not low <= float(experience.reward) <= high:
                raise ValueError("reward is outside registered task contract")
        self._reserve(experience, digest)
        applied: list[str] = []
        try:
            if authorized and learner is not None:
                task = experience.domain
                actions = tuple(getattr(learner.tasks.get(task), "actions", ()))
                if not actions:
                    learner.register_task(task, (experience.action,), reward_range=(-1.0, 1.0))
                elif experience.action not in actions:
                    if not hasattr(learner, "extend_task_actions"):
                        raise ValueError("experience action is outside registered task contract")
                    learner.extend_task_actions(task, (experience.action,))
                learner.observe(
                    task, dict(experience.observation), experience.action,
                    float(experience.reward),
                    dict(experience.outcome.get("next_state", experience.outcome)),
                    done=bool(experience.outcome.get("done", False)),
                    metadata={"provenance": experience.provenance,
                              "replay_id": experience.replay_id,
                              "reward_authority": experience.reward_authority.value},
                )
                applied.append("experience-superlearner")
            if authorized and pattern is not None:
                measured_mining = None
                if (experience.reward_authority is RewardAuthority.MEASURED_ENVIRONMENT
                        and "mining" in experience.domain.lower()
                        and "mining_success" in experience.outcome):
                    measured_mining = experience.outcome["mining_success"]
                self.pythia.learn(pattern, mining_success=measured_mining)
                applied.append("pythia")
            if self.memory is not None and hasattr(self.memory, "episodic"):
                self.memory.episodic.record(
                    trigger=experience.domain, plan=[experience.action], tool_calls=[],
                    outcome={**dict(experience.outcome), "observation": dict(experience.observation),
                             "provenance": experience.provenance, "replay_id": experience.replay_id,
                             "reward_authority": experience.reward_authority.value,
                             "reward_observed": experience.reward},
                    # Legacy episodic API requires a number. Authority and null
                    # reward remain in the exact outcome and durable database.
                    reward=float(experience.reward) if authorized else 0.0,
                )
                applied.append("pythia-memory")
            # The superlearner writes its own procedural event to this ledger.
            # Observations and memory-only authorized events still need lineage.
            if self.governed_learning is not None and not (authorized and learner is not None):
                from hyba_substrate.euclid_learning_system import MemoryKind

                self.governed_learning.record_experience(
                    domain=experience.domain, memory_kind=MemoryKind.EPISODIC,
                    observation=dict(experience.observation), prediction=None,
                    action=experience.action, outcome=dict(experience.outcome),
                    uncertainty=experience.uncertainty,
                    metadata={"provenance": experience.provenance,
                              "replay_id": experience.replay_id,
                              "reward_authority": experience.reward_authority.value},
                )
            self._persist_experience(experience)
            if self.store is not None and hasattr(self.store, "record_run"):
                self.store.record_run("governed-experience", {
                    "digest": digest, "domain": experience.domain,
                    "reward_authority": experience.reward_authority.value,
                    "uncertainty": experience.uncertainty, "engines": applied,
                })
                # Persist every accepted step, not just an autosave watermark.
                if hasattr(self.store, "save"):
                    self.store.save()
            self._mark_replay(experience, digest)
        except Exception as exc:
            self.evidence.append("experience-incomplete", {
                "digest": digest, "engines": applied, "error_type": type(exc).__name__,
                "operator_reconciliation_required": True,
            })
            raise
        reward_applied = "experience-superlearner" in applied or "pythia" in applied
        self.evidence.append("experience-learned" if reward_applied else "experience-observed", {
            "digest": digest, "engines": applied, "reward_applied": reward_applied,
            "domain": experience.domain,
        })
        return digest

    def curriculum(self, *, limit: int = 10) -> dict[str, Any]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        return {
            "experience": [asdict(x) for x in self.experience_learner.autonomous_curriculum(limit)]
            if self.experience_learner is not None else [],
            "claims": [asdict(x) for x in self.governed_learning.generate_curriculum(limit)]
            if self.governed_learning is not None else [],
        }

    def consolidate(self, *, replay_limit: int = 64) -> dict[str, Any]:
        if replay_limit <= 0:
            raise ValueError("replay_limit must be positive")
        result: dict[str, Any] = {"external_validation": False}
        if self.governed_learning is not None:
            result["governed"] = asdict(self.governed_learning.consolidate(replay_limit=replay_limit))
        if self.pythia is not None:
            result["pythia_patterns"] = self.pythia.consolidate()
        if self.store is not None and hasattr(self.store, "save"):
            self.store.save()
        self.evidence.append("learning-consolidated", result)
        return result

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
                "governed_learning": self.governed_learning is not None,
                "durable_memory_database": self.memory_database is not None,
            },
            "experiences_seen": len(self._seen),
            "pending_reconciliation": sum(e.get("status") == "pending" for e in self._journal.values()),
            "replay_journal": {
                "path": replay["replay_journal_path"],
                "entries": replay["journal_entries"],
                "durable_replay_protection": replay["durable"],
            },
            "evidence_head": self.evidence.head,
        }
