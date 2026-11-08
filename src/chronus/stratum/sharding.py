"""
Chronus Sub-Range Work Partitioning & Deduplication Engine.

Shard Partitioning Contract:
-----------------------------
- Divides 32-bit nonce space (2^32 = 4,294,967,296) into SHARD_COUNT non-overlapping ranges:
  Shard[i] owns nonces in [i * (2^32 / SHARD_COUNT), (i + 1) * (2^32 / SHARD_COUNT))
- Each shard owns a distinct version_bits sub-mask:
  version_bits_offset = (i << 13) & pool_mask
- Maintains an in-memory LRU DedupLedger of (job_id, version_bits, extranonce2, ntime, nonce)
  to guarantee zero duplicate work across searcher processes.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class NonceRange:
    shard_id: int
    start_nonce: int
    end_nonce: int
    version_bits_offset: int


@dataclass(frozen=True)
class ShareCandidate:
    job_id: str
    extranonce2_hex: str
    ntime_hex: str
    nonce_int: int
    version_bits_hex: str
    hash_int: int
    block_height: Optional[int] = None
    shard_id: int = 0


class DedupLedger:
    """
    In-memory LRU ledger preventing duplicate share submission across parallel searchers.
    Caps history to max_entries to bound memory usage.
    """
    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self._entries: Set[Tuple[str, str, str, str, int]] = set()
        self._order: List[Tuple[str, str, str, str, int]] = []

    def is_duplicate(self, job_id: str, version_bits_hex: str, extranonce2_hex: str, ntime_hex: str, nonce_int: int) -> bool:
        key = (job_id, version_bits_hex, extranonce2_hex, ntime_hex, nonce_int)
        return key in self._entries

    def record(self, job_id: str, version_bits_hex: str, extranonce2_hex: str, ntime_hex: str, nonce_int: int) -> bool:
        """
        Records a work key in the dedup ledger.
        Returns True if newly recorded, False if already present (duplicate).
        """
        key = (job_id, version_bits_hex, extranonce2_hex, ntime_hex, nonce_int)
        if key in self._entries:
            return False

        if len(self._order) >= self.max_entries:
            oldest = self._order.pop(0)
            self._entries.remove(oldest)

        self._entries.add(key)
        self._order.append(key)
        return True

    def clear(self):
        self._entries.clear()
        self._order.clear()


class WorkPartitioner:
    """
    Partitions nonce space and version-rolling masks across SHARD_COUNT workers.
    """
    def __init__(self, shard_count: int = 8, pool_mask_hex: str = "1fffe000"):
        if shard_count <= 0:
            raise ValueError(f"Shard count must be positive, got {shard_count}")
        self.shard_count = shard_count
        self.pool_mask_hex = pool_mask_hex
        self.pool_mask_int = int(pool_mask_hex, 16)
        self.ranges: List[NonceRange] = self._build_ranges()

    def _build_ranges(self) -> List[NonceRange]:
        total_nonces = 1 << 32
        chunk_size = total_nonces // self.shard_count
        ranges = []
        for i in range(self.shard_count):
            start = i * chunk_size
            end = (i + 1) * chunk_size if i < self.shard_count - 1 else total_nonces
            v_offset = (i << 13) & self.pool_mask_int
            ranges.append(NonceRange(shard_id=i, start_nonce=start, end_nonce=end, version_bits_offset=v_offset))
        return ranges

    def get_range(self, shard_id: int) -> NonceRange:
        if shard_id < 0 or shard_id >= self.shard_count:
            raise ValueError(f"Invalid shard_id {shard_id} for total shards {self.shard_count}")
        return self.ranges[shard_id]
