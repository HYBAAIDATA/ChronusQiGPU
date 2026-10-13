#!/usr/bin/env python3
"""Exact Kernel MCP server aligned with the standard MCP initialize handshake.

The server keeps backward-compatible support for stateless metadata-driven
requests but implements the real initialize handshake used by MCP clients.
"""

from __future__ import annotations

import json
import sys
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "exact-kernel", "version": "0.2.1"}
STANDARD_PROTOCOL_VERSIONS = {PROTOCOL_VERSION}

try:
    from chronus.lucas.core import lucas, fibonacci
    from chronus.lucas.ladder import verify_ladder, ladder_capacity
except ImportError as e:
    print(json.dumps({"error": f"Import failed: {e}. Set PYTHONPATH to repo root."}), file=sys.stderr)
    sys.exit(1)


def _supports_protocol(version: Any) -> bool:
    return str(version) in STANDARD_PROTOCOL_VERSIONS if version is not None else True


def initialize_response(request_id: Any) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False},
                "prompts": {},
            },
            "serverInfo": SERVER_INFO,
        },
        "_meta": {"io.modelcontextprotocol/serverInfo": SERVER_INFO},
    }


def cassini_witness(n: int) -> dict[str, Any]:
    f = fibonacci(n)
    l = lucas(n)
    left = l * l - 5 * f * f
    right = 4 * (1 if n % 2 == 0 else -1)
    return {
        "n": n,
        "F_n": f,
        "L_n": l,
        "cassini_holds": left == right,
        "left": left,
        "right": right,
        "theorem_proven": False,
    }


def zeckendorf(n: int) -> dict[str, Any]:
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return {"n": 0, "indices": [], "non_adjacency": True, "valid": True, "theorem_proven": False}
    fibs = [1, 2]
    while fibs[-1] <= n:
        fibs.append(fibs[-1] + fibs[-2])
    indices: list[int] = []
    remaining = n
    for i in range(len(fibs) - 1, -1, -1):
        if fibs[i] <= remaining:
            indices.append(i + 2)
            remaining -= fibs[i]
            if remaining == 0:
                break
    indices = sorted(indices)
    non_adj = all(indices[i + 1] - indices[i] >= 2 for i in range(len(indices) - 1))
    if not non_adj:
        raise ValueError(
            f"Zeckendorf certificate failed for n={n}: adjacent indices observed in representation {indices}"
        )
    return {"n": n, "indices": indices, "non_adjacency": True, "valid": True, "theorem_proven": False}


def largest_feasible_tile(max_size: int, alignment: int = 16) -> dict[str, Any]:
    if max_size < alignment:
        return {
            "tile": None,
            "feasible": False,
            "max_size": max_size,
            "alignment": alignment,
            "reason": "max_size is smaller than the required alignment",
            "theorem_proven": False,
        }
    candidate = 1 << (max_size.bit_length() - 1)
    while candidate > 0:
        if candidate % alignment == 0:
            return {
                "tile": candidate,
                "feasible": True,
                "max_size": max_size,
                "alignment": alignment,
                "theorem_proven": False,
            }
        candidate >>= 1
    return {
        "tile": None,
        "feasible": False,
        "max_size": max_size,
        "alignment": alignment,
        "reason": "no power-of-two tile is compatible with the alignment",
        "theorem_proven": False,
    }


def _tool_result(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "lucas":
        n = int(arguments["n"])
        return {"L_n": lucas(n), **cassini_witness(n)}
    if name == "fibonacci":
        n = int(arguments["n"])
        return {"F_n": fibonacci(n), "theorem_proven": False}
    if name == "cassini":
        return cassini_witness(int(arguments["n"]))
    if name == "zeckendorf":
        return zeckendorf(int(arguments["n"]))
    if name == "ladder_verify":
        return verify_ladder()
    if name == "ladder_capacity":
        return {"capacity": ladder_capacity(int(arguments["bound"])), "theorem_proven": False}
    if name == "largest_feasible_tile":
        return largest_feasible_tile(
            int(arguments["max_size"]),
            int(arguments.get("alignment", 16)),
        )
    raise ValueError(f"Unknown tool: {name}")


TOOLS = {
    "lucas": {
        "description": "Exact Lucas number L_n via fast doubling. Returns L_n and Cassini witness.",
        "inputSchema": {"type": "object", "properties": {"n": {"type": "integer", "minimum": 0}}, "required": ["n"]},
    },
    "fibonacci": {
        "description": "Exact Fibonacci number F_n.",
        "inputSchema": {"type": "object", "properties": {"n": {"type": "integer", "minimum": 0}}, "required": ["n"]},
    },
    "cassini": {
        "description": "Cassini identity witness for index n. theorem_proven remains False.",
        "inputSchema": {"type": "object", "properties": {"n": {"type": "integer", "minimum": 0}}, "required": ["n"]},
    },
    "zeckendorf": {
        "description": "Zeckendorf representation with non-adjacency certificate.",
        "inputSchema": {"type": "object", "properties": {"n": {"type": "integer", "minimum": 0}}, "required": ["n"]},
    },
    "ladder_verify": {
        "description": "Verify the Lucas scale ladder. theorem_proven remains False.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "ladder_capacity": {
        "description": "Snap a bound to the nearest ladder index (upward bias).",
        "inputSchema": {"type": "object", "properties": {"bound": {"type": "integer", "minimum": 1}}, "required": ["bound"]},
    },
    "largest_feasible_tile": {
        "description": "Largest feasible power-of-two tile under max_size and alignment.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "max_size": {"type": "integer", "minimum": 1},
                "alignment": {"type": "integer", "minimum": 1, "default": 16},
            },
            "required": ["max_size"],
        },
    },
}


def _extract_meta(params: dict[str, Any]) -> dict[str, Any]:
    return params.get("_meta") if isinstance(params, dict) else {}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        rid: Any = None
        try:
            req = json.loads(line)
            method = req.get("method")
            params = req.get("params") or {}
            rid = req.get("id")
            meta = _extract_meta(params)
            version = meta.get("io.modelcontextprotocol/protocolVersion")

            if method == "initialize":
                resp = initialize_response(rid)
                print(json.dumps(resp), flush=True)
                continue

            if version is not None and not _supports_protocol(version):
                print(json.dumps({
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {
                        "code": -32022,
                        "message": "Unsupported protocol version",
                        "data": {"supported": [PROTOCOL_VERSION], "requested": version},
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
                resp = {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": {"tools": [{"name": k, **v} for k, v in TOOLS.items()]},
                    "_meta": {"io.modelcontextprotocol/serverInfo": SERVER_INFO},
                }
            elif method == "tools/call":
                name = params.get("name")
                args = params.get("arguments") or {}
                tool_result = _tool_result(name, args)
                resp = {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": {"content": [{"type": "text", "text": json.dumps(tool_result)}]},
                    "_meta": {"io.modelcontextprotocol/serverInfo": SERVER_INFO},
                }
            elif method == "notifications/initialized":
                resp = {"jsonrpc": "2.0", "method": "notifications/initialized", "id": rid}
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
                "id": rid,
                "error": {"code": -32000, "message": str(exc)},
            }
            print(json.dumps(err), flush=True)


if __name__ == "__main__":
    main()
