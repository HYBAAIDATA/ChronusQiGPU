"""Process-local seam store. Silicon handles stay below the seam."""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from .scale import snap_work_items

_lock = threading.RLock()
_capabilities: Dict[str, Any] = {}
_buffers: Dict[str, Any] = {}
_handles: Dict[str, Any] = {}
_queues: Dict[str, Any] = {}
_idempotent: Dict[str, str] = {}
_quarantined: Dict[str, str] = {}
_audit: List[Dict[str, Any]] = []


def reset() -> None:
    with _lock:
        _capabilities.clear()
        _buffers.clear()
        _handles.clear()
        _queues.clear()
        _idempotent.clear()
        _quarantined.clear()
        _audit.clear()


def put_cap(cap: Any) -> None:
    with _lock:
        _capabilities[cap.device_id] = cap


def get_cap(device_id: str) -> Optional[Any]:
    with _lock:
        return _capabilities.get(device_id)


def all_caps() -> List[Any]:
    with _lock:
        return list(_capabilities.values())


def quarantine(device_id: str, reason: str) -> None:
    with _lock:
        _quarantined[device_id] = reason
        cap = _capabilities.get(device_id)
        if cap is not None:
            cap.state = type(cap.state)("quarantined")


def is_quarantined(device_id: str) -> bool:
    with _lock:
        return device_id in _quarantined


def put_buffer(buf: Any) -> None:
    with _lock:
        _buffers[buf.id] = buf


def get_buffer(buffer_id: str) -> Optional[Any]:
    with _lock:
        return _buffers.get(buffer_id)


def drop_buffer(buffer_id: str) -> None:
    with _lock:
        _buffers.pop(buffer_id, None)


def put_handle(handle: Any) -> None:
    with _lock:
        _handles[handle.id] = handle


def get_handle(handle_id: str) -> Optional[Any]:
    with _lock:
        return _handles.get(handle_id)


def lookup_idempotent(key: str) -> Optional[str]:
    with _lock:
        return _idempotent.get(key)


def remember_idempotent(key: str, handle_id: str) -> None:
    with _lock:
        _idempotent[key] = handle_id


def queue_of(device_id: str) -> Dict[str, Any]:
    with _lock:
        q = _queues.get(device_id)
        if q is None:
            q = {
                "pending": [],
                "in_flight": [],
                "completed": 0,
                "failed": 0,
                # LUCAS_SCALED (lemma_lucas_universal): queue backpressure
                # depth is a Chronus-owned capacity envelope — a ladder stop.
                "threshold": snap_work_items(64),
                "throughputs": [],
            }
            _queues[device_id] = q
        return q


def lock() -> threading.RLock:
    """Queue mutations span several reads/writes — hold this across them."""
    return _lock


def audit(kind: str, **fields: Any) -> None:
    with _lock:
        rec = {"kind": kind, **fields}
        _audit.append(rec)


def audit_snapshot() -> List[Dict[str, Any]]:
    with _lock:
        return list(_audit)
