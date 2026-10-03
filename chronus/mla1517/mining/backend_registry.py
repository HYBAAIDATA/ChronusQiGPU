"""Fail-closed execution-backend registry for the production mining runtime.

Names are not capabilities.  A backend becomes selectable only after its
factory has produced an implementation and its health probe has passed.
Explicit backend requests never degrade to CPU.  ``auto`` follows a declared
ordered policy and records exactly why each stronger lane was skipped.
"""
from __future__ import annotations

import json
import os
import platform
import time
import uuid
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Iterable

SCHEMA = "pythia.execution-backend-registry/1"


class BackendKind(StrEnum):
    CPU = "CPU"
    GPU = "GPU"
    ASIC = "ASIC"
    SUPER_ASIC = "SUPER_ASIC"


class BackendUnavailable(RuntimeError):
    """No policy-permitted, capability-proven backend can execute work."""


@dataclass(frozen=True)
class BackendCapability:
    backend_id: str
    kind: BackendKind
    implementation: str
    available: bool
    healthy: bool
    device: str
    reason: str
    probed_at: float
    evidence: dict[str, Any]


@dataclass(frozen=True)
class BackendSelection:
    decision_id: str
    job_id: str
    epoch: str
    observation: dict[str, Any]
    available_actions: tuple[str, ...]
    selected_action: str
    reason: str
    execution_target: str
    result: str
    disposition: str
    timestamp: float
    software_revision: str


@dataclass
class _Provider:
    backend_id: str
    kind: BackendKind
    implementation: str
    factory: Callable[[], Any] | None
    health: Callable[[Any], tuple[bool, str, dict[str, Any]]]
    unavailable_reason: str


class BackendRegistry:
    """Own capability probes and policy-governed execution selection."""

    def __init__(self, *, software_revision: str = "unknown", evidence_path: str | Path | None = None):
        self.software_revision = software_revision or "unknown"
        self.evidence_path = Path(evidence_path) if evidence_path else None
        self._providers: dict[str, _Provider] = {}
        self._instances: dict[str, Any] = {}
        self._capabilities: dict[str, BackendCapability] = {}
        self.last_selection: BackendSelection | None = None

    def register(
        self,
        backend_id: str,
        kind: BackendKind,
        implementation: str,
        *,
        factory: Callable[[], Any] | None,
        health: Callable[[Any], tuple[bool, str, dict[str, Any]]] | None = None,
        unavailable_reason: str = "implementation not configured",
    ) -> None:
        if not backend_id or backend_id in self._providers:
            raise ValueError(f"invalid or duplicate backend id: {backend_id!r}")
        self._providers[backend_id] = _Provider(
            backend_id,
            kind,
            implementation,
            factory,
            health or self._default_health,
            unavailable_reason,
        )

    @staticmethod
    def _default_health(instance: Any) -> tuple[bool, str, dict[str, Any]]:
        healthy = bool(getattr(instance, "healthy", True))
        reason = "health probe passed" if healthy else "implementation reported unhealthy"
        return healthy, reason, {
            "reported_backend": getattr(instance, "backend", "Unavailable"),
            "reported_device": getattr(instance, "device", "Unavailable"),
        }

    def probe(self, backend_id: str) -> BackendCapability:
        provider = self._providers[backend_id]
        now = time.time()
        if provider.factory is None:
            cap = BackendCapability(
                backend_id, provider.kind, provider.implementation, False, False,
                "Unavailable", provider.unavailable_reason, now, {},
            )
        else:
            try:
                instance = provider.factory()
                healthy, reason, evidence = provider.health(instance)
                available = instance is not None and healthy
                cap = BackendCapability(
                    backend_id, provider.kind, provider.implementation, available, healthy,
                    str(getattr(instance, "device", "Unavailable")), reason, now, dict(evidence),
                )
                if available:
                    self._instances[backend_id] = instance
                else:
                    self._instances.pop(backend_id, None)
            except Exception as exc:
                self._instances.pop(backend_id, None)
                cap = BackendCapability(
                    backend_id, provider.kind, provider.implementation, False, False,
                    "Unavailable", f"capability probe failed: {type(exc).__name__}: {exc}", now, {},
                )
        self._capabilities[backend_id] = cap
        return cap

    def probe_all(self) -> dict[str, BackendCapability]:
        return {backend_id: self.probe(backend_id) for backend_id in self._providers}

    def select(
        self,
        requested: str,
        *,
        policy_order: Iterable[str],
        job_id: str = "Unavailable",
        epoch: str = "Unavailable",
    ) -> Any:
        capabilities = self.probe_all()
        order = tuple(policy_order)
        if requested != "auto":
            order = (requested,)
        unknown = [name for name in order if name not in capabilities]
        if unknown:
            raise BackendUnavailable(f"unknown backend(s): {', '.join(unknown)}")
        selectable = [name for name in order if capabilities[name].available and capabilities[name].healthy]
        selected = selectable[0] if selectable else "Unavailable"
        skipped = {
            name: capabilities[name].reason
            for name in order
            if name != selected
        }
        disposition = "accepted" if selected != "Unavailable" else "rejected"
        reason = (
            f"selected first capable backend in declared order {order}"
            if selected != "Unavailable"
            else f"no capable backend in declared order {order}"
        )
        decision = BackendSelection(
            decision_id=f"backend:{uuid.uuid4()}",
            job_id=job_id,
            epoch=epoch,
            observation={
                "requested": requested,
                "policy_order": list(order),
                "capabilities": {k: asdict(v) for k, v in capabilities.items()},
                "skipped": skipped,
            },
            available_actions=tuple(selectable),
            selected_action=selected,
            reason=reason,
            execution_target=selected,
            result="backend_bound" if selected != "Unavailable" else "no_backend_bound",
            disposition=disposition,
            timestamp=time.time(),
            software_revision=self.software_revision,
        )
        self.last_selection = decision
        self._append_evidence(decision)
        if selected == "Unavailable":
            detail = "; ".join(f"{name}: {capabilities[name].reason}" for name in order)
            raise BackendUnavailable(f"{reason}: {detail}")
        instance = self._instances[selected]
        setattr(instance, "backend_selection", asdict(decision))
        return instance

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "host": {"system": platform.system(), "machine": platform.machine()},
            "capabilities": {k: asdict(v) for k, v in self._capabilities.items()},
            "last_selection": asdict(self.last_selection) if self.last_selection else "Unavailable",
        }

    def _append_evidence(self, decision: BackendSelection) -> None:
        if self.evidence_path is None:
            return
        self.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(decision), sort_keys=True, separators=(",", ":")) + "\n"
        fd = os.open(self.evidence_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line.encode())
            os.fsync(fd)
        finally:
            os.close(fd)
