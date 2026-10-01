"""Hashrate governor: the rate the network sees stays under a set cap.

Pools and the network never observe hashes. They infer a miner's rate from
the work its shares and blocks prove: ``2**256 / (target + 1)`` expected
hashes per share. The governor therefore charges each window the larger of
the hashes it executed and the work its shares prove, so the cap holds
however the shares were found.

The cap is the lowest of

* ``hashrate.target_hs`` from the operator config (0 means no target),
* the configured ceiling (``hashrate.ceiling_hs``, 1 EH/s by default), and
* ``MAX_NETWORK_FRACTION`` (1%) of the network rate implied by the job's own
  ``nbits``: ``2**256 / (network target + 1) / 600 s``. No configuration can
  raise this one; only a test harness simulating a toy network constructs a
  governor without it.

Spending is a token bucket refilled at the cap with ``burst_s`` of headroom;
a window is admitted while the bucket is not in deficit.

The governor also reports share yield: shares found against the shares the
executed hashes would find by exhaustive search, with an exact 95% Poisson
interval. A lower bound above 1 is measured evidence that shares arrive
faster than search alone explains.
"""

from __future__ import annotations

import math
import time
from functools import lru_cache
from typing import Any, Callable

from .pow import compact_target

MAX_NETWORK_FRACTION = 0.01
BLOCK_INTERVAL_S = 600.0
DEFAULT_CEILING_HS = 1e18


def expected_hashes(target: int) -> float:
    """Hashes an exhaustive search needs on average to meet ``target``."""
    if target < 0:
        raise ValueError("target must be non-negative")
    return float((1 << 256) // (target + 1))


def _log_poisson_cdf(k: int, lam: float) -> float:
    if lam <= 0.0:
        return 0.0
    log_lam = math.log(lam)
    terms = [-lam + i * log_lam - math.lgamma(i + 1) for i in range(k + 1)]
    peak = max(terms)
    return peak + math.log(sum(math.exp(t - peak) for t in terms))


def _solve(predicate: Callable[[float], bool], lo: float, hi: float) -> float:
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if predicate(mid):
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


@lru_cache(maxsize=4096)
def poisson_interval(n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact (Garwood) interval for a Poisson mean given ``n`` events."""
    if n < 0:
        raise ValueError("count must be non-negative")
    tail = alpha / 2.0
    if n > 1000:
        # Wilson-Hilferty: within 0.1% of exact at this size.
        z = 1.959963984540054
        lower = n * (1 - 1 / (9 * n) - z / (3 * math.sqrt(n))) ** 3
        m = n + 1
        upper = m * (1 - 1 / (9 * m) + z / (3 * math.sqrt(m))) ** 3
        return lower, upper
    log_tail = math.log(tail)
    hi = max(10.0, 3.0 * n + 10.0)
    # P(X <= n; upper) = tail
    upper = _solve(lambda lam: _log_poisson_cdf(n, lam) <= log_tail, 0.0, hi)
    if n == 0:
        return 0.0, upper
    # P(X >= n; lower) = tail, i.e. P(X <= n - 1; lower) = 1 - tail
    log_head = math.log1p(-tail)
    lower = _solve(lambda lam: _log_poisson_cdf(n - 1, lam) <= log_head, 0.0, hi)
    return lower, upper


class HashrateGovernor:
    def __init__(
        self,
        *,
        target_hs: float = 0.0,
        ceiling_hs: float = DEFAULT_CEILING_HS,
        burst_s: float = 30.0,
        max_network_fraction: float | None = MAX_NETWORK_FRACTION,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if burst_s <= 0:
            raise ValueError("burst_s must be positive")
        self.burst_s = burst_s
        self.max_network_fraction = max_network_fraction
        self._clock = clock
        self.configure(target_hs=target_hs, ceiling_hs=ceiling_hs)
        self.network_hs: float | None = None
        self._tokens: float | None = None  # full on first use
        self._refilled_at = 0.0
        self.admitted = 0
        self.deferred = 0
        self.hashes = 0
        self.shares = 0
        self.expected_shares = 0.0
        self.charged_work = 0.0

    def configure(self, *, target_hs: float, ceiling_hs: float) -> None:
        for name, value in (("target_hs", target_hs), ("ceiling_hs", ceiling_hs)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a number")
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if ceiling_hs == 0:
            raise ValueError("ceiling_hs must be positive; stop mining to stop")
        self.target_hs = float(target_hs)
        self.ceiling_hs = min(float(ceiling_hs), DEFAULT_CEILING_HS)

    def observe_network(self, nbits: int | str) -> None:
        self.network_hs = expected_hashes(compact_target(nbits)) / BLOCK_INTERVAL_S

    @property
    def cap_hs(self) -> float:
        limits = [self.ceiling_hs]
        if self.target_hs > 0:
            limits.append(self.target_hs)
        if self.network_hs is not None and self.max_network_fraction is not None:
            limits.append(self.max_network_fraction * self.network_hs)
        return min(limits)

    def _refill(self) -> float:
        now = self._clock()
        capacity = self.cap_hs * self.burst_s
        if self._tokens is None:
            self._tokens = capacity
        else:
            self._tokens = min(capacity, self._tokens + self.cap_hs * (now - self._refilled_at))
        self._refilled_at = now
        return self._tokens

    def admit(self) -> bool:
        """True when a window may start now; the budget is not in deficit."""
        if self._refill() >= 0.0:
            self.admitted += 1
            return True
        self.deferred += 1
        return False

    def record(self, *, hashes: int, share_target: int | None, shares: int) -> float:
        """Charge one finished window; returns the work charged."""
        if hashes < 0 or shares < 0:
            raise ValueError("hashes and shares must be non-negative")
        tokens = self._refill()
        per_share = expected_hashes(share_target) if share_target is not None else 0.0
        charged = max(float(hashes), shares * per_share)
        self._tokens = tokens - charged
        self.hashes += hashes
        self.shares += shares
        if per_share > 0:
            self.expected_shares += hashes / per_share
        self.charged_work += charged
        return charged

    def share_yield(self) -> dict[str, Any]:
        expected = self.expected_shares
        if expected <= 0:
            return {"shares": self.shares, "expected": expected, "ratio": None, "ci95": None}
        lower, upper = poisson_interval(self.shares)
        return {
            "shares": self.shares,
            "expected": expected,
            "ratio": self.shares / expected,
            "ci95": [lower / expected, upper / expected],
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": "pythia.hashrate_governor/1",
            "cap_hs": self.cap_hs,
            "target_hs": self.target_hs,
            "ceiling_hs": self.ceiling_hs,
            "network_hs": self.network_hs,
            "max_network_fraction": self.max_network_fraction,
            "budget_hashes": self._tokens,
            "admitted": self.admitted,
            "deferred": self.deferred,
            "hashes": self.hashes,
            "charged_work": self.charged_work,
            "share_yield": self.share_yield(),
        }
