"""PYTHIA structural training for observed Bitcoin nonce corpora.

This module is deliberately not a PoW predictor and does not alter the
consensus truth boundary. It teaches PYTHIA the geometry/distribution of an
observed nonce corpus as unlabelled structural evidence. SHA256d + target
comparison remains the only validity predicate.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from python_backend.phi_grover_v4 import cheap_resonance, phi_resonance

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI15 = PHI ** 15
UINT32_MAX = (1 << 32) - 1
DEFAULT_HOLDOUT_FRACTION = 0.20
DEFAULT_NULL_SEED = 0x9E3779B9
_ALLOWED_REAL_VERIFICATION = {
    "bundle_local_pow_verified",
    "full_header_pow_verified",
}


class CorpusIntegrityError(ValueError):
    """Raised when training provenance or corpus integrity is not sufficient."""


@dataclass(frozen=True)
class NonceObservation:
    height: int
    nonce: int


@dataclass(frozen=True)
class StructureTrainingReport:
    corpus_id: str
    corpus_sha256: str
    rows_total: int
    rows_train: int
    rows_holdout: int
    rows_newly_taught: int
    rows_already_known: int
    consolidated: int
    source_type: str
    verification_level: str
    outcome_mode: str
    train_resonance_ge_0_5_rate: float
    holdout_resonance_ge_0_5_rate: float
    holdout_mean_max_cosine: float
    uniform_control_mean_max_cosine: float
    holdout_minus_uniform_similarity: float
    pythia_outcome_evidence_unchanged: bool
    snapshot_path: Optional[str]
    claim_boundary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: Path) -> Dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CorpusIntegrityError("training manifest must be a JSON object")
    return data


def load_nonce_corpus(
    csv_path: Path,
    manifest_path: Path,
) -> Tuple[List[NonceObservation], Dict[str, Any]]:
    """Load a corpus and fail closed on provenance/integrity violations."""
    csv_path = Path(csv_path)
    manifest = load_manifest(Path(manifest_path))

    digest = _sha256_path(csv_path)
    if digest != manifest.get("csv_sha256"):
        raise CorpusIntegrityError(
            f"corpus digest mismatch: measured={digest} manifest={manifest.get('csv_sha256')}"
        )
    if manifest.get("source_type") != "real":
        raise CorpusIntegrityError(
            "PYTHIA structural seed training accepts real observations only"
        )
    if manifest.get("synthetic_excluded") is not True:
        raise CorpusIntegrityError("manifest must assert synthetic_excluded=true")
    verification = str(manifest.get("verification_level", ""))
    if verification not in _ALLOWED_REAL_VERIFICATION:
        raise CorpusIntegrityError(
            f"unaccepted verification_level={verification!r}"
        )

    rows: List[NonceObservation] = []
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != ["height", "nonce"]:
            raise CorpusIntegrityError(
                f"expected exact columns ['height', 'nonce'], got {reader.fieldnames!r}"
            )
        for raw in reader:
            height = int(raw["height"])
            nonce = int(raw["nonce"])
            if height < 0:
                raise CorpusIntegrityError(f"negative block height {height}")
            if not 0 <= nonce <= UINT32_MAX:
                raise CorpusIntegrityError(
                    f"nonce outside uint32 at height {height}: {nonce}"
                )
            rows.append(NonceObservation(height=height, nonce=nonce))

    expected_n = int(manifest.get("row_count", -1))
    if len(rows) != expected_n:
        raise CorpusIntegrityError(
            f"row_count mismatch: measured={len(rows)} manifest={expected_n}"
        )
    heights = [r.height for r in rows]
    if len(set(heights)) != len(heights):
        raise CorpusIntegrityError("duplicate block heights in real nonce corpus")
    if not rows:
        raise CorpusIntegrityError("empty corpus")
    return rows, manifest


def _bit_transition_rate(nonce: int) -> float:
    x = nonce ^ (nonce >> 1)
    return (x & UINT32_MAX).bit_count() / 32.0


def _phi15_proximity(nonce: int) -> float:
    frac = (float(nonce) / PHI15) % 1.0
    return 1.0 - 2.0 * min(frac, 1.0 - frac)


def structural_vector(
    observation: NonceObservation,
    previous: Optional[NonceObservation] = None,
) -> np.ndarray:
    """Encode one observed nonce into PYTHIA's 32-channel structure pattern."""
    n = int(observation.nonce)
    prev = int(previous.nonce) if previous is not None else n
    delta = (n - prev) & UINT32_MAX
    xor = n ^ prev

    out: List[float] = [
        n / UINT32_MAX,
        float(phi_resonance(n)),
        float(cheap_resonance(n)),
        (n * PHI) % 1.0,
        _phi15_proximity(n),
        n.bit_count() / 32.0,
        _bit_transition_rate(n),
        delta / UINT32_MAX,
        xor.bit_count() / 32.0,
    ]
    out.extend(((n >> shift) & 0xFF) / 255.0 for shift in (0, 8, 16, 24))
    for k in range(1, 20):
        phase = (n * (PHI ** k)) % 1.0
        out.append(0.5 + 0.5 * math.cos(2.0 * math.pi * phase))

    vec = np.asarray(out, dtype=float)
    if vec.shape != (32,):
        raise AssertionError(f"structural vector must be 32D, got {vec.shape}")
    if not np.all(np.isfinite(vec)):
        raise CorpusIntegrityError("non-finite structural feature")
    return np.clip(vec, 0.0, 1.0)


def build_vectors(rows: Sequence[NonceObservation]) -> List[np.ndarray]:
    ordered = sorted(rows, key=lambda r: r.height)
    vectors: List[np.ndarray] = []
    previous: Optional[NonceObservation] = None
    for row in ordered:
        vectors.append(structural_vector(row, previous=previous))
        previous = row
    return vectors


def split_by_height(
    rows: Sequence[NonceObservation],
    holdout_fraction: float = DEFAULT_HOLDOUT_FRACTION,
) -> Tuple[List[NonceObservation], List[NonceObservation]]:
    """Chronological split with newest observations kept blind."""
    if not 0.0 < holdout_fraction < 0.5:
        raise ValueError("holdout_fraction must be in (0, 0.5)")
    ordered = sorted(rows, key=lambda r: r.height)
    n_holdout = max(1, int(round(len(ordered) * holdout_fraction)))
    if n_holdout >= len(ordered):
        raise CorpusIntegrityError("not enough rows for train/holdout split")
    return ordered[:-n_holdout], ordered[-n_holdout:]


def _pattern_id(corpus_id: str, row: NonceObservation) -> int:
    digest = hashlib.sha256(
        f"{corpus_id}:{row.height}:{row.nonce}".encode("ascii")
    ).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _teach_unlabelled_structure(
    pythia: Any,
    pattern: np.ndarray,
    pattern_id: int,
) -> bool:
    """Teach structure without inventing a mining success/failure label.

    PythiaLearning.learning_step historically maps an omitted outcome to
    False. That is not appropriate for a positive-only structural corpus.
    This adapter uses the same plasticity, short-term memory, golden folding,
    Zeckendorf storage and consolidation machinery while leaving the mining
    outcome evidence counters untouched.
    """
    existing_long_term = {m.pattern_id for m in pythia.patterns()}
    if pattern_id in existing_long_term:
        return False

    p = np.asarray(pattern, dtype=float)
    if len(p) < pythia.n:
        p = np.concatenate([p, np.zeros(pythia.n - len(p))])
    elif len(p) > pythia.n:
        p = p[: pythia.n]

    pythia._strengthen_connections(p)

    for entry in pythia._short_term:
        if entry["pattern_id"] == pattern_id:
            entry["activation_count"] += 1
            entry["pattern"] = p
            entry["evidence_kind"] = "structure_only"
            return False

    pythia._short_term.append(
        {
            "pattern_id": pattern_id,
            "pattern": p,
            "activation_count": 1,
            "mining_success": False,
            "evidence_kind": "structure_only",
        }
    )
    return True


def _mean_max_cosine(
    queries: Sequence[np.ndarray],
    references: Sequence[np.ndarray],
) -> float:
    if not queries or not references:
        return 0.0
    ref = np.stack(references)
    ref_norm = np.linalg.norm(ref, axis=1)
    values: List[float] = []
    for query in queries:
        query_norm = float(np.linalg.norm(query))
        denom = ref_norm * query_norm
        scores = np.divide(
            ref @ query,
            denom,
            out=np.zeros_like(ref_norm),
            where=denom > 0,
        )
        values.append(float(np.max(scores)))
    return float(np.mean(values))


def _uniform_control_vectors(
    n: int,
    reference_rows: Sequence[NonceObservation],
    seed: int = DEFAULT_NULL_SEED,
) -> List[np.ndarray]:
    rng = random.Random(seed)
    if not reference_rows:
        return []
    min_height = min(r.height for r in reference_rows)
    controls = [
        NonceObservation(height=min_height + i, nonce=rng.getrandbits(32))
        for i in range(n)
    ]
    return build_vectors(controls)


def _resonance_rate(
    rows: Sequence[NonceObservation],
    threshold: float = 0.5,
) -> float:
    if not rows:
        return 0.0
    return sum(phi_resonance(r.nonce) >= threshold for r in rows) / len(rows)


def train_pythia_structure(
    orchestrator: Any,
    csv_path: Path,
    manifest_path: Path,
    *,
    holdout_fraction: float = DEFAULT_HOLDOUT_FRACTION,
    persist: bool = True,
) -> StructureTrainingReport:
    """Train PYTHIA on real nonce structure while preserving a blind holdout."""
    rows, manifest = load_nonce_corpus(Path(csv_path), Path(manifest_path))
    train_rows, holdout_rows = split_by_height(
        rows,
        holdout_fraction=holdout_fraction,
    )
    train_vectors = build_vectors(train_rows)
    holdout_vectors = build_vectors(holdout_rows)
    control_vectors = _uniform_control_vectors(len(holdout_rows), holdout_rows)

    pythia = orchestrator.pythia
    before_evidence = {
        key: list(value)
        for key, value in getattr(pythia, "_evidence", {}).items()
    }
    before_totals = tuple(getattr(pythia, "_totals", ()))

    corpus_id = str(manifest["corpus_id"])
    newly_taught = 0
    already_known = 0
    ordered_train = sorted(train_rows, key=lambda r: r.height)
    for row, vector in zip(ordered_train, train_vectors):
        if _teach_unlabelled_structure(
            pythia,
            vector,
            _pattern_id(corpus_id, row),
        ):
            newly_taught += 1
        else:
            already_known += 1

    consolidated = int(pythia.consolidate()) if newly_taught else 0

    after_evidence = {
        key: list(value)
        for key, value in getattr(pythia, "_evidence", {}).items()
    }
    evidence_unchanged = (
        before_evidence == after_evidence
        and before_totals == tuple(getattr(pythia, "_totals", ()))
    )
    if not evidence_unchanged:
        raise RuntimeError(
            "structure-only training contaminated mining outcome evidence"
        )

    holdout_similarity = _mean_max_cosine(holdout_vectors, train_vectors)
    control_similarity = _mean_max_cosine(control_vectors, train_vectors)

    report_payload: Dict[str, Any] = {
        "corpus_id": corpus_id,
        "corpus_sha256": manifest["csv_sha256"],
        "rows_total": len(rows),
        "rows_train": len(train_rows),
        "rows_holdout": len(holdout_rows),
        "rows_newly_taught": newly_taught,
        "rows_already_known": already_known,
        "consolidated": consolidated,
        "source_type": manifest["source_type"],
        "verification_level": manifest["verification_level"],
        "outcome_mode": "structure_only_unlabelled",
        "train_resonance_ge_0_5_rate": _resonance_rate(train_rows),
        "holdout_resonance_ge_0_5_rate": _resonance_rate(holdout_rows),
        "holdout_mean_max_cosine": holdout_similarity,
        "uniform_control_mean_max_cosine": control_similarity,
        "holdout_minus_uniform_similarity": holdout_similarity - control_similarity,
        "pythia_outcome_evidence_unchanged": evidence_unchanged,
        "snapshot_path": None,
        "claim_boundary": (
            "structural learning/search-order evidence only; never a SHA256d "
            "validity predicate, hit-probability claim, hashrate claim, or "
            "pool-acceptance claim"
        ),
    }

    store = getattr(orchestrator, "store", None)
    if store is not None:
        store.record_run("pythia_structure_training", dict(report_payload))
        if persist:
            report_payload["snapshot_path"] = str(store.save())

    return StructureTrainingReport(**report_payload)


__all__ = [
    "CorpusIntegrityError",
    "NonceObservation",
    "StructureTrainingReport",
    "load_manifest",
    "load_nonce_corpus",
    "structural_vector",
    "build_vectors",
    "split_by_height",
    "train_pythia_structure",
]
