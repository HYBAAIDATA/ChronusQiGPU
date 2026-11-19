"""Lifecycle helpers for maintained Chronus entrypoints."""
from __future__ import annotations
import asyncio
from enum import Enum
import logging
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


class OwnedWorkerGroup:
    """Own native workers so asyncio.run cannot silently wait forever on its executor.

    A Python thread cannot be forcibly stopped safely. A live worker at the
    deadline is a degraded shutdown, not a successful cancellation.
    """
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._threads: list[threading.Thread] = []

    async def call(self, name, function, *args):
        loop = asyncio.get_running_loop()
        result = loop.create_future()

        def publish(value, error):
            if result.done():
                if error is not None:
                    logging.getLogger(__name__).error("Late worker failure: %s (%s)", name, type(error).__name__)
                return
            if error is None:
                result.set_result(value)
            elif isinstance(error, StopIteration):
                result.set_exception(RuntimeError("Worker raised StopIteration"))
            else:
                result.set_exception(error)

        def work():
            try:
                value, error = function(*args), None
            except BaseException as exc:
                value, error = None, exc
            try:
                loop.call_soon_threadsafe(publish, value, error)
            except RuntimeError:
                # Loop already closed after a recorded degraded stop.
                if error is not None:
                    logging.getLogger(__name__).error("Worker failed after shutdown: %s (%s)", name, type(error).__name__)

        thread = threading.Thread(target=work, name=name, daemon=True)
        with self._lock:
            self._threads = [worker for worker in self._threads if worker.is_alive()]
            self._threads.append(thread)
            try:
                thread.start()
            except BaseException:
                self._threads.remove(thread)
                raise
        return await result

    def join_until(self, deadline_ns: int) -> list[str]:
        with self._lock:
            threads = list(self._threads)
        return join_until(threads, deadline_ns)
