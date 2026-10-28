#!/usr/bin/env python3
"""Bounded local stdio MCP server for HYBA mathematical and governed tools."""

from __future__ import annotations

import json
import logging
import math
import re
import sys
from typing import Any, Callable, Mapping

from .control_plane import ControlPlane
from .salamander import MAX_AUTHORITY_LEASE_SECONDS, SALAMANDER_TOOLS, SalamanderTools
from .skills import discover_skills, get_skill_module

from .hyba_context import EXECUTE_PATCH, TOOLS_PATCH

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {
    "name": "hyba-mcp-server",
    "version": "2.0.0",
    "sovereignty": "HYBA_SOVEREIGN_CNS",
    "narrow_ai_credit": "NONE_FORBIDDEN",
}
STANDARD_PROTOCOL_VERSIONS = {PROTOCOL_VERSION, "2024-10-07", "2026-07-28"}
MAX_SEQUENCE_INDEX = 10_000
MAX_N = MAX_SEQUENCE_INDEX
MAX_INTEGER_ARGUMENT = (1 << 63) - 1
MAX_PAYLOAD_BYTES = 1_048_576
MAX_REQUEST_BYTES = 2 * MAX_PAYLOAD_BYTES + 65_536
MAX_TASK_TYPE_LENGTH = 256

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
    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False and arguments.keys() - properties.keys():
        raise ValueError("arguments contain unsupported fields")
    for key in schema.get("required", []):
        if key not in arguments:
            raise ValueError(f"missing required argument: {key}")
    for key, spec in properties.items():
        if key not in arguments:
            continue
        value = arguments[key]
        kind = spec["type"]
        if (
            (kind == "integer" and type(value) is not int)
            or (kind == "number" and type(value) not in (int, float))
            or (kind == "string" and not isinstance(value, str))
            or (kind == "object" and not isinstance(value, Mapping))
            or (kind == "array" and not isinstance(value, list))
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
        if kind == "string" and "maxLength" in spec and len(value) > spec["maxLength"]:
            raise ValueError(f"{key} exceeds the maximum length")


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
        return {
            "n": 0,
            "indices": [],
            "non_adjacency": True,
            "valid": True,
            "theorem_proven": False,
        }
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
    return {
        "n": n,
        "indices": indices,
        "non_adjacency": True,
        "valid": True,
        "theorem_proven": False,
    }


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


class ToolInputError(ValueError):
    """A safe, caller-correctable MCP tool argument error."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _validated_arguments(name: str, arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise ToolInputError("arguments must be a JSON object")

    schemas: dict[str, tuple[set[str], set[str]]] = {
        "lucas": ({"n"}, {"n"}),
        "fibonacci": ({"n"}, {"n"}),
        "cassini": ({"n"}, {"n"}),
        "zeckendorf": ({"n"}, {"n"}),
        "ladder_verify": (set(), set()),
        "ladder_capacity": ({"bound"}, {"bound"}),
        "largest_feasible_tile": ({"max_size", "alignment"}, {"max_size"}),
        "sha256d_verify": ({"payload_hex", "compact_bits"}, {"payload_hex"}),
        "scale_intelligence": (
            {"target_rung", "task_type", "complexity", "step_direction"},
            set(),
        ),
    }
    if name not in schemas:
        raise ToolInputError("unknown HYBA MCP tool")

    allowed, required = schemas[name]
    unknown = arguments.keys() - allowed
    missing = required - arguments.keys()
    if unknown:
        raise ToolInputError("arguments contain unsupported fields")
    if missing:
        raise ToolInputError("required tool arguments are missing")

    def integer(field: str, minimum: int, maximum: int) -> int:
        value = arguments[field]
        if type(value) is not int or not minimum <= value <= maximum:
            raise ToolInputError(f"{field} must be an integer between {minimum} and {maximum}")
        return value

    if name in {"lucas", "fibonacci", "cassini", "zeckendorf"}:
        integer("n", 0, MAX_SEQUENCE_INDEX)
    elif name == "ladder_capacity":
        integer("bound", 1, MAX_INTEGER_ARGUMENT)
    elif name == "largest_feasible_tile":
        integer("max_size", 1, MAX_INTEGER_ARGUMENT)
        if "alignment" in arguments:
            integer("alignment", 1, MAX_INTEGER_ARGUMENT)
    elif name == "sha256d_verify":
        payload_hex = arguments["payload_hex"]
        if not isinstance(payload_hex, str):
            raise ToolInputError("payload_hex must be a hexadecimal string")
        if len(payload_hex) > MAX_PAYLOAD_BYTES * 2:
            raise ToolInputError("payload_hex exceeds the maximum payload size")
        if len(payload_hex) % 2 or re.fullmatch(r"[0-9a-fA-F]*", payload_hex) is None:
            raise ToolInputError("payload_hex must contain complete hexadecimal bytes")
        if "compact_bits" in arguments:
            integer("compact_bits", 0, 0xFFFFFFFF)
    elif name == "scale_intelligence":
        if "target_rung" in arguments:
            rung = integer("target_rung", 0, MAX_INTEGER_ARGUMENT)
            if rung not in {10, 12, 15, 18, 20, 31}:
                raise ToolInputError("target_rung is not a supported Lucas scale rung")
        if "task_type" in arguments:
            task_type = arguments["task_type"]
            if not isinstance(task_type, str) or len(task_type) > MAX_TASK_TYPE_LENGTH:
                raise ToolInputError("task_type must be a short string")
        if "complexity" in arguments:
            complexity = arguments["complexity"]
            if (
                isinstance(complexity, bool)
                or not isinstance(complexity, (int, float))
                or not 0 <= complexity <= 1
                or not math.isfinite(complexity)
            ):
                raise ToolInputError("complexity must be a finite number between 0 and 1")
        if "step_direction" in arguments:
            direction = arguments["step_direction"]
            if not isinstance(direction, str) or direction not in {"up", "down", "hold"}:
                raise ToolInputError("step_direction must be up, down, or hold")

    return arguments


TOOLS: dict[str, dict[str, Any]] = {
    "lucas": {
        "description": "Exact Lucas number L_n via fast doubling with Cassini invariant witness.",
        "inputSchema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "minimum": 0, "maximum": MAX_SEQUENCE_INDEX}},
            "required": ["n"],
            "additionalProperties": False,
        },
    },
    "fibonacci": {
        "description": "Exact Fibonacci number F_n via fast doubling.",
        "inputSchema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "minimum": 0, "maximum": MAX_SEQUENCE_INDEX}},
            "required": ["n"],
            "additionalProperties": False,
        },
    },
    "cassini": {
        "description": "Cassini identity verification L_n^2 - 5*F_n^2 = 4*(-1)^n.",
        "inputSchema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "minimum": 0, "maximum": MAX_SEQUENCE_INDEX}},
            "required": ["n"],
            "additionalProperties": False,
        },
    },
    "zeckendorf": {
        "description": "Canonical non-adjacent Zeckendorf representation certificate.",
        "inputSchema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "minimum": 0, "maximum": MAX_SEQUENCE_INDEX}},
            "required": ["n"],
            "additionalProperties": False,
        },
    },
    "ladder_verify": {
        "description": "Verify the canonical Lucas scale ladder stops.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "ladder_capacity": {
        "description": "Snap an envelope/retention bound to the nearest valid ladder stop.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "bound": {"type": "integer", "minimum": 1, "maximum": MAX_INTEGER_ARGUMENT}
            },
            "required": ["bound"],
            "additionalProperties": False,
        },
    },
    "largest_feasible_tile": {
        "description": "Compute largest power-of-two work tile compatible with alignment.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "max_size": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_INTEGER_ARGUMENT,
                },
                "alignment": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_INTEGER_ARGUMENT,
                    "default": 16,
                },
            },
            "required": ["max_size"],
            "additionalProperties": False,
        },
    },
    "sha256d_verify": {
        "description": "Compute independent double SHA-256 hash and check against uint256 target.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "payload_hex": {
                    "type": "string",
                    "maxLength": MAX_PAYLOAD_BYTES * 2,
                    "pattern": "^(?:[0-9a-fA-F]{2})*$",
                },
                "compact_bits": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 4294967295,
                },
            },
            "required": ["payload_hex"],
            "additionalProperties": False,
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
                    "maxLength": MAX_TASK_TYPE_LENGTH,
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
            "additionalProperties": False,
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
TOOLS.update(TOOLS_PATCH)
TOOLS.update(SALAMANDER_TOOLS)


class HybaMCPServer:
    """Production Model Context Protocol server exposing exact and governed tools."""

    def __init__(
        self,
        name: str = "hyba-mcp-server",
        version: str = "2.0.0",
        control_plane: ControlPlane | None = None,
        identity_provider: Callable[[], str | None] | None = None,
        salamander_enabled: bool = False,
    ) -> None:
        self.name = name
        self.version = version
        self.control_plane = control_plane or ControlPlane()
        self.identity_provider = identity_provider
        self.salamander_tools = SalamanderTools(
            self.control_plane,
            enabled=salamander_enabled,
        )
        self._initialized = False
        self._ready = False

    def _trusted_identity(self) -> str:
        if self.identity_provider is None:
            return ""
        try:
            identity = self.identity_provider()
        except Exception:
            return ""
        return identity.strip() if isinstance(identity, str) else ""

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
        if name in {
            "lucas",
            "fibonacci",
            "cassini",
            "zeckendorf",
            "ladder_verify",
            "ladder_capacity",
            "largest_feasible_tile",
            "sha256d_verify",
            "scale_intelligence",
        }:
            arguments = _validated_arguments(name, arguments)
        else:
            validate_arguments(name, arguments)
        if name == "lucas":
            n = arguments["n"]
            return {"L_n": lucas(n), **cassini_witness(n)}
        if name == "fibonacci":
            n = arguments["n"]
            return {"F_n": fibonacci(n), "theorem_proven": False}
        if name == "cassini":
            return cassini_witness(arguments["n"])
        if name == "zeckendorf":
            return zeckendorf(arguments["n"])
        if name == "ladder_verify":
            return verify_ladder()
        if name == "ladder_capacity":
            return {"capacity": ladder_capacity(arguments["bound"]), "theorem_proven": False}
        if name == "largest_feasible_tile":
            return largest_feasible_tile(
                arguments["max_size"],
                arguments.get("alignment", 16),
            )
        if name == "sha256d_verify":
            raw = bytes.fromhex(arguments["payload_hex"])
            digest = sha256d(raw)
            result = {
                "sha256d_le": digest.hex(),
                "sha256d_be": digest[::-1].hex(),
            }
            if "compact_bits" in arguments:
                try:
                    target = compact_target(arguments["compact_bits"])
                except ValueError as exc:
                    raise ToolInputError(
                        "compact_bits is not a valid positive compact target"
                    ) from exc
                if target > (1 << 256) - 1:
                    raise ToolInputError("compact_bits decodes to a target larger than uint256")
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
        if name in SALAMANDER_TOOLS:
            return self.salamander_tools.execute(name, arguments, self._trusted_identity())
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
            skill_id = str(arguments["skill_id"])
            skill_arguments = arguments["arguments"]
            if skill_id == "security.verify_authority" and isinstance(skill_arguments, Mapping):
                skill_arguments = {**skill_arguments, "identity": identity}
                if skill_arguments.get("capability") == "salamander.optimise":
                    duration = skill_arguments.get("lease_duration")
                    if (
                        isinstance(duration, bool)
                        or not isinstance(duration, (int, float))
                        or (isinstance(duration, float) and not math.isfinite(duration))
                        or duration <= 0
                        or duration > MAX_AUTHORITY_LEASE_SECONDS
                    ):
                        raise ToolInputError(
                            f"Salamander authority leases are limited to "
                            f"{MAX_AUTHORITY_LEASE_SECONDS:g} seconds"
                        )
            result = self.control_plane.invoke_skill(
                identity,
                skill_id,
                skill_arguments,
                options=options,
            )
            if skill_id == "security.verify_authority" and isinstance(skill_arguments, Mapping):
                lease = self.salamander_tools.issue_authority_lease(
                    identity,
                    skill_arguments,
                    result,
                )
                if lease is not None:
                    result = {**result, "authority_lease": lease}
            return result
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
        if name == "hyba_context":
            self.control_plane.enforce_context_budget(
                arguments.get("tier", "T0"),
                arguments.get("budget_bytes"),
            )
            return EXECUTE_PATCH[name](**arguments)
        if name in EXECUTE_PATCH:
            return EXECUTE_PATCH[name](**arguments)
        raise ValueError(f"Unknown HYBA MCP tool: {name}")

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

    def handle_request(self, req: Any) -> dict[str, Any] | None:
        if not isinstance(req, Mapping) or req.get("jsonrpc") != "2.0":
            if isinstance(req, Mapping) and "id" not in req:
                return None
            request_id = req.get("id") if isinstance(req, Mapping) else None
            return self._error(request_id, -32600, "Invalid JSON-RPC request")

        method = req.get("method")
        has_id = "id" in req
        rid = req.get("id")
        if not isinstance(method, str) or not method:
            return None if not has_id else self._error(rid, -32600, "Invalid JSON-RPC request")
        if has_id and (isinstance(rid, bool) or not isinstance(rid, (str, int))):
            return self._error(None, -32600, "Invalid JSON-RPC request id")

        params = req.get("params", {})
        if not isinstance(params, Mapping):
            return None if not has_id else self._error(rid, -32600, "Invalid request parameters")

        if method == "initialize":
            if not has_id:
                return None
            if self._initialized:
                return self._error(rid, -32600, "Server has already been initialized")
            protocol_version = params.get("protocolVersion")
            if (
                not isinstance(protocol_version, str)
                or not isinstance(params.get("capabilities"), Mapping)
                or not isinstance(params.get("clientInfo"), Mapping)
            ):
                return self._error(rid, -32602, "Invalid initialize parameters")
            selected_version = (
                protocol_version
                if protocol_version in STANDARD_PROTOCOL_VERSIONS
                else PROTOCOL_VERSION
            )
            self._initialized = True
            self._ready = False
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "protocolVersion": selected_version,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": self.name, "version": self.version},
                },
            }

        if method in ("server/discover", "server/info"):
            if not has_id:
                return None
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "protocolVersions": sorted(STANDARD_PROTOCOL_VERSIONS),
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": self.name, "version": self.version},
                },
            }

        if method == "notifications/initialized":
            if has_id:
                return self._error(rid, -32600, "initialized must be a notification")
            if self._initialized:
                self._ready = True
            return None

        if method == "ping":
            if not has_id:
                return None
            return {"jsonrpc": "2.0", "id": rid, "result": {}}

        if not self._ready:
            return None if not has_id else self._error(rid, -32002, "Server is not initialized")

        if method == "tools/list":
            if not has_id:
                return None
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {"tools": [{"name": k, **v} for k, v in TOOLS.items()]},
            }

        if method == "tools/call":
            if not has_id:
                return None
            tool_name = params.get("name")
            args = params.get("arguments", {})
            try:
                if not isinstance(tool_name, str):
                    raise ToolInputError("name must be a string")
                res = self.execute_tool(tool_name, args)
            except (ToolInputError, ValueError, TypeError, KeyError) as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {
                        "code": -32602,
                        "message": (
                            str(exc)
                            if isinstance(exc, ToolInputError)
                            else "Invalid tool arguments"
                        ),
                    },
                }
            except RuntimeError:
                return {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {
                        "code": -32000,
                        "message": (
                            "scale_intelligence unavailable"
                            if tool_name == "scale_intelligence"
                            else "Tool execution failed"
                        ),
                    },
                }
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                res, sort_keys=True, separators=(",", ":"), allow_nan=False
                            ),
                        }
                    ],
                    "isError": False,
                },
            }

        return None if not has_id else self._error(rid, -32601, "Method not found")


def run_server() -> None:
    server = HybaMCPServer()
    while True:
        text = sys.stdin.readline(MAX_REQUEST_BYTES + 1)
        if not text:
            break
        if len(text.encode("utf-8", errors="replace")) > MAX_REQUEST_BYTES:
            while text and not text.endswith("\n"):
                text = sys.stdin.readline(MAX_REQUEST_BYTES + 1)
            print(
                json.dumps(HybaMCPServer._error(None, -32600, "Request exceeds maximum size")),
                flush=True,
            )
            continue
        text = text.strip()
        if not text:
            continue
        request_id: Any = None
        try:
            req = json.loads(
                text,
                parse_constant=_reject_json_constant,
                object_pairs_hook=_reject_duplicate_keys,
            )
            if isinstance(req, Mapping):
                request_id = req.get("id")
            resp = server.handle_request(req)
        except (json.JSONDecodeError, ValueError):
            resp = HybaMCPServer._error(None, -32700, "Parse error")
        except Exception:
            resp = HybaMCPServer._error(request_id, -32603, "Internal error")
        if resp is not None:
            print(json.dumps(resp, separators=(",", ":"), allow_nan=False), flush=True)


if __name__ == "__main__":
    run_server()
