"""Evidence telemetry — counters only when measured; never fabricate."""
from __future__ import annotations

import threading
from typing import Optional


class EvidenceTelemetry:
    """Process-local measured counters.

    ``get(name)`` returns ``None`` for unknown metrics (Rule 7 — never invent).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {}

    def incr(self, name: str, amount: int = 1) -> None:
        if amount < 0:
            raise ValueError("amount must be non-negative")
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + amount

    def measure(self, name: str, value: int) -> None:
        """Set a measured absolute counter value."""
        with self._lock:
            self._counters[name] = int(value)

    def get(self, name: str) -> Optional[int]:
        with self._lock:
            if name not in self._counters:
                return None
            return self._counters[name]

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counters)

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()


__all__ = ["EvidenceTelemetry"]
