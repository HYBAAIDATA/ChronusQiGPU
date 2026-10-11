"""Sparse Lucas evaluation and bounded streaming dispatch."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Iterator
from .lucas_engine import lucas
from .lucas_datapath import DatapathConfig, DatapathFailure, SpatialLucasPipeline

def lucas_sparse(n: int, width: int = 0) -> int:
    if n < 0: raise ValueError("n must be non-negative")
    if width < 0: raise ValueError("width must be non-negative")
    value = lucas(n)
    return value if width == 0 else value % (1 << width)

def lucas_batch_sparse(rungs: Iterable[int], width: int = 0) -> list[int]:
    requested = list(rungs)
    return [lucas_sparse(n, width) for n in requested]

@dataclass(frozen=True)
class SparseResult:
    tier: int
    records: tuple
    execution_mode: str = "sparse"

def sparse_dispatch(tier: int, rungs: Iterable[int], width: int = 256, prime_rom_limit: int = 100_000) -> SparseResult:
    if tier <= 15: raise ValueError("sparse dispatch is reserved for tiers above 15")
    pipeline = SpatialLucasPipeline(DatapathConfig(width, 6, prime_rom_limit, "sparse-reference"))
    records = tuple(pipeline.process_batch(rungs))
    return SparseResult(tier, records)

def stream_rungs(rungs: Iterable[int], width: int = 256, prime_rom_limit: int = 100_000) -> Iterator:
    pipeline = SpatialLucasPipeline(DatapathConfig(width, 6, prime_rom_limit, "sparse-stream"))
    for rung in rungs: yield pipeline.process_one(rung)
