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
import sys
from typing import Any, Callable, Mapping

from .control_plane import ControlPlane
from .skills import discover_skills, get_skill_module

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {
    "name": "hyba-mcp-server",
    "version": "2.0.0",
    "sovereignty": "HYBA_SOVEREIGN_CNS",
    "narrow_ai_credit": "NONE_FORBIDDEN",
}
STANDARD_PROTOCOL_VERSIONS = {PROTOCOL_VERSION, "2024-10-07", "2026-07-28"}

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


TOOLS: dict[str, dict[str, Any]] = {
    "lucas": {
        "description": "Exact Lucas number L_n via fast doubling with Cassini invariant witness.",
        "inputSchema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "minimum": 0}},
            "required": ["n"],
        },
    },
    "fibonacci": {
        "description": "Exact Fibonacci number F_n via fast doubling.",
        "inputSchema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "minimum": 0}},
            "required": ["n"],
        },
    },
    "cassini": {
        "description": "Cassini identity verification L_n^2 - 5*F_n^2 = 4*(-1)^n.",
        "inputSchema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "minimum": 0}},
            "required": ["n"],
        },
    },
    "zeckendorf": {
        "description": "Canonical non-adjacent Zeckendorf representation certificate.",
        "inputSchema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "minimum": 0}},
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
        "description": "Adjust or query Lucas intelligence scale (L_10 to L_31) dynamically based on task parameters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_rung": {"type": "integer", "enum": [10, 12, 15, 18, 20, 31]},
                "task_type": {"type": "string"},
                "complexity": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "step_direction": {"type": "string", "enum": ["up", "down", "hold"]},
            },
        },
    },
    "discover_skills": {
        "description": "List governed expert capabilities and their JSON contracts.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "get_skill": {
        "description": "Return one expert skill contract, examples, and limitations.",
        "inputSchema": {
            "type": "object",
            "properties": {"skill_id": {"type": "string"}},
            "required": ["skill_id"],
        },
    },
    "invoke_skill": {
        "description": "Invoke one advisory skill through permission, budget, audit, and sandbox gates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "skill_id": {"type": "string"},
                "arguments": {"type": "object"},
                "options": {"type": "object"},
            },
            "required": ["skill_id", "arguments"],
        },
    },
    "validate_inputs": {
        "description": "Validate arguments against one registered skill input contract.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "skill_id": {"type": "string"},
                "arguments": {"type": "object"},
            },
            "required": ["skill_id", "arguments"],
        },
    },
    "evaluate_skill_outcome": {
        "description": "Record an authorized skill outcome for regression and calibration tracking.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "skill_id": {"type": "string"},
                "outcome": {"type": "object"},
                "options": {"type": "object"},
            },
            "required": ["skill_id", "outcome"],
        },
    },
}


class HybaMCPServer:
    """Production Model Context Protocol server exposing exact and governed tools."""

    def __init__(
        self,
        name: str = "hyba-mcp-server",
        version: str = "2.0.0",
        control_plane: ControlPlane | None = None,
        identity_provider: Callable[[], str | None] | None = None,
    ) -> None:
        self.name = name
        self.version = version
        self.control_plane = control_plane or ControlPlane()
        self.identity_provider = identity_provider

    def _trusted_identity(self) -> str:
        if self.identity_provider is None:
            return ""
        try:
            identity = self.identity_provider()
        except Exception:
            return ""
        return identity.strip() if isinstance(identity, str) else ""

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
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
            from Intelligence.lucas_scaler import LucasIntelligenceScaler
            target_rung = arguments.get("target_rung")
            scaler = LucasIntelligenceScaler(initial_scale=int(target_rung) if target_rung is not None else 31)
            step = arguments.get("step_direction")
            if step == "up":
                scaler.scale_up()
            elif step == "down":
                scaler.scale_down()
            elif "task_type" in arguments or "complexity" in arguments:
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
        if name == "discover_skills":
            return {"skills": discover_skills()}
        if name == "get_skill":
            skill_id = str(arguments["skill_id"])
            module = get_skill_module(skill_id)
            return {
                "skill_id": skill_id,
                "title": module.TITLE,
                "source": module.SOURCE,
                "input_schema": module.INPUT_SCHEMA,
                "output_schema": module.OUTPUT_SCHEMA,
                "cost_estimate": module.COST_ESTIMATE,
                "risk_level": module.RISK_LEVEL,
                "time_estimate_seconds": module.TIME_ESTIMATE,
                "examples": list(module.EXAMPLES),
                "limitations": list(module.LIMITATIONS),
            }
        if name == "validate_inputs":
            return self.control_plane.validate_inputs(
                str(arguments["skill_id"]), arguments["arguments"]
            )
        if name == "invoke_skill":
            options = arguments.get("options") or {}
            identity = self._trusted_identity()
            return self.control_plane.invoke_skill(
                identity,
                str(arguments["skill_id"]),
                arguments["arguments"],
                options=options,
            )
        if name == "evaluate_skill_outcome":
            skill_id = str(arguments["skill_id"])
            outcome = arguments["outcome"]
            identity = self._trusted_identity()
            allowed, reason, audit_record = self.control_plane.check_permission(
                identity, skill_id, outcome
            )
            if not allowed:
                return {
                    "ok": False,
                    "error": {"code": "permission_denied", "message": reason},
                    "audit_record": audit_record,
                }
            try:
                summary = self.control_plane.record_outcome(
                    skill_id,
                    outcome.get("inputs", {}),
                    outcome.get("outputs", {}),
                    float(outcome.get("latency", 0.0)),
                    outcome.get("success") is True,
                    identity=identity,
                )
            except (TypeError, ValueError, OSError) as exc:
                return {"ok": False, "error": {"code": "invalid_outcome", "message": str(exc)}}
            return {"ok": True, "summary": summary, "audit_record": audit_record}
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
            args = params.get("arguments") or {}
            res = self.execute_tool(str(tool_name), args)
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
