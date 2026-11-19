"""Lifecycle helpers for maintained Chronus entrypoints."""
from __future__ import annotations
from enum import Enum
import signal
import threading
import time

class LifecycleState(str, Enum):
    INIT = "INIT"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"

class ShutdownSignals:
    """Notify with a scalar; Event.set takes a lock and is not signal-reentrant."""
    def __init__(self) -> None:
        self.requested = False
        self._previous = {}

    def _notify(self, signum, frame) -> None:
        self.requested = True

    def __enter__(self) -> "ShutdownSignals":
        if threading.current_thread() is threading.main_thread():
            try:
                for sig in (signal.SIGINT, signal.SIGTERM):
                    self._previous[sig] = signal.getsignal(sig)
                    signal.signal(sig, self._notify)
            except BaseException:
                self.__exit__(None, None, None)
                raise
        return self

    def __exit__(self, *exc) -> None:
        for sig, previous in self._previous.items():
            signal.signal(sig, previous)
        self._previous.clear()

def join_until(threads: list[threading.Thread], deadline_ns: int) -> list[str]:
    """One monotonic join budget; report survivors rather than claiming clean stop."""
    for thread in threads:
        if thread is threading.current_thread() or thread.ident is None:
            continue
        thread.join(timeout=max(0, deadline_ns - time.monotonic_ns()) / 1_000_000_000)
    return [thread.name for thread in threads if thread.is_alive()]
