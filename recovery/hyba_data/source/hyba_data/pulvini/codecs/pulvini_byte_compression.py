#!/usr/bin/env python3
"""
Al Haras Pulvini byte-level compression (migrated from HYBA_PROD_READY).

This is a DIFFERENT Pulvini implementation than
`euclid.pythagoras.quantum.operators.pulvini_scaling.PulviniOperator`:

- `PulviniOperator` (quantum/operators/pulvini_scaling.py) does phi-recursive
  tensor/Hamiltonian *dimensionality folding* -- an exact, invertible linear
  transform for vectors and Hermitian matrices.
- `PulviniDataCompression` (this file) does general-purpose *byte-level*
  compression of arbitrary data (JSON/text/audit records) using real stdlib
  codecs (zlib/gzip/lzma), with an entropy-based adaptive codec selector.

They solve different problems and are both kept, not merged. Naming honesty
note: `CompressionAlgorithm.QUANTUM_AWARE` and `INTELLIGENT_ADAPTIVE` are not
quantum computation or ML -- they are real LZMA/GZIP/ZLIB calls, selected by a
Shannon-entropy heuristic on the input bytes. All compression ratios below are
computed from actual compressed byte lengths, not estimated/hardcoded factors.

Migrated (unchanged logic) from HYBA_PROD_READY's
`src/al_haras/pulvini_data_compression.py` on 2026-07-13 as part of Al Haras
consolidation into HYBA_INTELLIGENCE.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import lzma
import uuid
import zlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import (  # noqa: F401 (Tuple used by compress_data_with_payload)
    Any,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

import numpy as np


class CompressionAlgorithm(str, Enum):
    """Compression algorithms supported by Pulvini byte compression."""
    ZLIB = "zlib"
    GZIP = "gzip"
    LZMA = "lzma"
    INTELLIGENT_ADAPTIVE = "intelligent_adaptive"
    QUANTUM_AWARE = "quantum_aware"


class DataType(str, Enum):
    """Data types for compression optimization."""
    LOGICAL = "logical"
    SPATIAL = "spatial"
    TEMPORAL = "temporal"
    CAUSAL = "causal"
    QUANTUM = "quantum"
    AUDIT = "audit"
    METRIC = "metric"
    GENERAL = "general"


@dataclass(frozen=True)
class CompressionResult:
    """Result of data compression operation."""
    compression_id: str
    original_size_bytes: int
    compressed_size_bytes: int
    compression_ratio: float
    compression_time_ms: float
    algorithm: CompressionAlgorithm
    data_type: DataType
    integrity_hash: str
    compressed_data_hash: str
    timestamp: str


@dataclass(frozen=True)
class DecompressionResult:
    """Result of data decompression operation."""
    decompression_id: str
    original_compression_id: str
    decompressed_size_bytes: int
    decompression_time_ms: float
    integrity_verified: bool
    timestamp: str


@dataclass(frozen=True)
class CompressionStatistics:
    """Statistics for compression operations."""
    total_compressions: int
    total_decompressions: int
    total_original_bytes: int
    total_compressed_bytes: int
    average_compression_ratio: float
    average_compression_time_ms: float
    average_decompression_time_ms: float
    space_saved_bytes: int
    by_algorithm: Dict[str, Dict[str, Any]]
    by_data_type: Dict[str, Dict[str, Any]]
    timestamp: str


class PulviniDataCompression:
    """
    General-purpose byte-level compression for high-throughput data streams.

    Implements real stdlib compression (zlib/gzip/lzma) with a data-type-aware
    algorithm selector and an entropy-based adaptive mode. Distinct from, and
    complementary to, the phi-recursive tensor-folding PulviniOperator.
    """

    def __init__(self):
        self.compression_results: List[CompressionResult] = []
        self.decompression_results: List[DecompressionResult] = []

        self.algorithm_selection: Dict[DataType, CompressionAlgorithm] = {
            DataType.LOGICAL: CompressionAlgorithm.ZLIB,
            DataType.SPATIAL: CompressionAlgorithm.LZMA,
            DataType.TEMPORAL: CompressionAlgorithm.GZIP,
            DataType.CAUSAL: CompressionAlgorithm.LZMA,
            DataType.QUANTUM: CompressionAlgorithm.QUANTUM_AWARE,
            DataType.AUDIT: CompressionAlgorithm.ZLIB,
            DataType.METRIC: CompressionAlgorithm.GZIP,
            DataType.GENERAL: CompressionAlgorithm.INTELLIGENT_ADAPTIVE,
        }

    def compress_data(
        self,
        data: Any,
        data_type: DataType = DataType.GENERAL,
        algorithm: Optional[CompressionAlgorithm] = None,
    ) -> CompressionResult:
        """Compress data using Pulvini compression (metrics only; see below)."""
        result, _compressed_data = self.compress_data_with_payload(data, data_type, algorithm)
        return result

    def compress_data_with_payload(
        self,
        data: Any,
        data_type: DataType = DataType.GENERAL,
        algorithm: Optional[CompressionAlgorithm] = None,
    ) -> Tuple[CompressionResult, bytes]:
        """Compress data, returning the compressed bytes alongside the metrics.

        `compress_data` only returns metrics and does not retain the
        compressed bytes, which makes it impossible for a caller to actually
        store and later decompress a payload. This method is the real,
        round-trippable primitive; `compress_data` is a thin wrapper over it
        kept for backwards compatibility with callers that only need metrics.
        """
        compression_id = f"compression-{uuid.uuid4().hex[:16]}"

        if isinstance(data, str):
            data_bytes = data.encode()
        elif isinstance(data, dict):
            data_bytes = json.dumps(data, sort_keys=True).encode()
        elif isinstance(data, (list, tuple)):
            data_bytes = json.dumps(data).encode()
        else:
            data_bytes = str(data).encode()

        original_size = len(data_bytes)
        integrity_hash = hashlib.sha256(data_bytes).hexdigest()

        if algorithm is None:
            algorithm = self.algorithm_selection.get(data_type, CompressionAlgorithm.INTELLIGENT_ADAPTIVE)

        start_time = datetime.now(timezone.utc)

        if algorithm == CompressionAlgorithm.ZLIB:
            compressed_data = zlib.compress(data_bytes, level=9)
        elif algorithm == CompressionAlgorithm.GZIP:
            compressed_data = gzip.compress(data_bytes, compresslevel=9)
        elif algorithm == CompressionAlgorithm.LZMA:
            compressed_data = lzma.compress(data_bytes, preset=9)
        elif algorithm == CompressionAlgorithm.QUANTUM_AWARE:
            compressed_data = self._quantum_aware_compress(data_bytes)
        elif algorithm == CompressionAlgorithm.INTELLIGENT_ADAPTIVE:
            compressed_data = self._intelligent_adaptive_compress(data_bytes, data_type)
        else:
            compressed_data = zlib.compress(data_bytes, level=9)

        end_time = datetime.now(timezone.utc)
        compression_time_ms = (end_time - start_time).total_seconds() * 1000

        compressed_size = len(compressed_data)
        compression_ratio = original_size / compressed_size if compressed_size > 0 else 1.0

        compressed_data_hash = hashlib.sha256(compressed_data).hexdigest()

        result = CompressionResult(
            compression_id=compression_id,
            original_size_bytes=original_size,
            compressed_size_bytes=compressed_size,
            compression_ratio=compression_ratio,
            compression_time_ms=compression_time_ms,
            algorithm=algorithm,
            data_type=data_type,
            integrity_hash=integrity_hash,
            compressed_data_hash=compressed_data_hash,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        self.compression_results.append(result)
        return result, compressed_data

    def _quantum_aware_compress(self, data: bytes) -> bytes:
        """LZMA at a lower preset. Not literal quantum computation -- see module docstring."""
        return lzma.compress(data, preset=7)

    def _intelligent_adaptive_compress(self, data: bytes, data_type: DataType) -> bytes:
        """Select a real codec based on measured Shannon entropy of the input."""
        entropy = self._calculate_entropy(data)
        if entropy < 3.0:
            return lzma.compress(data, preset=9)
        elif entropy < 5.0:
            return gzip.compress(data, compresslevel=9)
        else:
            return zlib.compress(data, level=9)

    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of data (bits/byte)."""
        if not data:
            return 0.0
        byte_counts: Dict[int, int] = {}
        for byte in data:
            byte_counts[byte] = byte_counts.get(byte, 0) + 1
        entropy = 0.0
        length = len(data)
        for count in byte_counts.values():
            probability = count / length
            entropy -= probability * np.log2(probability)
        return entropy

    def decompress_data(
        self,
        compressed_data: bytes,
        original_compression_id: str,
        algorithm: CompressionAlgorithm,
        expected_hash: Optional[str] = None,
    ) -> DecompressionResult:
        """Decompress data using Pulvini decompression, with optional hash verification."""
        decompression_id = f"decompression-{uuid.uuid4().hex[:16]}"

        start_time = datetime.now(timezone.utc)

        if algorithm == CompressionAlgorithm.ZLIB:
            decompressed_data = zlib.decompress(compressed_data)
        elif algorithm == CompressionAlgorithm.GZIP:
            decompressed_data = gzip.decompress(compressed_data)
        elif algorithm == CompressionAlgorithm.LZMA:
            decompressed_data = lzma.decompress(compressed_data)
        elif algorithm == CompressionAlgorithm.QUANTUM_AWARE:
            decompressed_data = self._quantum_aware_decompress(compressed_data)
        elif algorithm == CompressionAlgorithm.INTELLIGENT_ADAPTIVE:
            decompressed_data = self._intelligent_adaptive_decompress(compressed_data)
        else:
            decompressed_data = zlib.decompress(compressed_data)

        end_time = datetime.now(timezone.utc)
        decompression_time_ms = (end_time - start_time).total_seconds() * 1000

        decompressed_size = len(decompressed_data)

        integrity_verified = True
        if expected_hash:
            actual_hash = hashlib.sha256(decompressed_data).hexdigest()
            integrity_verified = (actual_hash == expected_hash)

        result = DecompressionResult(
            decompression_id=decompression_id,
            original_compression_id=original_compression_id,
            decompressed_size_bytes=decompressed_size,
            decompression_time_ms=decompression_time_ms,
            integrity_verified=integrity_verified,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        self.decompression_results.append(result)
        return result

    def _quantum_aware_decompress(self, compressed_data: bytes) -> bytes:
        return lzma.decompress(compressed_data)

    def _intelligent_adaptive_decompress(self, compressed_data: bytes) -> bytes:
        try:
            return lzma.decompress(compressed_data)
        except Exception:
            try:
                return gzip.decompress(compressed_data)
            except Exception:
                return zlib.decompress(compressed_data)

    def batch_compress(
        self,
        data_list: List[Any],
        data_type: DataType = DataType.GENERAL,
    ) -> List[CompressionResult]:
        results = []
        for data in data_list:
            result = self.compress_data(data, data_type)
            results.append(result)
        return results

    def get_compression_statistics(self) -> CompressionStatistics:
        total_compressions = len(self.compression_results)
        total_decompressions = len(self.decompression_results)

        if total_compressions == 0:
            return CompressionStatistics(
                total_compressions=0,
                total_decompressions=0,
                total_original_bytes=0,
                total_compressed_bytes=0,
                average_compression_ratio=0.0,
                average_compression_time_ms=0.0,
                average_decompression_time_ms=0.0,
                space_saved_bytes=0,
                by_algorithm={},
                by_data_type={},
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        total_original_bytes = sum(r.original_size_bytes for r in self.compression_results)
        total_compressed_bytes = sum(r.compressed_size_bytes for r in self.compression_results)
        average_compression_ratio = float(np.mean([r.compression_ratio for r in self.compression_results]))
        average_compression_time_ms = float(np.mean([r.compression_time_ms for r in self.compression_results]))
        average_decompression_time_ms = float(np.mean([r.decompression_time_ms for r in self.decompression_results])) if self.decompression_results else 0.0
        space_saved_bytes = total_original_bytes - total_compressed_bytes

        by_algorithm: Dict[str, Dict[str, Any]] = {}
        for algorithm in CompressionAlgorithm:
            algorithm_results = [r for r in self.compression_results if r.algorithm == algorithm]
            if algorithm_results:
                by_algorithm[algorithm.value] = {
                    "count": len(algorithm_results),
                    "average_ratio": float(np.mean([r.compression_ratio for r in algorithm_results])),
                    "total_original": sum(r.original_size_bytes for r in algorithm_results),
                    "total_compressed": sum(r.compressed_size_bytes for r in algorithm_results),
                }

        by_data_type: Dict[str, Dict[str, Any]] = {}
        for data_type in DataType:
            type_results = [r for r in self.compression_results if r.data_type == data_type]
            if type_results:
                by_data_type[data_type.value] = {
                    "count": len(type_results),
                    "average_ratio": float(np.mean([r.compression_ratio for r in type_results])),
                    "total_original": sum(r.original_size_bytes for r in type_results),
                    "total_compressed": sum(r.compressed_size_bytes for r in type_results),
                }

        return CompressionStatistics(
            total_compressions=total_compressions,
            total_decompressions=total_decompressions,
            total_original_bytes=total_original_bytes,
            total_compressed_bytes=total_compressed_bytes,
            average_compression_ratio=average_compression_ratio,
            average_compression_time_ms=average_compression_time_ms,
            average_decompression_time_ms=average_decompression_time_ms,
            space_saved_bytes=space_saved_bytes,
            by_algorithm=by_algorithm,
            by_data_type=by_data_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


__all__ = [
    "CompressionAlgorithm",
    "DataType",
    "CompressionResult",
    "DecompressionResult",
    "CompressionStatistics",
    "PulviniDataCompression",
]
