"""
φ-Folded Quantum Memory Hierarchy
=================================
Implements a four-tier φ-folded memory hierarchy inspired by the EUCLID
PHI-Space architecture.

Tiers:
    Register (depth-0): no compression, fastest access
    SRAM (depth-1):     φ¹ compression (~1.618× reduction)
    L2 (depth-2):       φ² compression (~2.618× reduction)
    HBM (depth-3+):     φ³+ compression (~4.236×+ reduction)

All memory sizes are CONFIGURABLE — the spec's 512 TB + 2 PB is an
architecture target. Default sizes are small for testability.
All bandwidth is MEASURED from actual memory operations.

Claim lane: INTERNAL — demonstrates φ-folded memory hierarchy on classical
hardware with measured performance.
"""

import numpy as np
from typing import Dict, Optional, List
from dataclasses import dataclass
import time
from .phi_tensor_core import FoldState, PHI


@dataclass
class MemoryTier:
    """A single tier in the φ-folded memory hierarchy."""
    name: str
    depth: int          # φ-compression depth (0 = unfolded)
    capacity: int       # Number of elements this tier can hold
    data: Optional[dict] = None  # {key: FoldState}

    def __post_init__(self):
        self.data = {}

    @property
    def compression_factor(self) -> float:
        return PHI ** self.depth

    @property
    def effective_capacity(self) -> int:
        """Capacity in terms of original (unfolded) elements."""
        return int(self.capacity * self.compression_factor)

    def store(self, key: str, state: FoldState) -> bool:
        """Store a FoldState, folding if depth > 0."""
        if len(self.data) >= self.capacity:
            return False  # Tier full
        if self.depth > 0:
            state = state.fold(self.depth)
        self.data[key] = state
        return True

    def load(self, key: str) -> Optional[FoldState]:
        """Load a FoldState, unfolding if it was folded."""
        state = self.data.get(key)
        if state is None:
            return None
        if self.depth > 0:
            return state.unfold()
        return state

    def usage(self) -> float:
        return len(self.data) / self.capacity if self.capacity > 0 else 0


class QuantumMemoryHierarchy:
    """
    Four-tier φ-folded memory hierarchy.

    Architecture target: 512 TB HBM4 + 2 PB Quantum Cache.
    Default: small configurable sizes for testability.
    All bandwidth is MEASURED.
    """

    def __init__(self, register_cap: int = 64, sram_cap: int = 256,
                 l2_cap: int = 1024, hbm_cap: int = 4096):
        self.register = MemoryTier("Register", depth=0, capacity=register_cap)
        self.sram = MemoryTier("SRAM", depth=1, capacity=sram_cap)
        self.l2 = MemoryTier("L2", depth=2, capacity=l2_cap)
        self.hbm = MemoryTier("HBM", depth=3, capacity=hbm_cap)
        self._read_ops = 0
        self._write_ops = 0
        self._read_bytes = 0
        self._write_bytes = 0
        self._read_time = 0.0
        self._write_time = 0.0

    @property
    def tiers(self) -> List[MemoryTier]:
        return [self.register, self.sram, self.l2, self.hbm]

    def store(self, key: str, state: FoldState, tier: str = "register") -> bool:
        """Store data in the specified tier."""
        t0 = time.perf_counter()
        tier_map = {"register": self.register, "sram": self.sram,
                    "l2": self.l2, "hbm": self.hbm}
        t = tier_map.get(tier, self.register)
        success = t.store(key, state)
        self._write_ops += 1
        self._write_bytes += state.data.nbytes
        self._write_time += time.perf_counter() - t0
        return success

    def load(self, key: str, tier: str = "register") -> Optional[FoldState]:
        """Load data from the specified tier."""
        t0 = time.perf_counter()
        tier_map = {"register": self.register, "sram": self.sram,
                    "l2": self.l2, "hbm": self.hbm}
        t = tier_map.get(tier, self.register)
        state = t.load(key)
        if state is not None:
            self._read_ops += 1
            self._read_bytes += state.data.nbytes
        self._read_time += time.perf_counter() - t0
        return state

    def promote(self, key: str, from_tier: str, to_tier: str) -> bool:
        """Promote data from a lower tier to a higher one (unfold)."""
        state = self.load(key, from_tier)
        if state is None:
            return False
        return self.store(key, state, to_tier)

    def demote(self, key: str, from_tier: str, to_tier: str) -> bool:
        """Demote data from a higher tier to a lower one (fold)."""
        state = self.load(key, from_tier)
        if state is None:
            return False
        return self.store(key, state, to_tier)

    def stream_benchmark(self, array_size: int = 100000, trials: int = 100) -> Dict:
        """
        STREAM-style memory bandwidth benchmark.
        Measures REAL bandwidth from actual memory operations.
        """
        # Copy benchmark
        src = np.random.standard_normal(array_size)
        dst = np.empty_like(src)

        t0 = time.perf_counter()
        for _ in range(trials):
            np.copyto(dst, src)
        elapsed = time.perf_counter() - t0

        # Bandwidth: each copy moves 2 arrays (read + write) of 8 bytes each
        bytes_moved = 2 * array_size * 8 * trials  # 2 arrays * 8 bytes/element * trials
        bandwidth_bps = bytes_moved / elapsed if elapsed > 0 else 0

        # Scale benchmark
        a = np.random.standard_normal(array_size)
        np.empty_like(a)
        scalar = 3.0

        t0 = time.perf_counter()
        for _ in range(trials):
            a * scalar
        elapsed_scale = time.perf_counter() - t0

        # Triad benchmark
        c = np.random.standard_normal(array_size)
        np.empty_like(c)

        t0 = time.perf_counter()
        for _ in range(trials):
            a + scalar * c
        elapsed_triad = time.perf_counter() - t0

        triad_bytes = 3 * array_size * 8 * trials  # read a, read c, write d
        triad_bandwidth = triad_bytes / elapsed_triad if elapsed_triad > 0 else 0

        return {
            "array_size": array_size,
            "trials": trials,
            "copy_bandwidth_gbps": bandwidth_bps / 1e9,
            "copy_bandwidth_tbps": bandwidth_bps / 1e12,
            "scale_time": elapsed_scale,
            "triad_bandwidth_gbps": triad_bandwidth / 1e9,
            "triad_bandwidth_tbps": triad_bandwidth / 1e12,
            "note": "Real measured STREAM-style bandwidth on this hardware.",
        }

    def fold_integrity_test(self, dim: int = 4096, depths: List[int] = None) -> Dict:
        """
        Test fold/unfold integrity at each tier depth.
        Measures reconstruction error for each compression level.
        """
        if depths is None:
            depths = [0, 1, 2, 3]

        rng = np.random.default_rng(42)
        original_data = rng.standard_normal(dim) + 1j * rng.standard_normal(dim)
        original = FoldState(original_data, 0, dim)

        results = []
        for depth in depths:
            folded = original.fold(depth)
            unfolded = folded.unfold()
            if len(unfolded.data) == len(original.data):
                error = float(np.linalg.norm(unfolded.data - original.data))
                rel_error = error / float(np.linalg.norm(original.data))
            else:
                error = float("inf")
                rel_error = float("inf")
            results.append({
                "depth": depth,
                "compression_factor": PHI ** depth,
                "folded_dim": folded.dim,
                "reconstruction_error": error,
                "relative_error": rel_error,
                "lossless": rel_error < 1e-10,
            })

        return {
            "original_dim": dim,
            "results": results,
            "note": (
                "φ-fold is lossy at depth > 0 (block averaging + interpolation). "
                "Lossless fold requires a different method (e.g., wavelet or "
                "invertible transform). This test characterises the trade-off."
            ),
        }

    def get_specs(self) -> Dict:
        """Return honest, measured specifications."""
        return {
            "tiers": [
                {"name": t.name, "depth": t.depth,
                 "capacity": t.capacity,
                 "compression_factor": t.compression_factor,
                 "effective_capacity": t.effective_capacity,
                 "usage": t.usage()}
                for t in self.tiers
            ],
            "architecture_target": {
                "hbm4": "512 TB",
                "quantum_cache": "2 PB",
                "bandwidth": "2 PB/s",
                "note": "Architecture targets from spec. Actual sizes are configurable."
            },
            "measured": {
                "read_ops": self._read_ops,
                "write_ops": self._write_ops,
                "read_time": self._read_time,
                "write_time": self._write_time,
            },
        }
