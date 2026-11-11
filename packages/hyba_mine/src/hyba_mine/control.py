# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Operator state: active pool, approval, blocks and live control requests.

* ``state.json`` holds settings (active pool, credential backend, TLS policy,
  route) and a block marker set when a pool rejects the login, so a restart
  does not retry a rejected login against the pool.
* ``approval.json`` is the operator's explicit approval to mine on this
  machine. It is bound to the host name and user id; without it nothing runs.
* ``control.json`` carries one pending request from the console or CLI (for
  example a pool switch) to the running miner, which applies it and records
  the outcome in the ledger.
"""

from __future__ import annotations

import json
import os
import socket
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

from hyba_mine.paths import Layout, write_private_file
from hyba_mine.pools import TLS_POLICIES, get_pool

#: --backend choices. igpu is the Chronus iGPU (Mode A); metal, opencl and cuda are the host GPU.
BACKENDS = ("auto", "igpu", "metal", "opencl", "cuda", "simd", "reference")
#: --prefer: ours (the Chronus iGPU, the default) or host (the host GPU when it passes its tests).
PREFERENCES = ("ours", "host")
#: Accepted by --route and older state files; mode_a is the Chronus iGPU (igpu).
ROUTES = BACKENDS + ("mode_a",)
APPROVAL_STATEMENT = (
    "The operator approves HYBA Mine, HYBA's internal treasury mining runtime, "
    "to mine on this machine with the pool logins stored on this machine."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _read_json(path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path, data: dict) -> None:
    write_private_file(path, (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def load_state(layout: Layout) -> dict:
    state = {"active_pool": None, "credential_store": None, "tls_policy": "prefer", "route": "auto", "prefer": "ours",
             "blocked": None}
    stored = _read_json(layout.state)
    if stored:
        state.update({key: stored[key] for key in state if key in stored})
    return state


def save_state(layout: Layout, state: dict) -> dict:
    if state.get("active_pool") is not None:
        state["active_pool"] = get_pool(state["active_pool"]).pool_id
    if state.get("tls_policy") not in TLS_POLICIES:
        raise ValueError(f"tls policy must be one of {', '.join(TLS_POLICIES)}")
    if state.get("route") not in ROUTES:
        raise ValueError(f"route must be one of {', '.join(ROUTES)}")
    if state.get("prefer", "ours") not in PREFERENCES:
        raise ValueError("prefer must be ours or host")
    _write_json(layout.state, state)
    return state


def update_state(layout: Layout, **changes) -> dict:
    state = load_state(layout)
    state.update(changes)
    return save_state(layout, state)


def block_pool(layout: Layout, pool_id: str, reason: str) -> dict:
    return update_state(layout, blocked={"pool": get_pool(pool_id).pool_id, "reason": reason, "at": utc_now()})


def clear_block(layout: Layout, pool_id: Optional[str] = None) -> dict:
    state = load_state(layout)
    blocked = state.get("blocked")
    if blocked and (pool_id is None or blocked.get("pool") == get_pool(pool_id).pool_id):
        state["blocked"] = None
        save_state(layout, state)
    return state


def block_for(layout: Layout, pool_id: str) -> Optional[dict]:
    blocked = load_state(layout).get("blocked")
    if blocked and blocked.get("pool") == get_pool(pool_id).pool_id:
        return blocked
    return None


def _identity() -> Tuple[str, int]:
    return socket.gethostname(), os.getuid()


def grant_approval(layout: Layout) -> dict:
    host, uid = _identity()
    record = {"approved_at": utc_now(), "host": host, "uid": uid, "statement": APPROVAL_STATEMENT}
    _write_json(layout.approval, record)
    return record


def revoke_approval(layout: Layout) -> bool:
    if layout.approval.exists():
        layout.approval.unlink()
        return True
    return False


def approval_status(layout: Layout) -> Tuple[bool, str]:
    record = _read_json(layout.approval)
    if record is None:
        return False, "no operator approval on this machine; run: hyba-mine approve"
    host, uid = _identity()
    if record.get("host") != host or record.get("uid") != uid:
        return False, "the approval was given on another machine or account; run: hyba-mine approve"
    if record.get("statement") != APPROVAL_STATEMENT:
        return False, "the approval record is not the current statement; run: hyba-mine approve"
    return True, f"approved at {record.get('approved_at')}"


def request_pool_switch(layout: Layout, pool_id: str) -> dict:
    request = {
        "request_id": uuid.uuid4().hex,
        "action": "switch_pool",
        "pool_id": get_pool(pool_id).pool_id,
        "requested_at": utc_now(),
    }
    _write_json(layout.control, request)
    return request


def read_control_request(layout: Layout) -> Optional[dict]:
    request = _read_json(layout.control)
    if not request or request.get("action") != "switch_pool" or not request.get("request_id"):
        return None
    return request


def clear_control_request(layout: Layout, request_id: str) -> None:
    current = _read_json(layout.control)
    if current and current.get("request_id") == request_id:
        layout.control.unlink()
