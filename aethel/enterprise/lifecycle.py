"""Composition root — ordered start/stop for shared THESEUS/OVID custody."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable, Optional

from .custody import EnterpriseCustody, compose
from .entangled_custody import EntangledCustodyFabric, SystemDataPort
from .hooks import SecurityHook
from .telemetry import EvidenceTelemetry


class CompositionRoot:
    """Ordered lifecycle for the shared data substrate.

    Start order:
      1. Open/recover enterprise custody (THESEUS).
      2. Bind one OVID-lineage / THESEUS-custody entanglement fabric to it.
      3. Mark the shared substrate ready.
      4. Start registered consumers; every memory/data consumer obtains a
         bounded :class:`SystemDataPort` over this same fabric.

    Stop order:
      1. Halt consumers.
      2. Flush / close THESEUS custody.
      3. Release the shared fabric reference.

    The fabric is shared identity, not a private store per subsystem.  Owner
    authority remains with each producer; THESEUS owns custody and OVID owns
    transformation/lineage.
    """

    def __init__(
        self,
        root: Path | str,
        *,
        tenant: str = "default",
        hmac_key: Optional[bytes] = None,
        key_id: str = "k1",
        require_authenticity: bool = True,
        allow_insecure_dev_key: bool = False,
        previous_hmac_keys: Optional[list[bytes]] = None,
        hook: Optional[SecurityHook] = None,
        chronus_accel: bool = False,
        telemetry: Optional[EvidenceTelemetry] = None,
    ) -> None:
        self._root = Path(root)
        self._tenant = tenant
        self._hmac_key = hmac_key
        self._key_id = key_id
        self._require_authenticity = require_authenticity
        self._allow_insecure_dev_key = allow_insecure_dev_key
        self._previous_hmac_keys = previous_hmac_keys
        self._hook = hook
        self._chronus_accel = chronus_accel
        self.telemetry = telemetry or EvidenceTelemetry()
        self.custody: Optional[EnterpriseCustody] = None
        self.fabric: Optional[EntangledCustodyFabric] = None
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
            if self._started and self.custody is not None and self.fabric is not None:
                return self.custody
            # 1. Recover THESEUS before any consumer.
            self.custody = compose(
                self._root,
                tenant=self._tenant,
                hmac_key=self._hmac_key,
                key_id=self._key_id,
                require_authenticity=self._require_authenticity,
                allow_insecure_dev_key=self._allow_insecure_dev_key,
                previous_hmac_keys=self._previous_hmac_keys,
                hook=self._hook,
                chronus_accel=self._chronus_accel,
                telemetry=self.telemetry,
            )
            health = self.custody.health()
            if not health.get("ready"):
                raise RuntimeError("custody failed readiness after recover")

            # 2. Bind exactly one shared OVID/THESEUS fabric to this recovered
            # custody root.  No consumer below is allowed to create a substitute
            # private fabric through this lifecycle.
            self.fabric = EntangledCustodyFabric(self.custody)
            self.telemetry.incr("entangled_custody_ready")

            # 3. Start consumers only after shared custody + lineage are ready.
            for name, start_fn, _stop in self._consumers:
                start_fn()
                self.telemetry.incr(f"consumer_start:{name}")
            self._started = True
            self.telemetry.incr("lifecycle_start")
            return self.custody

    def data_port(self, system: str) -> SystemDataPort:
        """Return this lifecycle's bounded port over the one shared fabric."""
        if not self._started or self.fabric is None or self.custody is None:
            raise RuntimeError("shared THESEUS/OVID fabric is not started")
        return self.fabric.port(system)

    def readiness(self) -> dict[str, Any]:
        if self.custody is None or self.fabric is None:
            return {"ready": False, "reason": "not_started"}
        h = self.custody.health()
        fabric = self.fabric.status()
        return {
            "ready": bool(h.get("ready") and self._started),
            "custody": h,
            "entangled_custody": fabric,
            "consumers": [n for n, _, _ in self._consumers],
        }

    def stop(self) -> None:
        """Halt consumers then flush/close shared custody."""
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
            self.fabric = None
            self.custody = None
            self._started = False
            self.telemetry.incr("lifecycle_stop")

    def flush(self) -> None:
        """Ensure journal durability; recover re-seals incomplete state."""
        if self.custody is not None:
            # Re-open journal recover is a flush surrogate for JSONL WAL.
            self.custody.journal.recover()
            self.telemetry.incr("lifecycle_flush")


__all__ = ["CompositionRoot"]
