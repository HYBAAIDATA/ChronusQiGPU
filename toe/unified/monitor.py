"""Health loop. Once started, it probes and retrains without another call."""

from __future__ import annotations

import threading
from typing import Callable


class HealthMonitor:
    def __init__(self, tick: Callable[[], None], interval: float = 0.05) -> None:
        self._tick_body = tick
        self.interval = interval
        self.ticks = 0
        self.retrains = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def tick_once(self) -> None:
        self.ticks += 1
        self._tick_body()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()

        def loop() -> None:
            while not self._stop.wait(self.interval):
                self.tick_once()

        self._thread = threading.Thread(target=loop, name="toe-health", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
