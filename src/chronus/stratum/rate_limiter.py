"""
Chronus Integer Nanosecond Token Bucket Rate Limiter Engine.

Purity & Performance Contract:
-------------------------------
- Uses time.perf_counter_ns() integer nanoseconds ONLY.
- 0 floating-point operations.
- Non-blocking acquire() with exact integer token refill and integer remainder carrying.
- Priority Queue Block Bypass: Mainnet block solutions bypass rate limiter entirely.
"""

import time
from typing import Optional
from chronus.stratum.sharding import ShareCandidate


class IntegerNanosecondTokenBucket:
    """
    Token bucket rate limiter operating strictly on integer nanoseconds.
    Pacing rate: rate_per_sec (default 15 submits/sec).
    Capacity: 2 * rate_per_sec (default 30 tokens).
    """
    def __init__(self, rate_per_sec: int = 15, capacity: Optional[int] = None):
        if rate_per_sec <= 0:
            raise ValueError(f"Rate must be positive integer, got {rate_per_sec}")
        self.rate_per_sec = rate_per_sec
        self.capacity = capacity if capacity is not None else 2 * rate_per_sec

        self.tokens: int = self.capacity
        self.ns_per_token: int = 1_000_000_000 // rate_per_sec
        self.last_refill_ns: int = time.perf_counter_ns()
        self.remainder_ns: int = 0

    def refill(self, now_ns: Optional[int] = None) -> int:
        """Refills tokens based on elapsed nanoseconds. Returns current available tokens."""
        if now_ns is None:
            now_ns = time.perf_counter_ns()

        elapsed_ns = (now_ns - self.last_refill_ns) + self.remainder_ns
        if elapsed_ns >= self.ns_per_token:
            new_tokens = elapsed_ns // self.ns_per_token
            self.remainder_ns = elapsed_ns % self.ns_per_token
            self.tokens = min(self.capacity, self.tokens + new_tokens)
            self.last_refill_ns = now_ns

        return self.tokens

    def acquire(self, now_ns: Optional[int] = None) -> bool:
        """
        Attempts to acquire 1 token from the bucket.
        Returns True if acquired (allowed), False if rate-limited.
        """
        current_tokens = self.refill(now_ns)
        if current_tokens >= 1:
            self.tokens -= 1
            return True
        return False


class PriorityShareQueue:
    """
    Submission queue prioritizing mainnet block hits over standard shares.
    Block hits bypass the token bucket pacing entirely.
    """
    def __init__(self, maxsize: int = 64):
        self.maxsize = maxsize
        self.high_priority_blocks: list[ShareCandidate] = []
        self.normal_priority_shares: list[ShareCandidate] = []

    def push(self, candidate: ShareCandidate, is_block_hit: bool) -> bool:
        """
        Pushes candidate into queue.
        Block hits go to high_priority_blocks (bypassing rate bucket).
        Standard shares go to normal_priority_shares.
        """
        if is_block_hit:
            self.high_priority_blocks.append(candidate)
            return True

        if len(self.normal_priority_shares) >= self.maxsize:
            # Bounded queue drops candidate shares (NEVER drops block solutions)
            return False

        self.normal_priority_shares.append(candidate)
        return True

    def pop(self) -> Optional[tuple[ShareCandidate, bool]]:
        """
        Pops next available candidate.
        Returns (candidate, is_block_hit) or None if empty.
        High priority block hits are ALWAYS returned first.
        """
        if self.high_priority_blocks:
            return self.high_priority_blocks.pop(0), True
        if self.normal_priority_shares:
            return self.normal_priority_shares.pop(0), False
        return None

    def empty(self) -> bool:
        return not self.high_priority_blocks and not self.normal_priority_shares
