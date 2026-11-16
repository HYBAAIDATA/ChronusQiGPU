"""Nonce search for the canonical Stratum miner over every qualified lane.

LaneSearchMixin replaces ChronusRealMiningEngine._search_nonce_batch and
nothing else: the pool session, job handling, gatekeeper and submission stay
the engine's own. Each call searches one shard's window of the nonce space
with that shard's version-rolling bits (the engine's own partitioning), sized
from the measured rate to about one second. Every lane hit is rechecked on the
host before it is handed to the engine, whose gatekeeper checks it again
before submission.
"""

from __future__ import annotations

import collections
import hashlib
import logging
import time

from chronus.stratum.bip310 import apply_version_rolling
from chronus.stratum.endian_engine import build_header80, swap_prevhash_words

logger = logging.getLogger("HybaMine.search")
TARGET_CALL_NS = 1_000_000_000
MIN_WINDOW = 1 << 14
MAX_WINDOW = 1 << 28


def initial_window(calibrated_per_s: int) -> int:
    """The largest power of two not above one second of calibrated work, within bounds."""
    window = MIN_WINDOW
    while window * 2 <= calibrated_per_s and window < MAX_WINDOW:
        window *= 2
    return window


class LaneSearchMixin:
    """Engine nonce search over a lane set; requires the engine's partitioner and cursors."""

    def _init_lane_search(self, lanes, ledger) -> None:
        self.lanes = lanes
        self.ledger = ledger
        self.window = initial_window(ledger.calibrated_per_s)
        self._pending = collections.deque()
        self._pending_context = None
        self.lane_hits = 0
        self.lane_recheck_failures = 0

    def _adapt_window(self, elapsed_ns: int) -> None:
        if elapsed_ns > 2 * TARGET_CALL_NS and self.window > MIN_WINDOW:
            self.window //= 2
        elif elapsed_ns < TARGET_CALL_NS // 2 and self.window < MAX_WINDOW:
            self.window *= 2

    def _lane_search(self, job, merkle_root_bytes, pool_mask_hex, share_target):
        context = (job["job_id"], bytes(merkle_root_bytes))
        if context != self._pending_context:
            self._pending.clear()
            self._pending_context = context
        if self._pending:
            return self._pending.popleft()

        shards = self.partitioner.ranges
        shard_count = len(shards)
        shard = shards[self._next_shard % shard_count]
        span = shard.end_nonce - shard.start_nonce
        cursor = self._nonce_cursors.get(shard.shard_id, shard.start_nonce)
        cursor = shard.start_nonce + ((cursor - shard.start_nonce) % span)
        mask = int(pool_mask_hex, 16)
        version_bits = (shard.shard_id << 13) & mask
        rolled_version, _ = apply_version_rolling(int(job["version_hex"], 16), mask, version_bits)
        header = build_header80(
            rolled_version,
            swap_prevhash_words(job["prevhash_hex"]),
            merkle_root_bytes,
            int(job["ntime_hex"], 16),
            int(job["nbits_hex"], 16),
            0,
        )
        count = min(self.window, span)
        first_stop = min(cursor + count, shard.end_nonce)
        windows = [(cursor, first_stop)]
        if first_stop - cursor < count:
            windows.append((shard.start_nonce, shard.start_nonce + count - (first_stop - cursor)))

        started = time.perf_counter_ns()
        hits = []
        searched = 0
        for low, high in windows:
            hits.extend(self.lanes.search(header, low, high, share_target))
            requested = high - low
            span_done = getattr(self.lanes, "last_span", None)
            done = requested if span_done is None else span_done
            searched += done
            if done < requested:
                break
        elapsed = time.perf_counter_ns() - started
        if searched <= 0:
            self._hash_throttled = True
            return None
        self._hash_throttled = False
        self.hashes_computed += searched
        self.ledger.record(searched, elapsed)
        self._adapt_window(elapsed)

        self._nonce_cursors[shard.shard_id] = shard.start_nonce + (
            (cursor - shard.start_nonce + searched) % span
        )
        self._scanned_per_shard[shard.shard_id] = min(
            span, self._scanned_per_shard.get(shard.shard_id, 0) + searched
        )
        self._next_shard = (shard.shard_id + 1) % shard_count

        version_bits_hex = f"{version_bits:08x}"
        prefix = bytes(header[:76])
        for nonce in hits:
            digest = hashlib.sha256(hashlib.sha256(prefix + nonce.to_bytes(4, "little")).digest()).digest()
            value = int.from_bytes(digest, "little")
            if value <= share_target:
                self.lane_hits += 1
                self._pending.append((nonce, version_bits_hex, value))
            else:
                self.lane_recheck_failures += 1
                logger.error("[LANES] hit 0x%08x failed the host recheck and was discarded", nonce)

        if all(self._scanned_per_shard.get(s.shard_id, 0) >= s.end_nonce - s.start_nonce for s in shards):
            # Every nonce for this extranonce2 is searched; the engine starts a new extranonce2.
            self._nonce_space_exhausted = True
            self._nonce_context = None
        if self._pending:
            return self._pending.popleft()
        return None
