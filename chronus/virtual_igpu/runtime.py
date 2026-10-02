"""Control plane and closed transaction runtime for the Virtual iGPU."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import threading
from typing import Any, Iterable

from .abi import Workload, WorkloadResult
from .adapters import ExecutionAdapter, default_adapters
from .attestation import extend_chain
from .memory import VirtualMemoryPlane


class RuntimeInvariantError(RuntimeError):
    pass


@dataclass(frozen=True)
class Quota:
    max_workloads: int = 1000
    max_input_bytes: int = 16 * 1024 * 1024


@dataclass(frozen=True)
class RuntimeConfig:
    store_root: str = ".chronus-virtual-igpu"
    include_emulator: bool = True
    require_hardware: bool = False
    default_quota: Quota = Quota()


class RuntimeDaemon:
    def __init__(
        self,
        config: RuntimeConfig = RuntimeConfig(),
        adapters: Iterable[ExecutionAdapter] | None = None,
    ) -> None:
        self.config = config
        self.adapters = {
            adapter.id: adapter for adapter in (
                list(adapters) if adapters is not None else default_adapters(config.include_emulator)
            )
        }
        healthy = [a for a in self.adapters.values() if a.health().get("available")]
        if not healthy:
            raise RuntimeInvariantError("no execution adapter is available")
        if config.require_hardware and all(a.kind.value == "cpu_emulator" for a in healthy):
            raise RuntimeInvariantError("hardware required but only CPU emulator is available")
        self.memory = VirtualMemoryPlane(config.store_root)
        self.quotas: dict[str, Quota] = {}
        self.usage: dict[str, int] = {}
        self.refusals: list[dict[str, Any]] = []
        self.negotiations: list[dict[str, Any]] = []
        self.results: dict[str, WorkloadResult] = {}
        self._lock = threading.RLock()

    def _admit(self, workload: Workload) -> None:
        deadline = (
            datetime.fromisoformat(workload.deadline) if workload.deadline else None
        )
        if deadline is not None and deadline <= datetime.now(timezone.utc):
            raise RuntimeInvariantError("workload deadline has expired")
        quota = self.quotas.get(workload.tenant, self.config.default_quota)
        count = self.usage.get(workload.tenant, 0)
        size = len(str(workload.as_dict()).encode())
        if count >= quota.max_workloads or size > quota.max_input_bytes:
            raise RuntimeInvariantError("tenant quota exceeded")

    def _select(self, workload: Workload) -> tuple[ExecutionAdapter, dict[str, Any]]:
        candidates = [
            adapter for adapter in self.adapters.values()
            if adapter.health().get("available") and adapter.supports(workload.kind)
        ]
        if not candidates:
            refusal = {
                "workload_id": workload.id,
                "kind": workload.kind.value,
                "reason": "no healthy adapter supports workload",
            }
            self.refusals.append(refusal)
            raise RuntimeInvariantError(refusal["reason"])
        candidates.sort(key=lambda adapter: (-adapter.priority, adapter.id))
        chosen = candidates[0]
        record = {
            "workload_id": workload.id,
            "adapter_id": chosen.id,
            "policy": "priority_then_adapter_id",
            "candidates": [a.id for a in candidates],
            "attestation": list(
                extend_chain((), {
                    "workload_id": workload.id,
                    "chosen": chosen.id,
                    "candidates": [a.id for a in candidates],
                })
            ),
        }
        self.negotiations.append(record)
        return chosen, record

    def submit(self, workload: Workload) -> WorkloadResult:
        with self._lock:
            if workload.id in self.results:
                raise RuntimeInvariantError("duplicate workload id")
            self._admit(workload)
            adapter, negotiation = self._select(workload)
            result = adapter.execute(workload)
            if result.status != "ok":
                raise RuntimeInvariantError("adapter returned unsuccessful result")
            persisted = self.memory.persist(workload, result, negotiation)
            final = WorkloadResult(
                **{
                    **result.as_dict(),
                    "evidence_digest": persisted.evidence_digest,
                    "object_id": persisted.object_id,
                }
            )
            self.results[workload.id] = final
            self.usage[workload.tenant] = self.usage.get(workload.tenant, 0) + 1
            return final

    def adapter_report(self) -> list[dict[str, Any]]:
        return [
            {
                "id": adapter.id,
                "kind": adapter.kind.value,
                "capabilities": sorted(c.value for c in adapter.capabilities),
                "health": adapter.health(),
                "attestation": adapter.attest().as_dict(),
            }
            for adapter in sorted(self.adapters.values(), key=lambda a: a.id)
        ]

    def capabilities(self) -> list[str]:
        return sorted({
            capability.value
            for adapter in self.adapters.values()
            if adapter.health().get("available")
            for capability in adapter.capabilities
        })