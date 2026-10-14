"""Validated episodes/lessons; unsupported, overfitted generalizations are retained rejected."""

from dataclasses import dataclass, replace
from fractions import Fraction
from ._contracts import ContractError, ratio, sha, text


@dataclass(frozen=True)
class Episode:
    id: str
    task_key: str
    evidence_digest: str
    independent_group: str
    verifier: str
    validated: bool
    conclusion: str

    def __post_init__(self):
        for value in (
            self.id,
            self.task_key,
            self.independent_group,
            self.verifier,
            self.conclusion,
        ):
            text(value)
        sha(self.evidence_digest)
        if type(self.validated) is not bool:
            raise ContractError("typed validation required")


@dataclass(frozen=True)
class Lesson:
    id: str
    task_key: str
    conclusion: str
    kind: str
    support_ids: tuple[str, ...]
    confidence: Fraction

    def __post_init__(self):
        ratio(self.confidence)
        if self.kind not in ("FACT", "PROCEDURE") or type(self.support_ids) is not tuple:
            raise ContractError("typed lesson kind and support required")


class LongHorizonMemory:
    def __init__(self, ledger, *, minimum_support):
        if type(minimum_support) is not int or minimum_support < 2:
            raise ContractError("at least two independent support groups required")
        self.ledger = ledger
        self.minimum_support = minimum_support
        self.episodic = {}
        self.semantic = {}
        self.procedural = {}
        self.rejected = []
        self.contradictions = []
        self.contested = {}
        self.retracted = {}

    def record_episode(self, episode, *, now):
        if episode.id in self.episodic:
            raise ContractError("duplicate episode")
        self.ledger.append(
            "effect_confirmed", {"phase": "episode_recorded", "episode": episode}, now=now
        )
        self.episodic[episode.id] = episode

    def consolidate_memory(self, lesson, *, now):
        if lesson.id in self.semantic or lesson.id in self.procedural:
            raise ContractError("duplicate lesson")
        episodes = [self.episodic.get(i) for i in lesson.support_ids]
        groups = {e.independent_group for e in episodes if e is not None}
        valid = (
            len(set(lesson.support_ids)) == len(lesson.support_ids)
            and len(groups) >= self.minimum_support
            and all(
                e is not None
                and e.validated
                and e.task_key == lesson.task_key
                and e.conclusion == lesson.conclusion
                for e in episodes
            )
        )
        conflict = any(
            l.task_key == lesson.task_key and l.conclusion != lesson.conclusion
            for l in (*self.semantic.values(), *self.procedural.values())
        )
        if not valid:
            self.ledger.append(
                "memory_candidate_rejected",
                {"lesson": lesson, "reason": "unsupported_or_conflicting"},
                now=now,
            )
            self.rejected.append(lesson)
            if conflict:
                self.contradictions.append(lesson.id)
            return False
        lesson = replace(
            lesson, confidence=min(lesson.confidence, Fraction(len(groups), len(groups) + 1))
        )
        if conflict:
            self.ledger.append(
                "memory_adjudicated", {"lesson": lesson, "verdict": "RETAIN_WITH_TENSION"}, now=now
            )
            self.contested[lesson.id] = lesson
            self.contradictions.append(lesson.id)
            return False
        self.ledger.append("memory_lesson_stored", {"lesson": lesson, "support": episodes}, now=now)
        destination = self.semantic if lesson.kind == "FACT" else self.procedural
        if lesson.id in destination:
            raise ContractError("duplicate lesson")
        destination[lesson.id] = lesson
        return True

    def revise_or_forget(self, lesson_id, *, evidence_digest, now):
        sha(evidence_digest)
        if lesson_id not in self.semantic and lesson_id not in self.procedural:
            raise ContractError("unknown lesson")
        self.ledger.append(
            "memory_lesson_retracted", {"id": lesson_id, "evidence": evidence_digest}, now=now
        )
        removed = self.semantic.pop(lesson_id, None) or self.procedural.pop(lesson_id, None)
        if removed is None:
            raise ContractError("unknown lesson")
        self.retracted[lesson_id] = removed
        self.contradictions.append((lesson_id, evidence_digest))

    def adjudicate(
        self,
        new_id,
        old_id,
        new_quality,
        old_quality,
        policy,
        *,
        now,
        calibration=None,
        verify_calibration=None,
    ):
        from .world_model import adjudicate_contradiction

        new = self.contested[new_id]
        old = self.semantic.get(old_id) or self.procedural.get(old_id)
        if old is None or old.task_key != new.task_key or old.conclusion == new.conclusion:
            raise ContractError("matching conflicting lessons required")
        verdict = adjudicate_contradiction(
            new_quality,
            old_quality,
            policy,
            calibration=calibration,
            verify_calibration=verify_calibration,
            now=now,
        )
        self.ledger.append(
            "memory_adjudicated",
            {
                "new": new,
                "old": old,
                "new_quality": new_quality,
                "old_quality": old_quality,
                "policy": policy,
                "calibration": calibration,
                "verdict": verdict,
            },
            now=now,
        )
        if verdict == "SUPERSEDE":
            # Atomic in-memory transition after durable decision; preserve prior lesson.
            self.semantic.pop(old_id, None)
            self.procedural.pop(old_id, None)
            self.retracted[old_id] = old
            self.contested.pop(new_id)
            (self.semantic if new.kind == "FACT" else self.procedural)[new_id] = new
        return verdict
