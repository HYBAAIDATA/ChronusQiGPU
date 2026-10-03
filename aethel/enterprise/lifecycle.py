"""Composition root — ordered start/stop for enterprise custody."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable, Optional

from .custody import EnterpriseCustody, compose
from .hooks import SecurityHook
from .telemetry import EvidenceTelemetry


class CompositionRoot:
    """Ordered lifecycle: recover Theseus before consumers; halt consumers before close.

    Start order:
      1. Open/recover enterprise custody (Theseus)
      2. Mark ready
      3. Start registered consumers

    Stop order:
      1. Halt consumers
      2. Flush / close custody
    """

    def __init__(
        self,
        root: Path | str,
        *,
        tenant: str = "default",
        hmac_key: bytes = b"enterprise-dev-key-change-me",
        hook: Optional[SecurityHook] = None,
        chronus_accel: bool = False,
        telemetry: Optional[EvidenceTelemetry] = None,
    ) -> None:
        self._root = Path(root)
        self._tenant = tenant
        self._hmac_key = hmac_key
        self._hook = hook
        self._chronus_accel = chronus_accel
        self.telemetry = telemetry or EvidenceTelemetry()
        self.custody: Optional[EnterpriseCustody] = None
        self._consumers: list[tuple[str, Callable[[], None], Callable[[], None]]] = []
        self._started = False
        self._lock = threading.Lock()

    def register_consumer(
        self,
        name: str,
        start_fn: Callable[[], None],
        stop_fn: Callable[[], None],
    ) -> None:
        self._consumers.append((name, start_fn, stop_fn))

    def start(self) -> EnterpriseCustody:
        with self._lock:
            if self._started and self.custody is not None:
                return self.custody
            # 1. Recover Theseus before any consumer.
            self.custody = compose(
                self._root,
                tenant=self._tenant,
                hmac_key=self._hmac_key,
                hook=self._hook,
                chronus_accel=self._chronus_accel,
                telemetry=self.telemetry,
            )
            health = self.custody.health()
            if not health.get("ready"):
                raise RuntimeError("custody failed readiness after recover")
            # 2. Start consumers
            for name, start_fn, _stop in self._consumers:
                start_fn()
                self.telemetry.incr(f"consumer_start:{name}")
            self._started = True
            self.telemetry.incr("lifecycle_start")
            return self.custody

    def readiness(self) -> dict[str, Any]:
        if self.custody is None:
            return {"ready": False, "reason": "not_started"}
        h = self.custody.health()
        return {
            "ready": bool(h.get("ready") and self._started),
            "custody": h,
            "consumers": [n for n, _, _ in self._consumers],
        }

    def stop(self) -> None:
        """Halt consumers then flush/close custody."""
        with self._lock:
            # Halt consumers first.
            for name, _start, stop_fn in reversed(self._consumers):
                try:
                    stop_fn()
                    self.telemetry.incr(f"consumer_stop:{name}")
                except Exception:
                    self.telemetry.incr(f"consumer_stop_error:{name}")
            if self.custody is not None:
                self.custody.close()
            self._started = False
            self.telemetry.incr("lifecycle_stop")

    def flush(self) -> None:
        """Ensure journal durability; recover re-seals incomplete state."""
        if self.custody is not None:
            # Re-open journal recover is a flush surrogate for JSONL WAL.
            self.custody.journal.recover()
            self.telemetry.incr("lifecycle_flush")


__all__ = ["CompositionRoot"]
