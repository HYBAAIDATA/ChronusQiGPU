"""Hard ceiling on hashes this process may start per second.

1 EH/s is 10**18 hashes per second. Braiins Pool's combined hashrate is about
15 EH/s; this process will not schedule work above 1 EH/s. The ceiling is a
limit on work started here. It is not a measurement of device hashrate.
"""

from __future__ import annotations

import math
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
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
    """Integer token bucket. The balance never exceeds one second at the current rate."""

    def __init__(
        self,
        cap_h_s: int = HASHRATE_CAP_H_S,
        *,
        clock: Callable[[], int] | None = None,
    ) -> None:
        self.cap_h_s = _checked_rate(cap_h_s)
        self._clock = clock or time.perf_counter_ns
        self._tokens = self.cap_h_s
        self._last_ns = self._clock()
        self._carry = 0
        self._lock = threading.Lock()

    def _now(self, now_ns: int | None) -> int:
        if now_ns is None:
            return self._clock()
        if type(now_ns) is not int or isinstance(now_ns, bool):
            raise ValueError("now_ns must be an integer")
        return now_ns

    def _refill(self, now_ns: int) -> None:
        elapsed = now_ns - self._last_ns
        if elapsed < 0:
            elapsed = 0
        budget = self.cap_h_s * elapsed + self._carry
        earned = budget // _NS_PER_SECOND
        self._carry = budget % _NS_PER_SECOND
        self._last_ns = now_ns
        self._tokens = min(self.cap_h_s, self._tokens + earned)

    def available(self, now_ns: int | None = None) -> int:
        with self._lock:
            self._refill(self._now(now_ns))
            return self._tokens

    def allow(self, requested: int, now_ns: int | None = None) -> int:
        """Return how many of ``requested`` hashes may start now, and charge them."""
        if type(requested) is not int or isinstance(requested, bool) or requested < 0:
            raise ValueError("requested hash count must be a non-negative integer")
        with self._lock:
            self._refill(self._now(now_ns))
            granted = requested if requested < self._tokens else self._tokens
            self._tokens -= granted
            return granted

    def refund(self, count: int, now_ns: int | None = None) -> None:
        """Return unused hashes from a grant. The balance still cannot exceed one second."""
        if type(count) is not int or isinstance(count, bool) or count < 0:
            raise ValueError("refund count must be a non-negative integer")
        if count == 0:
            return
        with self._lock:
            self._refill(self._now(now_ns))
            self._tokens = min(self.cap_h_s, self._tokens + count)

    def set_rate(self, cap_h_s: int, now_ns: int | None = None) -> None:
        """Change the rate without granting another full burst."""
        cap_h_s = _checked_rate(cap_h_s)
        with self._lock:
            self._refill(self._now(now_ns))
            self.cap_h_s = cap_h_s
            if self._tokens > cap_h_s:
                self._tokens = cap_h_s

    def wait_ns(self, now_ns: int | None = None) -> int:
        """Nanoseconds until one more hash is allowed. Zero when one is available."""
        with self._lock:
            self._refill(self._now(now_ns))
            if self._tokens > 0:
                return 0
            return (_NS_PER_SECOND - self._carry + self.cap_h_s - 1) // self.cap_h_s


def _checked_rate(cap_h_s: int) -> int:
    if type(cap_h_s) is not int or isinstance(cap_h_s, bool):
        raise ValueError("cap_h_s must be an integer hash rate")
    if not 1 <= cap_h_s <= HASHRATE_CAP_H_S:
        raise ValueError(f"cap_h_s {cap_h_s} exceeds the 1 EH/s cap")
    return cap_h_s


_PROCESS_CAP = HashrateCap()


def process_cap() -> HashrateCap:
    return _PROCESS_CAP


def set_process_limit_eh_s(eh_s: float) -> HashrateCap:
    """Set the process rate. A repeat of the same rate keeps the hashes already charged."""
    cap = process_cap()
    cap.set_rate(hashes_per_second(eh_s))
    return cap


def limit_file() -> Path:
    """File shared by the API process and a separately started miner."""
    override = os.environ.get("CHRONUS_HASHRATE_LIMIT_FILE", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".local/share/hyba-mine/hashrate-cap"


def publish_limit_file(eh_s: float) -> None:
    """Write the active EH/s limit for other processes to read."""
    require_eh_s(eh_s)
    path = limit_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        temporary.write_text(f"{eh_s}\n", encoding="ascii")
        # Windows can briefly reject a concurrent replacement while another
        # publisher is closing its handle to the same destination. Retry only
        # that transient sharing failure; the final attempt remains fail-closed.
        for attempt in range(8):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(0.005)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def read_published_limit() -> float | None:
    """Return the shared rate, or None when the file is missing or not a valid rate."""
    try:
        text = limit_file().read_bytes().decode("ascii")
    except (OSError, UnicodeError):
        return None
    try:
        eh_s = require_eh_s(float(text.strip()))
        hashes_per_second(eh_s)
    except ValueError:
        return None
    return eh_s


def apply_published_limit() -> None:
    """Adopt the shared file when another process published a new rate."""
    eh_s = read_published_limit()
    if eh_s is None:
        return
    if process_cap().cap_h_s != hashes_per_second(eh_s):
        set_process_limit_eh_s(eh_s)


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
