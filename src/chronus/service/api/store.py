"""API persistence. SQLite is shared by default; memory is explicit for tests."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Iterable
from datetime import datetime, timezone

from chronus.service.api import state
from chronus.service.api.errors import ApiError
from chronus.service.api.schemas import (
    CapacitySlot,
    Node,
    Receipt,
    Workload,
    WorkloadCreate,
    WorkloadState,
)

_TERMINAL = {
    WorkloadState.succeeded,
    WorkloadState.failed,
    WorkloadState.cancelled,
}


def _encode(record: dict) -> dict:
    encoded = dict(record)
    for field in ("created_at", "updated_at", "last_heartbeat"):
        value = encoded.get(field)
        if isinstance(value, datetime):
            encoded[field] = value.isoformat()
    value = encoded.get("state")
    if isinstance(value, WorkloadState):
        encoded["state"] = value.value
    return encoded


def _decode(record: dict, model):
    decoded = dict(record)
    for field in ("created_at", "updated_at", "last_heartbeat"):
        value = decoded.get(field)
        if isinstance(value, str):
            decoded[field] = datetime.fromisoformat(value)
    if model is Workload and isinstance(decoded.get("state"), str):
        decoded["state"] = WorkloadState(decoded["state"])
    return model(**decoded)


def _get(table: str, record_id: str, model, conn=None):
    record = state.read_record(table, record_id, conn)
    return _decode(record, model) if record is not None else None


def _all(table: str, model) -> list:
    return [_decode(record, model) for record in state.all_records(table)]


def reset() -> None:
    for table in ("workloads", "nodes", "receipts"):
        state.clear_records(table)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def seed_nodes(specs: Iterable[dict]) -> None:
    for spec in specs:
        record = {**spec, "last_heartbeat": _now()}
        state.write_record("nodes", _encode(record))


def _new_workload(tenant_id: str, payload: WorkloadCreate) -> Workload:
    now = _now()
    return Workload(
        id=f"wl_{secrets.token_hex(8)}",
        tenant_id=tenant_id,
        **payload.model_dump(),
        state=WorkloadState.queued,
        created_at=now,
        updated_at=now,
        receipt_id=None,
    )


def create_workload(tenant_id: str, payload: WorkloadCreate, conn=None) -> Workload:
    workload = _new_workload(tenant_id, payload)
    state.write_record("workloads", _encode(workload.model_dump()), conn)
    return workload


def get_workload(tenant_id: str, workload_id: str) -> Workload:
    workload = _get("workloads", workload_id, Workload)
    if workload is None or workload.tenant_id != tenant_id:
        raise ApiError(
            404,
            "workload_not_found",
            "Workload not found",
            f"No workload {workload_id!r} for this tenant.",
        )
    return workload


def list_workloads(
    tenant_id: str,
    limit: int,
    cursor: dict | None,
    state_filter: str | None,
) -> tuple[list[Workload], dict | None]:
    rows = [w for w in _all("workloads", Workload) if w.tenant_id == tenant_id]
    if state_filter:
        rows = [w for w in rows if w.state.value == state_filter]
    rows.sort(key=lambda w: (w.created_at, w.id), reverse=True)

    if cursor:
        try:
            after = (datetime.fromisoformat(cursor["t"]), cursor["i"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ApiError(
                400,
                "invalid_cursor",
                "Invalid cursor",
                "Cursor is malformed.",
            ) from exc
        rows = [w for w in rows if (w.created_at, w.id) < after]

    window = rows[:limit]
    next_cursor = None
    if len(rows) > limit and window:
        last = window[-1]
        next_cursor = {"t": last.created_at.isoformat(), "i": last.id}
    return window, next_cursor


def _change_state(
    tenant_id: str,
    workload_id: str,
    new_state: WorkloadState,
    *,
    require_active: bool = False,
) -> Workload:
    with state.atomic() as conn:
        workload = _get("workloads", workload_id, Workload, conn)
        if workload is None or workload.tenant_id != tenant_id:
            raise ApiError(
                404,
                "workload_not_found",
                "Workload not found",
                f"No workload {workload_id!r} for this tenant.",
            )
        if workload.state in _TERMINAL:
            if workload.state is new_state and not require_active:
                return workload
            raise ApiError(
                409,
                "workload_terminal",
                "Workload already finished",
                f"State is {workload.state.value}; it cannot become {new_state.value}.",
            )
        if require_active and new_state is not WorkloadState.cancelled:
            raise ValueError("require_active is reserved for cancellation")

        workload.state = new_state
        workload.updated_at = _now()
        if new_state is WorkloadState.succeeded and workload.receipt_id is None:
            receipt_id = f"rc_{secrets.token_hex(8)}"
            digest_source = f"{workload_id}:{workload.updated_at.isoformat()}"
            receipt = Receipt(
                id=receipt_id,
                workload_id=workload_id,
                tenant_id=tenant_id,
                digest=hashlib.sha256(digest_source.encode("utf-8")).hexdigest(),
                created_at=_now(),
            )
            state.write_record("receipts", _encode(receipt.model_dump()), conn)
            workload.receipt_id = receipt_id
        state.write_record("workloads", _encode(workload.model_dump()), conn)
        return workload


def cancel_workload(tenant_id: str, workload_id: str) -> Workload:
    return _change_state(
        tenant_id,
        workload_id,
        WorkloadState.cancelled,
        require_active=True,
    )


def transition(
    tenant_id: str,
    workload_id: str,
    new_state: WorkloadState,
) -> Workload:
    """Test seam for a real executor; success mints exactly one receipt."""
    return _change_state(tenant_id, workload_id, new_state)


def get_receipt_for_workload(tenant_id: str, workload_id: str) -> Receipt:
    workload = get_workload(tenant_id, workload_id)
    if workload.receipt_id is None:
        raise ApiError(
            404,
            "receipt_not_ready",
            "Receipt not ready",
            "The workload has not produced a receipt yet.",
        )
    receipt = _get("receipts", workload.receipt_id, Receipt)
    if receipt is None:
        raise ApiError(
            500,
            "receipt_missing",
            "Receipt missing",
            "The workload references a receipt that does not exist.",
        )
    return receipt


def get_receipt(tenant_id: str, receipt_id: str) -> Receipt:
    receipt = _get("receipts", receipt_id, Receipt)
    if receipt is None or receipt.tenant_id != tenant_id:
        raise ApiError(
            404,
            "receipt_not_found",
            "Receipt not found",
            "No such receipt.",
        )
    return receipt


def list_nodes(
    limit: int,
    cursor: dict | None,
    region: str | None,
) -> tuple[list[Node], dict | None]:
    rows = _all("nodes", Node)
    if region:
        rows = [node for node in rows if node.region == region]
    rows.sort(key=lambda node: node.id)
    if cursor:
        rows = [node for node in rows if node.id > cursor.get("i", "")]
    window = rows[:limit]
    next_cursor = {"i": window[-1].id} if len(rows) > limit and window else None
    return window, next_cursor


def get_node(node_id: str) -> Node:
    node = _get("nodes", node_id, Node)
    if node is None:
        raise ApiError(
            404,
            "node_not_found",
            "Node not found",
            f"No node {node_id!r}.",
        )
    return node


def capacity() -> list[CapacitySlot]:
    counts: dict[tuple[str, str], int] = {}
    for node in _all("nodes", Node):
        if node.state != "ready":
            continue
        slot = (node.region, node.tier)
        counts[slot] = counts.get(slot, 0) + node.gpu_count
    return [
        CapacitySlot(region=region, tier=tier, free_slots=count)
        for (region, tier), count in sorted(counts.items())
    ]
