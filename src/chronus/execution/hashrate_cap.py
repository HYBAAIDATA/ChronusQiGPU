"""Hard ceiling on hashes this process may start per second.

1 EH/s is 10**18 hashes per second. Braiins Pool's combined hashrate is about
15 EH/s; this process will not schedule work above 1 EH/s. The ceiling is a
limit on work started here. It is not a measurement of device hashrate.
"""

from __future__ import annotations

import math
import time
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, Iterator

HASHRATE_CAP_EH_S = 1
HASHES_PER_EH = 10**18
HASHRATE_CAP_H_S = HASHES_PER_EH
_NS_PER_SECOND = 1_000_000_000


def _as_eh(value: float) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("hashrate must be a number of EH/s")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("hashrate must be finite")
    return value if isinstance(value, Decimal) else Decimal(str(value))


def require_eh_s(value: float, *, ceiling: float = HASHRATE_CAP_EH_S) -> float:
    """Return ``value`` when it is inside (0, ceiling] and the hard 1 EH/s cap."""
    amount = _as_eh(value)
    limit = min(_as_eh(ceiling), Decimal(HASHRATE_CAP_EH_S))
    if amount <= 0 or amount > limit:
        raise ValueError(f"hashrate {value} EH/s exceeds the {limit} EH/s cap")
    return float(amount)


def hashes_per_second(eh_s: float) -> int:
    """Convert an accepted EH/s value into an integer hash rate."""
    amount = _as_eh(require_eh_s(eh_s))
    hashes = int((amount * HASHES_PER_EH).to_integral_value(rounding=ROUND_HALF_UP))
    if hashes < 1 or hashes > HASHRATE_CAP_H_S:
        raise ValueError(f"hashrate {eh_s} EH/s exceeds the 1 EH/s cap")
    return hashes


class HashrateCap:
    """Integer token bucket. Burst is one second at the cap, then the rate holds."""

    def __init__(
        self,
        cap_h_s: int = HASHRATE_CAP_H_S,
        *,
        clock: Callable[[], int] | None = None,
    ) -> None:
        if type(cap_h_s) is not int or isinstance(cap_h_s, bool):
            raise ValueError("cap_h_s must be an integer hash rate")
        if not 1 <= cap_h_s <= HASHRATE_CAP_H_S:
            raise ValueError(f"cap_h_s {cap_h_s} exceeds the 1 EH/s cap")
        self.cap_h_s = cap_h_s
        self._clock = clock or time.perf_counter_ns
        self._origin_ns = self._clock()
        self._used = 0

    def _now(self, now_ns: int | None) -> int:
        if now_ns is None:
            return self._clock()
        if type(now_ns) is not int or isinstance(now_ns, bool):
            raise ValueError("now_ns must be an integer")
        return now_ns

    def available(self, now_ns: int | None = None) -> int:
        elapsed = self._now(now_ns) - self._origin_ns
        if elapsed < 0:
            elapsed = 0
        entitled = self.cap_h_s + (self.cap_h_s * elapsed) // _NS_PER_SECOND
        remaining = entitled - self._used
        return remaining if remaining > 0 else 0

    def allow(self, requested: int, now_ns: int | None = None) -> int:
        """Return how many of ``requested`` hashes may start now, and charge them."""
        if type(requested) is not int or isinstance(requested, bool) or requested < 0:
            raise ValueError("requested hash count must be a non-negative integer")
        granted = min(requested, self.available(now_ns))
        self._used += granted
        return granted

    def wait_ns(self, now_ns: int | None = None) -> int:
        """Nanoseconds until one more hash is allowed. Zero when one is available."""
        now = self._now(now_ns)
        if self.available(now) > 0:
            return 0
        need = self._used + 1 - self.cap_h_s
        if need <= 0:
            return 0
        elapsed_needed = (need * _NS_PER_SECOND + self.cap_h_s - 1) // self.cap_h_s
        elapsed = now - self._origin_ns
        if elapsed < 0:
            elapsed = 0
        if elapsed >= elapsed_needed:
            return 0
        return elapsed_needed - elapsed


_PROCESS_CAP = HashrateCap()


def process_cap() -> HashrateCap:
    return _PROCESS_CAP


def set_process_limit_eh_s(eh_s: float) -> HashrateCap:
    """Replace the process limit. The value cannot exceed 1 EH/s."""
    global _PROCESS_CAP
    _PROCESS_CAP = HashrateCap(hashes_per_second(eh_s))
    return _PROCESS_CAP


@contextmanager
def override_process_cap(cap: HashrateCap) -> Iterator[HashrateCap]:
    """Install ``cap`` for the duration of a test and then restore the previous one."""
    global _PROCESS_CAP
    previous = _PROCESS_CAP
    _PROCESS_CAP = cap
    try:
        yield cap
    finally:
        _PROCESS_CAP = previous
