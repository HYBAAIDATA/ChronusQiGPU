"""Production-shaped Chronus control plane and evidence-bound transaction loop."""

from __future__ import annotations

import os
import platform
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .abi import Workload, WorkloadResult, digest_json
from .adapters import ExecutionAdapter, default_adapters
from .attestation import extend_chain
from .evidence import EvidenceLedger
from .memory import VirtualMemoryPlane
from .optimizer import ClosedLoopOptimizer
from .planner import ChronusPlanner, CostVector, GeodesicRouter


class RuntimeInvariantError(RuntimeError):
    pass


@dataclass(frozen=True)
class Quota:
    max_workloads: int = 1000
    max_input_bytes: int = 16 * 1024 * 1024
    max_in_flight: int = 8


@dataclass(frozen=True)
class RuntimeConfig:
    store_root: str = ".chronus-virtual-igpu"
    include_emulator: bool = True
    require_hardware: bool = False
    default_quota: Quota = Quota()
    max_in_flight: int = 64
    signing_key_env: str = "CHRONUS_EVIDENCE_HMAC_KEY"


class RuntimeDaemon:
    def __init__(
        self,
        config: RuntimeConfig = RuntimeConfig(),
        adapters: Iterable[ExecutionAdapter] | None = None,
    ):
        self.config = config
        self.adapters = {
            a.id: a
            for a in (
                list(adapters)
                if adapters is not None
                else default_adapters(config.include_emulator)
            )
        }
        healthy = [a for a in self.adapters.values() if a.health().get("available")]
        if not healthy:
            raise RuntimeInvariantError("no execution adapter is available")
        if config.require_hardware and all(a.kind.value == "cpu_emulator" for a in healthy):
            raise RuntimeInvariantError("hardware required but only CPU emulator is available")
        self.memory = VirtualMemoryPlane(config.store_root)
        key = os.getenv(config.signing_key_env, "").encode() or None
        self.ledger = EvidenceLedger(config.store_root, key)
        self.planner = ChronusPlanner(self.ledger)
        self.optimizer = ClosedLoopOptimizer(
            os.path.join(config.store_root, "optimizer-state.json")
        )
        self.routes = GeodesicRouter()
        for adapter in healthy:
            priority = max(-100, min(100, int(adapter.priority)))
            self.routes.connect(
                "intent", adapter.id, CostVector(latency=float(100 - priority) / 100)
            )
        self.quotas: dict[str, Quota] = {}
        self.usage: dict[str, int] = {}
        self.in_flight: dict[str, int] = {}
        self.refusals: list[dict[str, Any]] = []
        self.negotiations: list[dict[str, Any]] = []
        self.results: dict[str, WorkloadResult] = {}
        self._pending: set[str] = set()
        self._cancelled: set[str] = set()
        self._running = True
        self._lock = threading.RLock()
        self._capacity = threading.BoundedSemaphore(max(1, config.max_in_flight))

    def start(self):
        self._running = True

    def stop(self):
        self._running = False
        self.memory.checkpoint("shutdown")

    def cancel(self, workload_id: str):
        with self._lock:
            self._cancelled.add(workload_id)

    def _admit(self, w: Workload):
        if not self._running:
            raise RuntimeInvariantError("runtime is stopped")
        if w.deadline and datetime.fromisoformat(w.deadline) <= datetime.now(timezone.utc):
            raise RuntimeInvariantError("workload deadline has expired")
        q = self.quotas.get(w.tenant, self.config.default_quota)
        size = len(str(w.as_dict()).encode())
        if self.usage.get(w.tenant, 0) >= q.max_workloads or size > q.max_input_bytes:
            raise RuntimeInvariantError("tenant quota exceeded")
        if self.in_flight.get(w.tenant, 0) >= q.max_in_flight:
            raise RuntimeInvariantError("tenant backpressure limit exceeded")
        if w.id in self.results or w.id in self._pending:
            raise RuntimeInvariantError("duplicate workload id")

    def _select(self, w: Workload):
        healthy = [
            a for a in self.adapters.values() if a.health().get("available") and a.supports(w.kind)
        ]
        if not healthy:
            refusal = {
                "workload_id": w.id,
                "kind": w.kind.value,
                "reason": "no healthy adapter supports workload",
            }
            self.refusals.append(refusal)
            raise RuntimeInvariantError(refusal["reason"])
        manifests = [a.capability_manifest().as_dict() for a in healthy]
        try:
            plan = self.planner.select(w, manifests, self.routes)
        except Exception as exc:
            refusal = {
                "workload_id": w.id,
                "kind": w.kind.value,
                "reason": f"planning failed: {exc}",
            }
            self.refusals.append(refusal)
            raise RuntimeInvariantError(refusal["reason"]) from exc
        chosen = self.adapters[plan.adapter_id]
        record = {
            "workload_id": w.id,
            "adapter_id": chosen.id,
            "policy": "evidence_geodesic_lucas_pisot_v1",
            "candidates": [a.id for a in healthy],
            "plan": plan.as_dict(),
        }
        record["attestation"] = list(extend_chain((), record))
        self.negotiations.append(record)
        return chosen, plan, record

    def submit(self, w: Workload) -> WorkloadResult:
        with self._lock:
            self._admit(w)
            self._pending.add(w.id)
            self.in_flight[w.tenant] = self.in_flight.get(w.tenant, 0) + 1
        if not self._capacity.acquire(timeout=5):
            with self._lock:
                self._pending.discard(w.id)
                self.in_flight[w.tenant] -= 1
            raise RuntimeInvariantError("runtime backpressure capacity exceeded")
        try:
            if w.id in self._cancelled:
                raise RuntimeInvariantError("workload cancelled before execution")
            adapter, plan, negotiation = self._select(w)
            result = adapter.execute_planned(w, plan)
            if (
                result.status != "ok"
                or result.digest != digest_json(result.output)
                or not result.attestation
            ):
                raise RuntimeInvariantError("adapter result invariant failed")
            if w.id in self._cancelled:
                raise RuntimeInvariantError("workload cancelled")
            evidence = {
                "workload": {
                    "id": w.id,
                    "tenant": w.tenant,
                    "operation": w.kind.value,
                    "input_hash": digest_json(w.input),
                },
                "planner": plan.as_dict(),
                "substrate": {
                    "adapter_id": adapter.id,
                    "backend": adapter.kind.value,
                    "manifest": adapter.capability_manifest().as_dict(),
                },
                "execution": {
                    "status": "ok",
                    "hardware_executed": adapter.kind.value != "cpu_emulator",
                    "wall_time_ns": result.wall_time_ns,
                    "device_time_ns": result.device_time_ns,
                    "energy_j": result.energy_j,
                    "temperature_c": result.temperature_c,
                },
                "validation": {
                    "passed": True,
                    "authority": "adapter-plus-result-digest",
                    "output_hash": result.digest,
                },
                "provenance": {
                    "runtime": "virtual_igpu_v1",
                    "python": platform.python_version(),
                    "adapter_fingerprint": adapter.attest().fingerprint,
                },
            }
            receipt = self.ledger.append(evidence)
            persisted = self.memory.persist(
                w, result, {**negotiation, "ledger_digest": receipt.digest}
            )
            final = WorkloadResult(
                **{
                    **result.as_dict(),
                    "evidence_digest": receipt.digest,
                    "object_id": persisted.object_id,
                }
            )
            with self._lock:
                self.results[w.id] = final
                self.usage[w.tenant] = self.usage.get(w.tenant, 0) + 1
            return final
        finally:
            self._capacity.release()
            with self._lock:
                self._pending.discard(w.id)
                self.in_flight[w.tenant] = max(0, self.in_flight.get(w.tenant, 1) - 1)

    def adapter_report(self):
        return [
            {
                "id": a.id,
                "kind": a.kind.value,
                "capabilities": sorted(c.value for c in a.capabilities),
                "manifest": a.capability_manifest().as_dict(),
                "health": a.health(),
                "attestation": a.attest().as_dict(),
            }
            for a in sorted(self.adapters.values(), key=lambda x: x.id)
        ]

    def capabilities(self):
        return sorted(
            {
                c.value
                for a in self.adapters.values()
                if a.health().get("available")
                for c in a.capabilities
            }
        )

    def health(self):
        return {
            "running": self._running,
            "healthy_adapters": sum(
                bool(a.health().get("available")) for a in self.adapters.values()
            ),
            "in_flight": sum(self.in_flight.values()),
            "evidence_records": len(self.ledger.query(limit=1000)),
            "last_successful_execution": self.ledger.query(limit=1)[0]
            if self.ledger.query(limit=1)
            else "Unavailable",
        }
