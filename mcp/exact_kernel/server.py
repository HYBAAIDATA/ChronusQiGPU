#!/usr/bin/env python3
"""Production-ready MCP server exposing the exact Lucas/Cassini/Zeckendorf kernel.

Usage (stdio):
  python -m mcp.exact_kernel.server

Or register in Claude Desktop / Notion agent MCP config:
{
  "mcpServers": {
    "exact-kernel": {
      "command": "python",
      "args": ["-m", "mcp.exact_kernel.server"],
      "env": {"PYTHONPATH": "/path/to/EuclidPhiEnterprise"}
    }
  }
}

All tools return exact integer results plus witnesses. theorem_proven is always False.
"""

from __future__ import annotations

import json
import sys
from typing import Any

# Import from the repository substrate (PYTHONPATH must include repo root)
try:
    from chronus.lucas.core import lucas, fibonacci
    from chronus.lucas.ladder import (
        FULL_LADDER,
        LUCAS_SCALE_LADDER,
        verify_ladder,
        ladder_capacity,
        is_ladder_index,
    )
except ImportError as e:
    print(json.dumps({"error": f"Import failed: {e}. Set PYTHONPATH to repo root."}), file=sys.stderr)
    sys.exit(1)


def cassini_witness(n: int) -> dict[str, Any]:
    """Exact Cassini check: L_n^2 - 5*F_n^2 == 4*(-1)^n."""
    f = fibonacci(n)
    l = lucas(n)
    left = l * l - 5 * f * f
    right = 4 * (1 if n % 2 == 0 else -1)
    holds = left == right
    return {
        "n": n,
        "F_n": f,
        "L_n": l,
        "cassini_holds": holds,
        "left": left,
        "right": right,
        "theorem_proven": False,
    }


def zeckendorf(n: int) -> dict[str, Any]:
    """Greedy Zeckendorf representation (non-adjacent Fibonacci)."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return {"n": 0, "indices": [], "non_adjacency": True, "theorem_proven": False}
    # Build Fibonacci up to n
    fibs = [1, 2]
    while fibs[-1] <= n:
        fibs.append(fibs[-1] + fibs[-2])
    indices = []
    remaining = n
    for i in range(len(fibs) - 1, -1, -1):
        if fibs[i] <= remaining:
            indices.append(i + 2)  # F_2=1, F_3=2, ...
            remaining -= fibs[i]
            if remaining == 0:
                break
    indices = sorted(indices)
    non_adj = all(indices[i+1] - indices[i] >= 2 for i in range(len(indices)-1))
    return {
        "n": n,
        "indices": indices,
        "non_adjacency": non_adj,
        "theorem_proven": False,
    }


def largest_feasible_tile(max_size: int, alignment: int = 16) -> dict[str, Any]:
    """Largest power-of-two tile <= max_size that is aligned."""
    if max_size < alignment:
        return {"tile": 0, "feasible": False, "theorem_proven": False}
    tile = 1
    while (tile << 1) <= max_size and (tile << 1) % alignment == 0:
        tile <<= 1
    return {
        "tile": tile,
        "feasible": True,
        "max_size": max_size,
        "alignment": alignment,
        "theorem_proven": False,
    }


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


def handle_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
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


def main() -> None:
    """Minimal JSON-RPC stdio MCP loop."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            method = req.get("method")
            params = req.get("params", {})
            rid = req.get("id")

            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "exact-kernel", "version": "0.1.0"},
                    },
                }
            elif method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": {"tools": [{"name": k, **v} for k, v in TOOLS.items()]},
                }
            elif method == "tools/call":
                name = params.get("name")
                args = params.get("arguments", {})
                result = handle_tool(name, args)
                resp = {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": {"content": [{"type": "text", "text": json.dumps(result)}]},
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
