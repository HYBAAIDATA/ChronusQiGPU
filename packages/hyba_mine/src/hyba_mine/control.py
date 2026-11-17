# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Operator state: active pool, approval, blocks and live control requests.

* ``state.json`` holds settings (active pool, credential backend, TLS policy,
  route, the set of routes that mine concurrently) and a block marker set when a pool rejects the login, so a restart
  does not retry a rejected login against the pool.
* ``approval.json`` is the operator's explicit approval to mine on this
  machine. It is bound to the host name and user id; without it nothing runs.
* ``control.json`` carries one pending request from the console or CLI (for
  example a pool switch) to the running miner, which applies it and records
  the outcome in the ledger.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
import socket
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

from hyba_mine.paths import Layout, ensure_private_dir, write_private_file
from hyba_mine.portable import exclusive_lock, user_identity
from hyba_mine.pools import TLS_POLICIES, get_pool

#: --backend choices. igpu is the Chronus iGPU (Mode A); metal, opencl and cuda are the host GPU.
BACKENDS = ("auto", "igpu", "metal", "opencl", "cuda", "simd", "reference")
#: --prefer: ours (the Chronus iGPU, the default) or host (the host GPU when it passes its tests).
PREFERENCES = ("ours", "host")
#: Accepted by --route and older state files; mode_a is the Chronus iGPU (igpu).
ROUTES = BACKENDS + ("mode_a",)
#: Local routes that can mine concurrently on disjoint nonce ranges (--routes).
ROUTE_SET_BACKENDS = ("igpu", "metal", "opencl")
ROUTE_SETS_HELP = ("auto (default): every local route that passes its known-answer tests, run concurrently on "
                   "disjoint nonce ranges (macOS: Chronus iGPU Mode A + Metal; elsewhere: Mode A + each eligible "
                   "OpenCL GPU); or a comma list of igpu,metal,opencl (strict: each listed route must pass)")
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


def parse_routes(text: str) -> tuple:
    """``auto`` -> ("auto",); else a de-duplicated tuple of igpu/metal/opencl in the order given (mode_a is igpu)."""
    if not isinstance(text, str):
        raise ValueError("routes must be auto or a comma list of igpu,metal,opencl")
    if text.strip().lower() == "auto":
        return ("auto",)
    routes: list = []
    for item in text.split(","):
        name = item.strip().lower()
        if not name:
            continue
        name = "igpu" if name == "mode_a" else name
        if name not in ROUTE_SET_BACKENDS:
            if name in BACKENDS:
                raise ValueError(f"HYBA Mine has no {name} lane on this machine to mine on concurrently; failing closed")
            raise ValueError(f"unknown route '{name}': use auto or a comma list of {', '.join(ROUTE_SET_BACKENDS)}")
        if name not in routes:
            routes.append(name)
    if not routes:
        raise ValueError("routes must be auto or a comma list of igpu,metal,opencl")
    return tuple(routes)


def load_state(layout: Layout) -> dict:
    state = {"active_pool": None, "credential_store": None, "tls_policy": "prefer", "route": "auto", "prefer": "ours",
             "routes": "auto", "blocked": None}
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
    state["routes"] = ",".join(parse_routes(state.get("routes") or "auto"))
    _write_json(layout.state, state)
    return state


@contextmanager
def _locked(path):
    ensure_private_dir(path.parent)
    with exclusive_lock(path.with_suffix(path.suffix + ".lock")):
        yield


def update_state(layout: Layout, **changes) -> dict:
    with _locked(layout.state):
        state = load_state(layout)
        state.update(changes)
        return save_state(layout, state)


def _blocks(state: dict) -> dict:
    blocked = state.get("blocked") or {}
    # Migrate the previous one-pool representation on the next write.
    return {blocked["pool"]: blocked} if "pool" in blocked else dict(blocked)


def block_pool(layout: Layout, pool_id: str, reason: str) -> dict:
    pool_id = get_pool(pool_id).pool_id
    with _locked(layout.state):
        state = load_state(layout)
        blocks = _blocks(state)
        blocks[pool_id] = {"pool": pool_id, "reason": reason, "at": utc_now()}
        state["blocked"] = blocks
        return save_state(layout, state)


def clear_block(layout: Layout, pool_id: Optional[str] = None) -> dict:
    with _locked(layout.state):
        state = load_state(layout)
        blocks = _blocks(state)
        if pool_id is None:
            blocks.clear()
        else:
            blocks.pop(get_pool(pool_id).pool_id, None)
        state["blocked"] = blocks
        return save_state(layout, state)


def block_for(layout: Layout, pool_id: str) -> Optional[dict]:
    return _blocks(load_state(layout)).get(get_pool(pool_id).pool_id)


def _identity() -> Tuple[str, object]:
    """(host, account). The account is the POSIX uid (unchanged, so existing macOS
    approvals stay valid) or the Windows account SID."""
    return socket.gethostname(), user_identity().value


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
    with _locked(layout.control):
        _write_json(layout.control, request)
    return request


def read_control_request(layout: Layout) -> Optional[dict]:
    request = _read_json(layout.control)
    if not request or request.get("action") != "switch_pool" or not request.get("request_id"):
        return None
    return request


def request_stop(layout: Layout, reason: str = "hyba-mine stop") -> dict:
    """Ask a running miner to stop gracefully. Kept apart from pool switches so neither overwrites the other."""
    request = {"request_id": uuid.uuid4().hex, "action": "stop", "reason": reason, "requested_at": utc_now()}
    with _locked(layout.stop_request):
        _write_json(layout.stop_request, request)
    return request


def read_stop_request(layout: Layout) -> Optional[dict]:
    request = _read_json(layout.stop_request)
    if not request or request.get("action") != "stop" or not request.get("request_id"):
        return None
    return request


def clear_stop_request(layout: Layout) -> None:
    with _locked(layout.stop_request):
        if layout.stop_request.exists():
            layout.stop_request.unlink()


def clear_control_request(layout: Layout, request_id: str) -> None:
    with _locked(layout.control):
        current = _read_json(layout.control)
        if current and current.get("request_id") == request_id:
            layout.control.unlink()
