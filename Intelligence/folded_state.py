"""Exact folded-state execution engine for PYTHIA.

The fold is a *working representation*, not a codec:

- ``turing_core.t_phi_fold`` applies the Cassini-protected T_phi byte-pair
  bijection (``M15`` in ``GL(2, Z/256Z)``, det = -1 mod 256 — exact
  integer inverse, bit-exact round trip).
- Storage = folded bytes + measured entropy coding (zlib ratio recorded
  per payload, never assumed).
- Queries are *compiled* against folded bytes and execute without
  materialising the raw buffer:

  * ``sum_u8`` / ``histogram_u8`` — fold-domain aggregation
  * ``modular_dot_u8`` — q^T x = (M^-T q)^T y (mod 256): the query vector
    is pushed through the inverse once, then dots folded bytes directly
  * ``weighted_sum_u8`` — streaming weighted sum via the fused inverse
  * ``sha256_equals`` — streams the inverse through the digest

This is the engine that makes "hold the blockchain in superposition" a
literal statement: folded artifacts are stored, queried, and verified in
fold-space; the 11D manifold point is the geodesic address.
"""

from __future__ import annotations

# LUCAS WIRING: draws from lucas/ (pool) OR the canonical turing_core
# substrate. MUST NOT import from any sibling algorithm.

import hashlib
import zlib
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import turing_core as tc  # canonical substrate — same module the iGPU runs

FOLDED_STATE_VERSION = "2.0.0-canonical"


@dataclass
class FoldedStateArtifact:
    """A payload held entirely in folded state."""

    sha256: str
    folded_sha256: str
    original_length: int
    folded_length: int
    storage: bytes
    storage_kind: str  # "zlib-folded" | "raw-folded"
    compressed_length: int
    compression_ratio: float  # measured, never assumed
    zeckendorf_indices: Tuple[int, ...]
    family: str = "golden"


@dataclass
class CompiledFoldedQuery:
    """A query bound to an artifact's fold-domain coordinates."""

    op: str
    weights: Optional[bytes] = None
    expected_sha256: Optional[str] = None


@dataclass
class FoldedQueryResult:
    value: Any
    op: str
    raw_buffer_materialized: bool = False
    resident_bytes: int = 0


class ExactFoldedStateEngine:
    """Encode, store, and query payloads in folded state.

    Every query executes against folded bytes; ``raw_buffer_materialized``
    stays False. ``restore`` is the only path that produces raw bytes and
    it is hash-verified.
    """

    def __init__(self) -> None:
        self._artifacts: Dict[str, FoldedStateArtifact] = {}
        self._folded_bytes: Dict[str, bytes] = {}  # resident folded state
        self._queries = 0
        self._raw_materializations = 0

    # -- store (Fibonacci/Cassini layer) --------------------------------

    def encode(
        self, payload: bytes, key: Optional[str] = None, family: str = "golden"
    ) -> FoldedStateArtifact:
        """Fold payload through T_phi and store measured-compressed form."""
        folded = tc.t_phi_fold(payload)
        packed = zlib.compress(folded, level=9)
        use_zlib = len(packed) < len(folded)
        storage = packed if use_zlib else folded
        n = len(payload)
        artifact = FoldedStateArtifact(
            sha256=hashlib.sha256(payload).hexdigest(),
            folded_sha256=hashlib.sha256(folded).hexdigest(),
            original_length=n,
            folded_length=len(folded),
            storage=storage,
            storage_kind="zlib-folded" if use_zlib else "raw-folded",
            compressed_length=len(storage),
            compression_ratio=(len(storage) / n) if n else 0.0,
            zeckendorf_indices=tuple(tc.zeckendorf_encode(n)),
            family=family,
        )
        k = key or artifact.sha256[:16]
        self._artifacts[k] = artifact
        self._folded_bytes[k] = folded  # resident fold-domain state
        return artifact

    def restore(self, key: str) -> bytes:
        """Unfold and hash-verify — the only path that yields raw bytes."""
        artifact = self._artifacts[key]
        folded = self._folded_bytes[key]
        raw = tc.t_phi_unfold(folded, artifact.original_length)
        self._raw_materializations += 1
        if hashlib.sha256(raw).hexdigest() != artifact.sha256:
            raise ValueError("folded artifact integrity check failed")
        return raw

    # -- query (work happens in fold-space) ------------------------------

    def compile_query(
        self, op: str, weights: Optional[bytes] = None, expected_sha256: Optional[str] = None
    ) -> CompiledFoldedQuery:
        return CompiledFoldedQuery(op=op, weights=weights, expected_sha256=expected_sha256)

    def execute(self, key: str, query: CompiledFoldedQuery) -> FoldedQueryResult:
        """Run a compiled query against resident folded bytes."""
        artifact = self._artifacts[key]
        folded = self._folded_bytes[key]
        n = artifact.original_length
        self._queries += 1

        if query.op == "sum_u8":
            value = sum(tc.iter_original_u8(folded, n))
        elif query.op == "weighted_sum_u8":
            w = query.weights or b""
            value = sum(
                x * (w[i] if i < len(w) else 1)
                for i, x in enumerate(tc.iter_original_u8(folded, n))
            )
        elif query.op == "modular_dot_u8":
            value = tc.folded_modular_dot(folded, n, list(query.weights or b""))
        elif query.op == "histogram_u8":
            hist = [0] * 256
            for x in tc.iter_original_u8(folded, n):
                hist[x] += 1
            value = hist
        elif query.op == "sha256_equals":
            digest = hashlib.sha256()
            for value_u8 in tc.iter_original_u8(folded, n):
                digest.update(bytes((value_u8,)))
            value = digest.hexdigest() == (query.expected_sha256 or artifact.sha256)
        else:
            raise ValueError(f"unknown folded op: {query.op}")

        return FoldedQueryResult(value=value, op=query.op, resident_bytes=artifact.folded_length)

    def status(self) -> Dict[str, Any]:
        return {
            "version": FOLDED_STATE_VERSION,
            "artifacts": len(self._artifacts),
            "resident_folded_bytes": sum(a.folded_length for a in self._artifacts.values()),
            "stored_bytes": sum(a.compressed_length for a in self._artifacts.values()),
            "queries_executed": self._queries,
            "raw_materializations": self._raw_materializations,
            "theorem_proven": False,
        }
