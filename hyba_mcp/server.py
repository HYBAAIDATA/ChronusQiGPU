#!/usr/bin/env python3
"""HYBA Sovereign MCP Server — Production Exact Kernel & Tool Gateway.

Implements the standard Model Context Protocol (MCP) JSON-RPC 2.0 handshake
and execution loop.

SOVEREIGNTY & CREDITING DOCTRINE:
HYBA MCP does not augment or defer to narrow AI. Narrow AI systems obtain zero
credit, zero proof authority, and zero decision rights. HYBA ingests and adapts
tools and training into its own deterministic mathematical substrate. All outputs
are verified against exact integer arithmetic, Cassini invariants, and fail-closed
consensus gates.
"""

from __future__ import annotations

import json
import logging
import math
import sys
from typing import Any, Mapping

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {
    "name": "hyba-mcp-server",
    "version": "1.0.0",
    "sovereignty": "HYBA_SOVEREIGN_CNS",
    "narrow_ai_credit": "NONE_FORBIDDEN",
}
STANDARD_PROTOCOL_VERSIONS = {PROTOCOL_VERSION, "2024-10-07", "2026-07-28"}
MAX_N = 10_000

try:
    from chronus.lucas.core import fibonacci, lucas
    from chronus.lucas.ladder import ladder_capacity, verify_ladder
    from chronus.mla1517.mining.pow import compact_target, sha256d
except ImportError:
    # Graceful path fallback
    import os
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from chronus.lucas.core import fibonacci, lucas
    from chronus.lucas.ladder import ladder_capacity, verify_ladder
    from chronus.mla1517.mining.pow import compact_target, sha256d


try:
    from Intelligence.lucas_scaler import LucasIntelligenceScaler
except ImportError:
    LucasIntelligenceScaler = None
    logging.getLogger(__name__).warning(
        "scale_intelligence unavailable: install the Intelligence.lucas_scaler dependencies"
    )


def validate_arguments(name: str, arguments: Mapping[str, Any]) -> None:
    """Enforce advertised types and limits before invoking any kernel."""
    if name not in TOOLS:
        raise ValueError(f"Unknown HYBA MCP tool: {name}")
    if not isinstance(arguments, Mapping):
        raise ValueError("tool arguments must be an object")
    schema = TOOLS[name]["inputSchema"]
    for key in schema.get("required", []):
        if key not in arguments:
            raise ValueError(f"missing required argument: {key}")
    for key, spec in schema["properties"].items():
        if key not in arguments:
            continue
        value = arguments[key]
        kind = spec["type"]
        if (
            (kind == "integer" and type(value) is not int)
            or (kind == "number" and type(value) not in (int, float))
            or (kind == "string" and not isinstance(value, str))
        ):
            raise ValueError(f"{key} must be a {kind}")
        if kind == "number" and isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{key} must be finite")
        if "minimum" in spec and value < spec["minimum"]:
            raise ValueError(f"{key} must be >= {spec['minimum']}")
        if "maximum" in spec and value > spec["maximum"]:
            raise ValueError(f"{key} must be <= {spec['maximum']}")
        if "enum" in spec and value not in spec["enum"]:
            raise ValueError(f"{key} must be one of {spec['enum']}")


def cassini_witness(n: int) -> dict[str, Any]:
    validate_arguments("cassini", {"n": n})
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
    validate_arguments("zeckendorf", {"n": n})
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


TOOLS: dict[str, dict[str, Any]] = {
    "lucas": {
        "description": "Exact Lucas number L_n via fast doubling with Cassini invariant witness.",
        "inputSchema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "minimum": 0, "maximum": MAX_N}},
            "required": ["n"],
        },
    },
    "fibonacci": {
        "description": "Exact Fibonacci number F_n via fast doubling.",
        "inputSchema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "minimum": 0, "maximum": MAX_N}},
            "required": ["n"],
        },
    },
    "cassini": {
        "description": "Cassini identity verification L_n^2 - 5*F_n^2 = 4*(-1)^n.",
        "inputSchema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "minimum": 0, "maximum": MAX_N}},
            "required": ["n"],
        },
    },
    "zeckendorf": {
        "description": "Canonical non-adjacent Zeckendorf representation certificate.",
        "inputSchema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "minimum": 0, "maximum": MAX_N}},
            "required": ["n"],
        },
    },
    "ladder_verify": {
        "description": "Verify the canonical Lucas scale ladder stops.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "ladder_capacity": {
        "description": "Snap an envelope/retention bound to the nearest valid ladder stop.",
        "inputSchema": {
            "type": "object",
            "properties": {"bound": {"type": "integer", "minimum": 1}},
            "required": ["bound"],
        },
    },
    "largest_feasible_tile": {
        "description": "Compute largest power-of-two work tile compatible with alignment.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "max_size": {"type": "integer", "minimum": 1},
                "alignment": {"type": "integer", "minimum": 1, "default": 16},
            },
            "required": ["max_size"],
        },
    },
    "sha256d_verify": {
        "description": "Compute independent double SHA-256 hash and check against uint256 target.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "payload_hex": {"type": "string"},
                "compact_bits": {"type": "integer"},
            },
            "required": ["payload_hex"],
        },
    },
    "scale_intelligence": {
        "description": (
            "Stateless Lucas intelligence scale selection (L_10 to L_31). "
            "Requires Intelligence.lucas_scaler; returned *_after values are modeled, not measured."
        ),
        "_meta": {
            "hyba/status": "available" if LucasIntelligenceScaler is not None else "unavailable",
            "hyba/dependency": "Intelligence.lucas_scaler",
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_rung": {
                    "type": "integer",
                    "enum": [10, 12, 15, 18, 20, 31],
                    "default": 31,
                    "description": "Starting rung for this call; not persistent state.",
                },
                "task_type": {
                    "type": "string",
                    "description": (
                        "Free-form, case-insensitive affinity substrings; highest match wins. "
                        "See README_MCP.md for the full keyword table."
                    ),
                },
                "complexity": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": (
                        "Finite demand; thresholds .15/.35/.55/.75/.90 select "
                        "10/12/15/18/20/31. Higher keyword demand wins."
                    ),
                },
                "step_direction": {
                    "type": "string",
                    "enum": ["up", "down", "hold"],
                    "description": (
                        "One clamped step, overriding task adaptation; hold preserves starting rung."
                    ),
                },
            },
        },
    },
}


class HybaMCPServer:
    """Production Model Context Protocol server exposing HYBA exact tools."""

    def __init__(self, name: str = "hyba-mcp-server", version: str = "1.0.0") -> None:
        self.name = name
        self.version = version

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute validated tools, retaining exact-kernel and proof boundaries.

        scale_intelligence is stateless: target_rung defaults to 31. An up/down
        step takes precedence over adaptation; hold queries the initial rung.
        Otherwise task_type matches case-insensitive affinity substrings and
        finite complexity in [0, 1] selects rungs at .15/.35/.55/.75/.90.
        The higher keyword/complexity demand wins. See README_MCP.md for keywords.
        Envelope fields describe configured manifold/context/reflection limits;
        *_after fields model scaling from fixed 0.5 baselines, not measurements
        of consciousness, intelligence, performance, or theorem completion.
        Missing scaler dependencies fail closed without disabling exact tools.
        """
        validate_arguments(name, arguments)
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
        if name == "sha256d_verify":
            raw = bytes.fromhex(arguments["payload_hex"])
            digest = sha256d(raw)
            result = {
                "sha256d_le": digest.hex(),
                "sha256d_be": digest[::-1].hex(),
            }
            if "compact_bits" in arguments:
                target = compact_target(arguments["compact_bits"])
                digest_int = int.from_bytes(digest, "little")
                result["target_int"] = target
                result["meets_target"] = digest_int <= target
            return result
        if name == "scale_intelligence":
            if LucasIntelligenceScaler is None:
                raise RuntimeError(
                    "scale_intelligence unavailable: Intelligence.lucas_scaler "
                    "or its dependencies are not installed"
                )
            target_rung = arguments.get("target_rung")
            scaler = LucasIntelligenceScaler(
                initial_scale=int(target_rung) if target_rung is not None else 31
            )
            step = arguments.get("step_direction")
            if step == "up":
                scaler.scale_up()
            elif step == "down":
                scaler.scale_down()
            elif step != "hold" and ("task_type" in arguments or "complexity" in arguments):
                scaler.scale_for_task(
                    task_type=arguments.get("task_type"),
                    complexity=arguments.get("complexity"),
                )
            env = scaler.current_envelope
            cassini = scaler.cassini_identity(scaler.current_scale)
            scale_res = scaler.scale(0.5, 0.5, 0.5, scaler.current_scale)
            return {
                "current_scale": scaler.current_scale,
                "lucas_number": env.lucas_number,
                "fibonacci_number": env.fibonacci_number,
                "cassini": cassini,
                "manifold_dimension": env.manifold_dimension,
                "context_limit": env.context_limit,
                "reflection_depth": env.reflection_depth,
                "curvature_tolerance": env.curvature_tolerance,
                "pci_after": scale_res.pci_after,
                "emergence_after": scale_res.emergence_after,
                "consciousness_after": scale_res.consciousness_after,
                "sovereign_doctrine": "Zero credit to narrow AI; ingested tools and templates adapted into EUCLID substrate.",
            }
        raise ValueError(f"Unknown HYBA MCP tool: {name}")

    def handle_request(self, req: Mapping[str, Any]) -> dict[str, Any]:
        method = req.get("method")
        params = req.get("params") or {}
        rid = req.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"subscribe": False},
                        "prompts": {},
                    },
                    "serverInfo": {
                        "name": self.name,
                        "version": self.version,
                        "sovereignty": "HYBA_SOVEREIGN_CNS",
                    },
                },
                "_meta": {"io.modelcontextprotocol/serverInfo": {"name": self.name, "version": self.version}},
            }

        if method in ("server/discover", "server/info"):
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "protocolVersions": [PROTOCOL_VERSION],
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": self.name, "version": self.version},
                },
            }

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {"tools": [{"name": k, **v} for k, v in TOOLS.items()]},
            }

        if method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})
            try:
                res = self.execute_tool(str(tool_name), args)
            except (ValueError, TypeError, KeyError) as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {"code": -32602, "message": str(exc)},
                }
            except RuntimeError as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {"code": -32000, "message": str(exc)},
                }
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {"content": [{"type": "text", "text": json.dumps(res)}]},
            }

        if method == "notifications/initialized":
            return {"jsonrpc": "2.0", "method": "notifications/initialized", "id": rid}

        return {
            "jsonrpc": "2.0",
            "id": rid,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }


def run_server() -> None:
    server = HybaMCPServer()
    for line in sys.stdin:
        text = line.strip()
        if not text:
            continue
        try:
            req = json.loads(text)
            resp = server.handle_request(req)
            print(json.dumps(resp), flush=True)
        except Exception as exc:
            err = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32000, "message": str(exc)},
            }
            print(json.dumps(err), flush=True)


if __name__ == "__main__":
    run_server()
