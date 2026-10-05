"""Read-only runtime projection of PYTHIA's structural training.

The advisor converts the provenance-bound, structure-only long-term memories
created by :mod:`Intelligence.mining_structure_training` into a 32-face score
vector.  The score may refine search ordering, but it never changes candidate
membership and has no SHA256d, target, freshness, or pool-acceptance authority.
"""
from __future__ import annotations

import hashlib
import threading
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from .mining_structure_training import (
    DEFAULT_CORPUS_CSV,
    DEFAULT_CORPUS_MANIFEST,
    NonceObservation,
    load_nonce_corpus,
    split_by_height,
    structural_vector,
)

PHI = (1.0 + 5.0 ** 0.5) / 2.0
FACE_COUNT = 32
_TOP_K = 5
_LOCK = threading.RLock()
_ACTIVE: "StructureAdvisorSnapshot | None" = None


@dataclass(frozen=True)
class StructureAdvisorSnapshot:
    corpus_id: str
    corpus_sha256: str
    reference_count: int
    pattern_ids: tuple[int, ...]
    references: tuple[tuple[float, ...], ...]
    model_digest: str
    claim_boundary: str = (
        "learned structural similarity may refine candidate ordering only; "
        "it never establishes Bitcoin proof or pool acceptance"
    )

    def metadata(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("references", None)
        data["state"] = "READY"
        return data


@dataclass(frozen=True)
class StructureFaceAdvice:
    state: str
    scores: tuple[float | None, ...]
    preferred_face: int | None
    model_digest: str | None
    reference_count: int
    detail: str
    proof_authority: bool = False
    preserves_candidate_membership: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _pattern_id(corpus_id: str, row: NonceObservation) -> int:
    digest = hashlib.sha256(
        f"{corpus_id}:{row.height}:{row.nonce}".encode("ascii")
    ).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _unfold(folded_data: bytes) -> np.ndarray:
    folded = np.frombuffer(folded_data, dtype=float).copy()
    if folded.shape != (32,):
        raise ValueError(f"expected a 32D folded PYTHIA pattern, got {folded.shape}")
    for index in range(32):
        folded[index] *= PHI ** (index % 5)
    return folded


def install_from_pythia(pythia: Any) -> StructureAdvisorSnapshot:
    """Install an immutable read-only model from fully trained PYTHIA memory.

    All 160 chronological training memories must be present.  Partial memory
    is not promoted to runtime advice; this makes the training/readiness
    boundary explicit and reproducible.
    """
    rows, manifest = load_nonce_corpus(DEFAULT_CORPUS_CSV, DEFAULT_CORPUS_MANIFEST)
    train_rows, _holdout = split_by_height(rows)
    corpus_id = str(manifest["corpus_id"])
    expected_ids = tuple(_pattern_id(corpus_id, row) for row in train_rows)
    by_id = {int(memory.pattern_id): memory for memory in pythia.patterns()}
    missing = [pattern_id for pattern_id in expected_ids if pattern_id not in by_id]
    if missing:
        raise RuntimeError(
            "PYTHIA structure advisor requires the complete trained corpus: "
            f"missing {len(missing)} of {len(expected_ids)} memories"
        )

    references = tuple(tuple(float(v) for v in _unfold(by_id[pattern_id].folded_data)) for pattern_id in expected_ids)
    digest = hashlib.sha256()
    digest.update(str(manifest["csv_sha256"]).encode("ascii"))
    for pattern_id, vector in zip(expected_ids, references):
        digest.update(pattern_id.to_bytes(8, "big", signed=False))
        digest.update(np.asarray(vector, dtype=np.float64).tobytes())
    snapshot = StructureAdvisorSnapshot(
        corpus_id=corpus_id,
        corpus_sha256=str(manifest["csv_sha256"]),
        reference_count=len(references),
        pattern_ids=expected_ids,
        references=references,
        model_digest=digest.hexdigest(),
    )
    global _ACTIVE
    with _LOCK:
        _ACTIVE = snapshot
    return snapshot


def clear_active_model() -> None:
    """Test helper: remove the process-local advisory projection."""
    global _ACTIVE
    with _LOCK:
        _ACTIVE = None


def active_model() -> StructureAdvisorSnapshot | None:
    with _LOCK:
        return _ACTIVE


def _top_k_similarity(query: np.ndarray, refs: np.ndarray) -> float:
    q_norm = float(np.linalg.norm(query))
    ref_norm = np.linalg.norm(refs, axis=1)
    denom = ref_norm * q_norm
    sims = np.divide(
        refs @ query,
        denom,
        out=np.zeros_like(ref_norm),
        where=denom > 0,
    )
    k = min(_TOP_K, len(sims))
    if not k:
        return 0.0
    top = np.partition(sims, len(sims) - k)[-k:]
    return float(np.mean(top))


def advise_faces(base_step: int, window: int) -> StructureFaceAdvice:
    """Score up to 32 live coarse-face representatives against trained memory.

    Face ``f`` is represented by the first leased nonce congruent to that
    coarse lane, ``base_step + f``.  This is only a ranking hint.  The caller
    must retain every face/vertex/nonce in the canonical itinerary.
    """
    if type(base_step) is not int or not 0 <= base_step <= 0xFFFFFFFF:
        raise ValueError("base_step must be uint32")
    if type(window) is not int or window <= 0 or base_step + window > 1 << 32:
        raise ValueError("window must be a positive uint32-bounded lease")
    snapshot = active_model()
    if snapshot is None:
        return StructureFaceAdvice(
            state="UNAVAILABLE_UNTRAINED",
            scores=(None,) * FACE_COUNT,
            preferred_face=None,
            model_digest=None,
            reference_count=0,
            detail="no trained PYTHIA structural model is installed",
        )

    refs = np.asarray(snapshot.references, dtype=float)
    previous = NonceObservation(height=0, nonce=base_step)
    scores: list[float | None] = []
    for face in range(FACE_COUNT):
        if face >= window:
            scores.append(None)
            continue
        nonce = base_step + face
        vector = structural_vector(
            NonceObservation(height=0, nonce=nonce),
            previous=previous,
        )
        scores.append(_top_k_similarity(vector, refs))
    available = [index for index, score in enumerate(scores) if score is not None]
    preferred = max(available, key=lambda index: (float(scores[index]), -index))
    return StructureFaceAdvice(
        state="ACTIVE",
        scores=tuple(scores),
        preferred_face=preferred,
        model_digest=snapshot.model_digest,
        reference_count=snapshot.reference_count,
        detail="mean cosine similarity to five nearest trained structural memories",
    )


__all__ = [
    "FACE_COUNT",
    "StructureAdvisorSnapshot",
    "StructureFaceAdvice",
    "active_model",
    "advise_faces",
    "clear_active_model",
    "install_from_pythia",
]
