#!/usr/bin/env python3
"""Cogito MCP server — twelve EUCLID/TOE capabilities.

Aligned with MCP 2026-07-28 (stateless).
Every result carries truth class, digest, and possible REFUSED / ACQUIRE_EVIDENCE.
theorem_proven remains False.

Usage:
  PYTHONPATH=/path/to/repo python -m mcp.cogito.server
"""

from __future__ import annotations

import json
import sys
from typing import Any

PROTOCOL_VERSION = "2026-07-28"
SERVER_INFO = {"name": "cogito", "version": "0.1.0"}

try:
    from euclid.cognition.toe_capabilities import CAPABILITIES, TOECapabilityAdapter
except ImportError as e:
    print(json.dumps({"error": f"Import failed: {e}. Set PYTHONPATH to repo root."}), file=sys.stderr)
    sys.exit(1)


def _envelope(capability: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Preserve truth class. Never flatten to a bare answer."""
    result = raw.get("result", {})
    evidence = raw.get("evidence", {})
    truth_class = "ACT"
    if isinstance(result, dict):
        if "error" in result or result.get("refused"):
            truth_class = "REFUSED"
        elif result.get("acquire_evidence") or result.get("needs_evidence"):
            truth_class = "ACQUIRE_EVIDENCE"
    return {
        "capability": capability,
        "truth_class": truth_class,
        "result": result,
        "evidence": evidence,
        "theorem_proven": False,
    }


def main() -> None:
    adapter = TOECapabilityAdapter()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            method = req.get("method")
            params = req.get("params") or {}
            rid = req.get("id")
            meta = params.get("_meta") or {}

            req_version = meta.get("io.modelcontextprotocol/protocolVersion")
            if req_version and req_version != PROTOCOL_VERSION:
                print(json.dumps({
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {
                        "code": -32022,
                        "message": "Unsupported protocol version",
                        "data": {"supported": [PROTOCOL_VERSION], "requested": req_version},
                    },
                }), flush=True)
                continue

            if method == "server/discover":
                result = {
                    "protocolVersions": [PROTOCOL_VERSION],
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": SERVER_INFO,
                }
                resp = {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": result,
                    "_meta": {"io.modelcontextprotocol/serverInfo": SERVER_INFO},
                }
            elif method == "tools/list":
                tools = [
                    {
                        "name": cap,
                        "description": f"EUCLID/TOE capability: {cap}. Returns truth_class + evidence. theorem_proven=False.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "problem": {"type": "object"},
                                "args": {"type": "object"},
                            },
                        },
                    }
                    for cap in CAPABILITIES
                ]
                resp = {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": {"tools": tools},
                    "_meta": {"io.modelcontextprotocol/serverInfo": SERVER_INFO},
                }
            elif method == "tools/call":
                name = params.get("name")
                args = params.get("arguments") or {}
                if name not in CAPABILITIES:
                    raise ValueError(f"unknown capability {name}")
                problem = args.get("problem", {})
                extra = args.get("args", {})
                raw = adapter.invoke(name, problem, **extra)
                enveloped = _envelope(name, raw)
                resp = {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": {"content": [{"type": "text", "text": json.dumps(enveloped)}]},
                    "_meta": {"io.modelcontextprotocol/serverInfo": SERVER_INFO},
                }
            else:
                resp = {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
            print(json.dumps(resp), flush=True)
        except Exception as exc:
            err = {
                "jsonrpc": "2.0",
                "id": rid if "rid" in locals() else None,
                "error": {"code": -32000, "message": str(exc)},
            }
            print(json.dumps(err), flush=True)


if __name__ == "__main__":
    main()
