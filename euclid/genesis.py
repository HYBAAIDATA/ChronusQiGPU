"""Fresh identity and provenance contracts for the post-convergence EUCLID.

This module creates evidence roots; it does not create a learner, memory store,
database, reward authority, or production authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

GENESIS_SCHEMA = "euclid.genesis/1"
GENERATION_ID = "EUCLID-PYTHIPhiMiner-CONVERGENCE-2026-10-02"
BASE_SHA = "d3eef9a71bccac5a59b27aff7283c4d98f06cc21"


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def root(domain: str, value: Any) -> str:
    if not domain:
        raise ValueError("hash domain is required")
    return hashlib.sha256(domain.encode() + b"\0" + canonical_json(value)).hexdigest()


class EvidenceClass(str, Enum):
    CURRENT_VERIFIED = "CURRENT_VERIFIED"
    CURRENT_INTERNAL = "CURRENT_INTERNAL"
    ARCHIVAL = "ARCHIVAL"
    CURRICULUM = "CURRICULUM"
    REHEARSAL = "REHEARSAL"
    REFUTED = "REFUTED"
    UNKNOWN = "UNKNOWN"


class SourceDisposition(str, Enum):
    OBSERVATION_ONLY = "OBSERVATION_ONLY"
    EVALUATION_CANDIDATE = "EVALUATION_CANDIDATE"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ProvenanceSource:
    source_id: str
    source_identity: str
    version: str
    evidence_class: EvidenceClass
    uncertainty: float
    disposition: SourceDisposition = SourceDisposition.OBSERVATION_ONLY
    uri: str | None = None
    content_sha256: str | None = None
    labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not all((self.source_id, self.source_identity, self.version)):
            raise ValueError("source identity, id, and version are required")
        if not 0.0 <= float(self.uncertainty) <= 1.0:
            raise ValueError("uncertainty must be in [0,1]")
        if self.evidence_class in (EvidenceClass.ARCHIVAL, EvidenceClass.CURRICULUM):
            if self.disposition is not SourceDisposition.OBSERVATION_ONLY:
                raise ValueError("archival/curriculum sources are observation-only")

    def assert_not_semantic_truth(self) -> None:
        if self.evidence_class in (EvidenceClass.ARCHIVAL, EvidenceClass.CURRICULUM):
            forbidden = {
                "CURRENT_SEMANTIC_TRUTH",
                "AUTOBIOGRAPHICAL_MEMORY",
                "PRODUCTION_REWARD",
                "FINAL_TEST",
            }
            overlap = forbidden.intersection(self.labels)
            if overlap:
                raise ValueError(
                    "archival/curriculum source crossed a genesis boundary: "
                    + ",".join(sorted(overlap))
                )


@dataclass(frozen=True)
class GenesisManifest:
    generation_id: str
    canonical_name: str
    base_sha: str
    predecessor_relationship: str
    created_at: str
    sources: tuple[ProvenanceSource, ...] = ()
    non_claims: tuple[str, ...] = (
        "consciousness",
        "inherited memories",
        "production intelligence",
        "general intelligence",
        "production qualification",
        "external validation",
    )
    authority_boundaries: Mapping[str, str] = field(
        default_factory=lambda: {
            "learning": "EUCLID LearningService/TrainingPipeline/RewardAuthority",
            "operational_experience": "Salamander",
            "durable_state": "OVID (current implementation name: Aethel)",
            "query_projection": "THESEUS (current implementation name: hyba_db)",
            "execution": "Chronus",
            "rehearsal": "Kairos; no production mining/network/pool/wallet authority",
            "bitcoin_consensus": "existing mining stack; unchanged",
        }
    )

    def __post_init__(self) -> None:
        if self.generation_id != GENERATION_ID:
            raise ValueError("this mutation may create only the declared new generation")
        if self.base_sha != BASE_SHA:
            raise ValueError("genesis must be rooted at the immutable #108 head")
        for source in self.sources:
            source.assert_not_semantic_truth()

    def body(self) -> dict[str, Any]:
        return {
            "schema": GENESIS_SCHEMA,
            "generation_id": self.generation_id,
            "canonical_name": self.canonical_name,
            "base_sha": self.base_sha,
            "predecessor_relationship": self.predecessor_relationship,
            "created_at": self.created_at,
            "sources": [asdict(source) for source in self.sources],
            "non_claims": list(self.non_claims),
            "authority_boundaries": dict(self.authority_boundaries),
        }

    def roots(self) -> dict[str, str]:
        body = self.body()
        source_rows = body["sources"]
        return {
            "identity_root": root(
                "euclid.identity-root.v1",
                {
                    "generation_id": self.generation_id,
                    "canonical_name": self.canonical_name,
                    "base_sha": self.base_sha,
                    "predecessor_relationship": self.predecessor_relationship,
                },
            ),
            "memory_root": root("euclid.memory-root.v1", []),
            "event_root": root("euclid.event-root.v1", []),
            "claim_root": root("euclid.claim-root.v1", []),
            "checkpoint_root": root(
                "euclid.checkpoint-root.v1",
                {"base_sha": self.base_sha, "generation_id": self.generation_id},
            ),
            "curriculum_provenance_root": root(
                "euclid.curriculum-provenance-root.v1", source_rows
            ),
            "manifest_root": root("euclid.genesis-manifest.v1", body),
        }

    def to_payload(self) -> dict[str, Any]:
        body = self.body()
        return {**body, "roots": self.roots(), "seal": root("euclid.genesis.seal.v1", body)}


def build_genesis(
    sources: Sequence[ProvenanceSource] = (),
) -> GenesisManifest:
    return GenesisManifest(
        generation_id=GENERATION_ID,
        canonical_name="EUCLID",
        base_sha=BASE_SHA,
        predecessor_relationship=(
            "NEW_INSTANCE; prior EUCLID identities and memory lineages are not "
            "identity ancestors and may enter only as labelled archival/curriculum evidence"
        ),
        created_at="2026-10-02T19:05:40Z",
        sources=tuple(sources),
    )


__all__ = [
    "BASE_SHA",
    "EvidenceClass",
    "GENERATION_ID",
    "GenesisManifest",
    "ProvenanceSource",
    "SourceDisposition",
    "build_genesis",
    "canonical_json",
    "root",
]