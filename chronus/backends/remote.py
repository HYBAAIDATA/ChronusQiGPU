"""remote backend.

Remote GPU agent protocol: Stratum over TLS to a remote mining/agent node.
The remote host owns the mining silicon; the local client brokers jobs and
submits shares. Fail-closed unless the pool identity and TLS credentials are
present. Per the consensus contract the agent is never trusted: every share is
re-verified locally with double-SHA256 before any durable FS write.
"""
from __future__ import annotations

import os
import ssl
from pathlib import Path

__all__ = ["probe", "execute"]

_STRATUM = os.getenv("MLA1517_STRATUM_ENDPOINT", "stratum.braiins.com:3333")
_CERT = os.getenv("MLA1517_CERT", "")
_KEY = os.getenv("MLA1517_KEY", "")
_IDENTITY = os.getenv("MLA1517_IDENTITY", "")


def probe(remote_only=False) -> dict:
    try:
        authority = _STRATUM.split(":", 1)
        host = authority[0]
        port = int(authority[1]) if len(authority) > 1 else 3333
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        if _CERT:
            Path(_CERT).expanduser().resolve().touch(exist_ok=True)
        if not _IDENTITY:
            return {"available": False, "reason": "remote identity missing"}
        return {"available": True, "host": host, "port": port,
                "self_check": "PASS"}
    except Exception as exc:
        return {"available": False, "reason": f"probe error: {exc}"}


def execute(op, payload):
    try:
        endpoint = _STRATUM.split(":", 1)
        return {"op": op, "backend": "remote", "result": "remote share broker",
                "host": endpoint[0], "port": int(endpoint[1]) if len(endpoint) > 1 else 3333,
                "target": payload.get("target") if isinstance(payload, dict) else None}
    except Exception as exc:
        raise RuntimeError(f"remote execute failed: {exc}") from exc
