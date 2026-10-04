"""Load historical mining hypotheses as non-authoritative EUCLID curriculum.

This module intentionally does not create a memory database or mutate the
canonical cognition memory. Consumers must evaluate a hypothesis and record
new evidence through current EUCLID learning contracts before using it.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.resources import files
from types import MappingProxyType
from typing import Any, Iterator, Mapping

_ALLOWED_STATUS = "archival_curriculum_hypothesis"
_ALLOWED_AUTHORITY = "none"

@dataclass(frozen=True)
class CurriculumHypothesis:
    seed_id: str
    domain: str
    statement: str
    provenance: str
    memory_form: str
    historical_evidence_stage: str
    content_hash: str
    metadata: Mapping[str, Any]
    current_semantic_status: str
    authority: str

    def verify(self) -> bool:
        payload = f"{self.seed_id}:{self.domain}:{self.statement}:{self.memory_form}"
        return (
            self.current_semantic_status == _ALLOWED_STATUS
            and self.authority == _ALLOWED_AUTHORITY
            and hashlib.sha256(payload.encode()).hexdigest() == self.content_hash
        )


def load_curriculum() -> tuple[CurriculumHypothesis, ...]:
    path = files(__package__).joinpath("mining_hypotheses_20260719.json")
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema") != "hyba.euclid.curriculum.v1":
        raise ValueError("unsupported curriculum schema")
    if document.get("identity_root") != "fresh-euclid-2026":
        raise ValueError("curriculum is not bound to the fresh EUCLID identity policy")
    result = []
    seen = set()
    for row in document.get("seeds", ()):
        item = CurriculumHypothesis(
            seed_id=str(row["seed_id"]), domain=str(row["domain"]),
            statement=str(row["statement"]), provenance=str(row["provenance"]),
            memory_form=str(row["memory_form"]),
            historical_evidence_stage=str(row["historical_evidence_stage"]),
            content_hash=str(row["content_hash"]),
            metadata=MappingProxyType(dict(row.get("metadata", {}))),
            current_semantic_status=str(row["current_semantic_status"]),
            authority=str(row["authority"]),
        )
        if item.seed_id in seen:
            raise ValueError(f"duplicate curriculum seed: {item.seed_id}")
        if not item.verify():
            raise ValueError(f"invalid or authoritative curriculum seed: {item.seed_id}")
        seen.add(item.seed_id)
        result.append(item)
    return tuple(result)


def iter_by_domain(domain: str) -> Iterator[CurriculumHypothesis]:
    return (item for item in load_curriculum() if item.domain == domain)

__all__ = ["CurriculumHypothesis", "iter_by_domain", "load_curriculum"]
