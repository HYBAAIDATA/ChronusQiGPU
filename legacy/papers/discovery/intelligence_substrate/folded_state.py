"""Exact folded-state storage and execution for the HYBA substrate.

This module composes four existing HYBA mechanisms without treating any one
of them as the system itself:

* the Cassini-protected ``T_phi`` byte bijection is the state representation;
* entropy coding is the storage layer and is measured per payload;
* Fibonacci tiers are the capacity/addressing policy for resident state; and
* compiled queries execute against folded state without materialising a raw
  byte buffer.

The distinction between mathematical and empirical claims is deliberate.
Losslessness follows from the inverse matrix over ``Z/256Z``.  Compression is
data-dependent and is therefore recorded, never assumed.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import time
from typing import Any, Dict, Iterable, Optional, Sequence
import zlib

from python_backend.hyba_substrate.infrastructure import HYBACore
from python_backend.lattice.fibonacci_memory import FibonacciMemoryPartitionManager

M15 = ((219, 98), (98, 121))
M15_INV = ((135, 98), (98, 37))
MODULUS = 256


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _matrix_product_mod_256(left, right):
    return tuple(
        tuple(sum(left[i][k] * right[k][j] for k in range(2)) % MODULUS for j in range(2))
        for i in range(2)
    )


@dataclass(frozen=True)
class FoldedStateArtifact:
    """Self-describing, content-addressed folded storage artifact."""

    encoded_folded: bytes
    original_len: int
    folded_len: int
    original_sha256: str
    folded_sha256: str
    compression_ratio: float
    reduction_fraction: float
    storage_tier_bytes: int
    resident_tier_bytes: int
    codec: str = "zlib-9"
    transform: str = "T_phi_M15_mod_256"
    version: int = 1

    def metadata(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "transform": self.transform,
            "codec": self.codec,
            "original_len": self.original_len,
            "folded_len": self.folded_len,
            "encoded_len": len(self.encoded_folded),
            "original_sha256": self.original_sha256,
            "folded_sha256": self.folded_sha256,
            "compression_ratio": self.compression_ratio,
            "reduction_fraction": self.reduction_fraction,
            "storage_tier_bytes": self.storage_tier_bytes,
            "resident_tier_bytes": self.resident_tier_bytes,
        }

    @classmethod
    def from_metadata(
        cls, metadata: Dict[str, Any], encoded_folded: bytes
    ) -> "FoldedStateArtifact":
        return cls(
            encoded_folded=bytes(encoded_folded),
            original_len=int(metadata["original_len"]),
            folded_len=int(metadata["folded_len"]),
            original_sha256=str(metadata["original_sha256"]),
            folded_sha256=str(metadata["folded_sha256"]),
            compression_ratio=float(metadata["compression_ratio"]),
            reduction_fraction=float(metadata["reduction_fraction"]),
            storage_tier_bytes=int(metadata["storage_tier_bytes"]),
            resident_tier_bytes=int(metadata["resident_tier_bytes"]),
            codec=str(metadata.get("codec", "zlib-9")),
            transform=str(metadata.get("transform", "T_phi_M15_mod_256")),
            version=int(metadata.get("version", 1)),
        )


@dataclass(frozen=True)
class CompiledFoldedQuery:
    """A query whose semantics are defined against original unsigned bytes."""

    operation: str
    weights: Optional[tuple[int, ...]] = None
    expected_sha256: Optional[str] = None


@dataclass(frozen=True)
class FoldedQueryResult:
    value: Any
    operation: str
    backend: str
    elapsed_ns: int
    folded_bytes_read: int
    result_bytes_returned: int
    host_to_device_bytes: int
    device_to_host_bytes: int
    raw_buffer_materialized: bool
    proof: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "operation": self.operation,
            "backend": self.backend,
            "elapsed_ns": self.elapsed_ns,
            "folded_bytes_read": self.folded_bytes_read,
            "result_bytes_returned": self.result_bytes_returned,
            "host_to_device_bytes": self.host_to_device_bytes,
            "device_to_host_bytes": self.device_to_host_bytes,
            "raw_buffer_materialized": self.raw_buffer_materialized,
            "proof": dict(self.proof),
        }


class ExactFoldedStateEngine:
    """Create, restore, and query exact folded-state artifacts."""

    OPERATIONS = frozenset(
        {"sum_u8", "weighted_sum_u8", "modular_dot_u8", "histogram_u8", "sha256_equals"}
    )

    def __init__(
        self, tier_manager: Optional[FibonacciMemoryPartitionManager] = None, igpu: Any = None
    ):
        self.tiers = tier_manager or FibonacciMemoryPartitionManager(use_spectral=False)
        self.igpu = igpu
        if _matrix_product_mod_256(M15, M15_INV) != ((1, 0), (0, 1)):
            raise RuntimeError("T_phi inverse proof failed in Z/256Z")
        determinant = (M15[0][0] * M15[1][1] - M15[0][1] * M15[1][0]) % MODULUS
        if determinant != MODULUS - 1:
            raise RuntimeError("Cassini determinant must be -1 mod 256")

    @property
    def algebra_proof(self) -> Dict[str, Any]:
        return {
            "ring": "Z/256Z",
            "matrix": M15,
            "inverse": M15_INV,
            "determinant_mod_256": 255,
            "matrix_times_inverse_mod_256": ((1, 0), (0, 1)),
            "category": "GL(2,Z/256Z)",
        }

    def encode(self, raw: bytes, compression_level: int = 9) -> FoldedStateArtifact:
        if not isinstance(raw, (bytes, bytearray, memoryview)):
            raise TypeError("raw must be bytes-like")
        if not 0 <= compression_level <= 9:
            raise ValueError("compression_level must be in [0, 9]")
        raw_bytes = bytes(raw)
        folded = HYBACore.t_phi_fold(raw_bytes)
        expected_folded_len = len(raw_bytes) + (len(raw_bytes) % 2)
        if len(folded) != expected_folded_len:
            raise RuntimeError("fold changed length by more than the recorded odd-byte pad")
        if HYBACore.t_phi_unfold(folded, len(raw_bytes)) != raw_bytes:
            raise RuntimeError("T_phi round-trip invariant failed")

        encoded = zlib.compress(folded, level=compression_level)
        ratio = len(encoded) / max(1, len(raw_bytes))
        return FoldedStateArtifact(
            encoded_folded=encoded,
            original_len=len(raw_bytes),
            folded_len=len(folded),
            original_sha256=_sha256(raw_bytes),
            folded_sha256=_sha256(folded),
            compression_ratio=ratio,
            reduction_fraction=1.0 - ratio,
            storage_tier_bytes=self.tiers.get_optimal_tier(max(1, len(encoded))),
            resident_tier_bytes=self.tiers.get_optimal_tier(max(1, len(folded))),
        )

    def folded_bytes(self, artifact: FoldedStateArtifact) -> bytes:
        if artifact.codec != "zlib-9":
            raise ValueError(f"unsupported codec: {artifact.codec}")
        folded = zlib.decompress(artifact.encoded_folded)
        if len(folded) != artifact.folded_len:
            raise ValueError("folded length does not match artifact metadata")
        if _sha256(folded) != artifact.folded_sha256:
            raise ValueError("folded-state hash mismatch")
        return folded

    def restore(self, artifact: FoldedStateArtifact) -> bytes:
        folded = self.folded_bytes(artifact)
        raw = HYBACore.t_phi_unfold(folded, artifact.original_len)
        if _sha256(raw) != artifact.original_sha256:
            raise ValueError("restored content hash mismatch")
        return raw

    def compile_query(
        self,
        operation: str,
        *,
        weights: Optional[Sequence[int]] = None,
        expected_sha256: Optional[str] = None,
    ) -> CompiledFoldedQuery:
        if operation not in self.OPERATIONS:
            raise ValueError(f"unsupported folded query: {operation}")
        compiled_weights = None if weights is None else tuple(int(w) for w in weights)
        if operation in {"weighted_sum_u8", "modular_dot_u8"} and compiled_weights is None:
            raise ValueError(f"{operation} requires weights")
        if operation == "sha256_equals" and not expected_sha256:
            raise ValueError("sha256_equals requires expected_sha256")
        return CompiledFoldedQuery(operation, compiled_weights, expected_sha256)

    @staticmethod
    def _iter_original_u8(folded: bytes, original_len: int) -> Iterable[int]:
        if len(folded) % 2:
            raise ValueError("folded state must contain complete pairs")
        emitted = 0
        for i in range(0, len(folded), 2):
            u, v = folded[i], folded[i + 1]
            x = (M15_INV[0][0] * u + M15_INV[0][1] * v) % MODULUS
            y = (M15_INV[1][0] * u + M15_INV[1][1] * v) % MODULUS
            if emitted < original_len:
                yield x
                emitted += 1
            if emitted < original_len:
                yield y
                emitted += 1

    @staticmethod
    def _modular_dot(folded: bytes, original_len: int, weights: Sequence[int]) -> int:
        """Compute q^T x (mod 256) as (M^-T q)^T y, pair by pair."""
        if len(weights) != original_len:
            raise ValueError("weights length must equal original byte length")
        total = 0
        for pair, i in enumerate(range(0, len(folded), 2)):
            q0 = int(weights[2 * pair]) if 2 * pair < original_len else 0
            q1 = int(weights[2 * pair + 1]) if 2 * pair + 1 < original_len else 0
            qu = (M15_INV[0][0] * q0 + M15_INV[1][0] * q1) % MODULUS
            qv = (M15_INV[0][1] * q0 + M15_INV[1][1] * q1) % MODULUS
            total = (total + qu * folded[i] + qv * folded[i + 1]) % MODULUS
        return total

    def execute(
        self,
        artifact: FoldedStateArtifact,
        query: CompiledFoldedQuery,
        *,
        resident: Any = None,
    ) -> FoldedQueryResult:
        folded = self.folded_bytes(artifact)
        start = time.perf_counter_ns()
        backend = "cpu-fused-folded"
        host_to_device_bytes = 0
        device_to_host_bytes = 0

        if query.operation == "sum_u8" and resident is not None:
            value = int(resident.sum_original())
            backend = "opencl-resident-folded"
            device_to_host_bytes = int(getattr(resident, "last_device_to_host_bytes", 0))
        elif (
            query.operation == "sum_u8"
            and self.igpu is not None
            and getattr(self.igpu, "available", False)
        ):
            resident = self.igpu.resident_folded_bytes(folded, artifact.original_len)
            value = int(resident.sum_original())
            backend = "opencl-resident-folded"
            host_to_device_bytes = len(folded)
            device_to_host_bytes = int(getattr(resident, "last_device_to_host_bytes", 0))
        elif query.operation == "sum_u8":
            value = sum(self._iter_original_u8(folded, artifact.original_len))
        elif query.operation == "weighted_sum_u8":
            assert query.weights is not None
            if len(query.weights) != artifact.original_len:
                raise ValueError("weights length must equal original byte length")
            value = sum(
                w * x
                for w, x in zip(
                    query.weights, self._iter_original_u8(folded, artifact.original_len)
                )
            )
        elif query.operation == "modular_dot_u8":
            assert query.weights is not None
            value = self._modular_dot(folded, artifact.original_len, query.weights)
        elif query.operation == "histogram_u8":
            bins = [0] * MODULUS
            for value_u8 in self._iter_original_u8(folded, artifact.original_len):
                bins[value_u8] += 1
            value = bins
        elif query.operation == "sha256_equals":
            digest = hashlib.sha256()
            chunk = bytearray()
            for value_u8 in self._iter_original_u8(folded, artifact.original_len):
                chunk.append(value_u8)
                if len(chunk) == 4096:
                    digest.update(chunk)
                    chunk.clear()
            if chunk:
                digest.update(chunk)
            value = digest.hexdigest() == query.expected_sha256
        else:  # guarded by compile_query, protects manually constructed objects
            raise ValueError(f"unsupported folded query: {query.operation}")

        elapsed = time.perf_counter_ns() - start
        result_size = 2048 if query.operation == "histogram_u8" else 8
        return FoldedQueryResult(
            value=value,
            operation=query.operation,
            backend=backend,
            elapsed_ns=elapsed,
            folded_bytes_read=len(folded),
            result_bytes_returned=result_size,
            host_to_device_bytes=host_to_device_bytes,
            device_to_host_bytes=device_to_host_bytes,
            raw_buffer_materialized=False,
            proof={
                "original_sha256": artifact.original_sha256,
                "folded_sha256": artifact.folded_sha256,
                "inverse_fused_into_query": True,
                "modular_query_identity": "q^T x = (M^-T q)^T y (mod 256)",
                "resident_tier_bytes": artifact.resident_tier_bytes,
            },
        )
