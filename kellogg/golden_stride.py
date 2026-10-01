"""Kellogg golden stride — hardware-dispersion and cache-locality probes.

Two benchmarks from the transcript, both measured:

* ``sparse_coverage_benchmark`` (Wall 13): a sparse boolean mask stands in
  for a sparse tensor; each striding engine walks addresses and we count
  how many *distinct active* addresses it reaches.  Dispersion, not reuse,
  is the metric — linear and Fibonacci strides clump into harmonic banks
  that irrational strides miss.

* :class:`CacheAwareGoldenStride` / :class:`GoldenHilbertOptimizer`: golden
  samples reordered by a space-filling index (Morton order — the scipy-free
  stand-in for the transcript's Hilbert curve, which the pseudocode itself
  replaces with "Morton/Z-order for higher dimensions"), then scored on an
  LRU cache-miss simulation.

Nothing here is a hardware guarantee: the miss rate comes from a toy
associative cache model in Python, declared as such.
"""

from __future__ import annotations

import math
from collections import OrderedDict
from typing import Callable, Dict

import numpy as np

from .first_principles import golden_ratio, plastic_number


class GoldenStrideError(ValueError):
    """A stride or coverage contract was violated."""


def sparse_coverage_benchmark(
    n_steps: int,
    data_size: int = 1_000_000,
    sparsity: float = 0.9,
    seed: int = 0,
) -> Dict[str, int]:
    """Unique active-address coverage of each striding engine.

    ``mask`` marks ~``1 - sparsity`` of ``data_size`` cells as active.  Each
    engine produces ``n_steps`` addresses; we return the count of distinct
    active cells visited.  Higher dispersion → higher unique coverage for
    irrational strides.
    """
    if n_steps < 1:
        raise GoldenStrideError(f"n_steps must be >= 1, got {n_steps}")
    if data_size < 1:
        raise GoldenStrideError(f"data_size must be >= 1, got {data_size}")
    rng = np.random.default_rng(seed)
    mask = (rng.random(data_size) < (1.0 - sparsity)).astype(np.int8)

    phi = golden_ratio()
    rho = plastic_number()
    fib_state = [1 % data_size, 1 % data_size]

    def fib_step(i: int) -> int:
        # Modular Fibonacci: the additive recurrence has a Pisano period,
        # so this engine's coverage is capped by that period — measured.
        fib_state[0], fib_state[1] = (
            fib_state[1],
            (fib_state[0] + fib_state[1]) % data_size,
        )
        return fib_state[0]

    engines: Dict[str, Callable[[int], float]] = {
        "linear": lambda i: float(i),
        "golden": lambda i: i * phi,
        "plastic": lambda i: i * rho,
        "fibonacci": lambda i: float(fib_step(i)),
        "random": lambda i: float(rng.integers(0, data_size)),
    }

    results: Dict[str, int] = {}
    for name, engine in engines.items():
        seen = set()
        for i in range(n_steps):
            addr = int(math.floor(engine(i))) % data_size
            if mask[addr]:
                seen.add(addr)
        results[name] = len(seen)
    return results


class CacheAwareGoldenStride:
    """Golden samples reordered for simulated cache locality.

    ``optimal_stride`` is the golden-ratio stride in units of cache lines —
    chosen for dispersion across lines, not for reuse distance.
    """

    def __init__(self, dimension: int = 2, cache_line_size: int = 64):
        if dimension < 1:
            raise GoldenStrideError(f"dimension must be >= 1, got {dimension}")
        if cache_line_size < 1:
            raise GoldenStrideError(
                f"cache_line_size must be >= 1, got {cache_line_size}"
            )
        self.dimension = int(dimension)
        self.cache_line_size = int(cache_line_size)
        self.phi = golden_ratio()
        self.optimal_stride = int(round(self.phi * self.cache_line_size))

    def grid_index(self, point: np.ndarray, grid_size: int) -> np.ndarray:
        """Quantise a ``[0,1)^d`` point onto a ``grid_size`` integer grid."""
        coords = np.floor(np.asarray(point) * grid_size).astype(np.int64)
        return np.clip(coords, 0, grid_size - 1)

    def morton_order(self, points: np.ndarray, grid_size: int) -> np.ndarray:
        """Permutation sorting points by Morton (Z-order) code.

        Morton order is the no-scipy stand-in for a Hilbert index; it keeps
        grid neighbours adjacent in memory order for most of the curve.
        """
        pts = np.asarray(points, dtype=float)
        if pts.shape[1] != self.dimension:
            raise GoldenStrideError(
                f"points have dimension {pts.shape[1]}; expected {self.dimension}"
            )
        grid = np.floor(pts * grid_size).astype(np.int64)
        grid = np.clip(grid, 0, grid_size - 1)
        bits = max(1, int(math.ceil(math.log2(grid_size))))
        codes = []
        for row in grid:
            code = 0
            for axis, coord in enumerate(row):
                for bit in range(bits):
                    code |= ((int(coord) >> bit) & 1) << (bit * self.dimension + axis)
            codes.append(code)
        return np.argsort(np.asarray(codes), kind="stable")

    def golden_stride_sequence(self, n: int) -> np.ndarray:
        """``n`` golden-ratio points in ``[0,1)^2`` ordered by Morton code."""
        if n < 1:
            raise GoldenStrideError(f"n must be >= 1, got {n}")
        idx = np.arange(n, dtype=float)
        points = np.stack(
            [(idx * self.phi) % 1.0, (idx / self.phi) % 1.0], axis=1
        )
        grid_size = max(2, int(math.ceil(math.sqrt(n))))
        order = self.morton_order(points, grid_size)
        return points[order]

    def compute_cache_misses(
        self, sequence: np.ndarray, cache_size: int = 1000
    ) -> float:
        """LRU miss rate of a point sequence in the simulated cache.

        Each point hashes to a cache-line key (quantised to 8 decimal cells
        per unit).  This is a toy fully-associative LRU model — a measured
        proxy for locality, not a hardware trace.
        """
        seq = np.asarray(sequence)
        if len(seq) == 0:
            return 0.0
        cache: "OrderedDict[tuple, None]" = OrderedDict()
        misses = 0
        for point in seq:
            key = tuple(np.floor(np.asarray(point) * 8).astype(np.int64).tolist())
            if key in cache:
                cache.move_to_end(key)
            else:
                misses += 1
                cache[key] = None
                if len(cache) > cache_size:
                    cache.popitem(last=False)
        return misses / float(len(seq))


class GoldenHilbertOptimizer:
    """Measured locality duel: raw golden order vs Morton-ordered golden."""

    def __init__(self, dimension: int = 2):
        self.dimension = int(dimension)
        self.stride = CacheAwareGoldenStride(dimension)
        self.phi = golden_ratio()

    def optimize_sampling(
        self, n_points: int = 10_000, cache_size: int = 1000, seed: int = 0
    ) -> Dict[str, Dict[str, float]]:
        """Miss-rate comparison of the three orderings."""
        idx = np.arange(n_points, dtype=float)
        standard = np.stack(
            [(idx * self.phi) % 1.0, (idx / self.phi) % 1.0], axis=1
        )
        cache_aware = self.stride.golden_stride_sequence(n_points)
        random = np.random.default_rng(seed).random((n_points, self.dimension))

        results: Dict[str, Dict[str, float]] = {}
        for name, seq in (
            ("standard_golden", standard),
            ("cache_aware", cache_aware),
            ("random", random),
        ):
            miss_rate = self.stride.compute_cache_misses(seq, cache_size)
            results[name] = {
                "cache_miss_rate": miss_rate,
                "locality_score": 1.0 - miss_rate,
            }
        return results


__all__ = [
    "CacheAwareGoldenStride",
    "GoldenHilbertOptimizer",
    "GoldenStrideError",
    "sparse_coverage_benchmark",
]
