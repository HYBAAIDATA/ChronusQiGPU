"""Layer 4 — idempotent, backpressured, linearizable work queue."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from igpu.seam import store
from igpu.seam.types import (
    Distribution,
    Err,
    KernelName,
    Ok,
    Result,
    SeamError,
    new_id,
    now_iso,
)


@dataclass
class WorkItem:
    id: str
    job_id: str
    kernel: KernelName
    args: str
    priority: int
    deadline: Optional[str]
    idempotency_key: str
    submitted_at: str
    assigned_device: Optional[str]
    state: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "kernel": self.kernel.value,
            "args": self.args,
            "priority": self.priority,
            "deadline": self.deadline,
            "idempotency_key": self.idempotency_key,
            "submitted_at": self.submitted_at,
            "assigned_device": self.assigned_device,
            "state": self.state,
        }


@dataclass
class QueueState:
    queue_id: str
    device_id: str
    pending: int
    in_flight: int
    completed: int
    failed: int
    backpressure: bool
    threshold: int
    throughput: Distribution

    def as_dict(self) -> Dict[str, Any]:
        return {
            "queue_id": self.queue_id,
            "device_id": self.device_id,
            "pending": self.pending,
            "in_flight": self.in_flight,
            "completed": self.completed,
            "failed": self.failed,
            "backpressure": self.backpressure,
            "threshold": self.threshold,
            "throughput": self.throughput.as_dict(),
        }


def enqueue(caller: str, device_id: str, item: WorkItem) -> Result[str]:
    if store.get_cap(device_id) is None:
        return Err(SeamError.device_absent, device_id)
    if store.is_quarantined(device_id):
        return Err(SeamError.device_quarantined, device_id)
    with store.lock():
        q = store.queue_of(device_id)
        key = f"{item.idempotency_key}:{item.args}"
        for existing in q["pending"] + q["in_flight"]:
            if f"{existing.idempotency_key}:{existing.args}" == key:
                return Ok(existing.id)
        if len(q["in_flight"]) >= int(q["threshold"]):
            return Err(SeamError.rate_limited, f"in_flight={len(q['in_flight'])}")
        item.id = item.id or new_id("w")
        item.assigned_device = device_id
        item.state = "pending"
        item.submitted_at = item.submitted_at or now_iso()
        q["pending"].append(item)
        store.audit("enqueue", device_id=device_id, item_id=item.id, caller=caller)
        return Ok(item.id)


def peek(caller: str, device_id: str) -> Result[Optional[WorkItem]]:
    q = store.queue_of(device_id)
    if not q["pending"]:
        return Ok(None)
    return Ok(q["pending"][0])


def dequeue(caller: str, device_id: str) -> Result[Optional[WorkItem]]:
    with store.lock():
        q = store.queue_of(device_id)
        if not q["pending"]:
            return Ok(None)
        item = q["pending"].pop(0)
        item.state = "in_flight"
        q["in_flight"].append(item)
        store.audit("dequeue", device_id=device_id, item_id=item.id, caller=caller)
        return Ok(item)


def queue_state(caller: str, device_id: str) -> Result[QueueState]:
    with store.lock():
        q = store.queue_of(device_id)
        samples = list(q["throughputs"]) or [0.0]
        mean = sum(samples) / len(samples)
        return Ok(
            QueueState(
                queue_id=f"q_{device_id}",
                device_id=device_id,
                pending=len(q["pending"]),
                in_flight=len(q["in_flight"]),
                completed=int(q["completed"]),
                failed=int(q["failed"]),
                backpressure=len(q["in_flight"]) >= int(q["threshold"]),
                threshold=int(q["threshold"]),
                throughput=Distribution(mean, 0.0, len(samples)),
            )
        )
