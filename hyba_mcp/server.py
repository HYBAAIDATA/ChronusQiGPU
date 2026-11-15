"""Newline-delimited JSON-RPC MCP server for the TURING maths wrapper.

Protocol shape follows the enterprise ``hyba_mcp`` server on
``import/phienterprise-20261111``: initialize, notifications/initialized,
tools/list, and tools/call. This process registers only the TURING tools.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Mapping

from .adapter import ToolInputError, TuringAdapter

PROTOCOL_VERSION = "2024-11-05"
STANDARD_PROTOCOL_VERSIONS = {PROTOCOL_VERSION, "2024-10-07", "2026-07-28"}
SERVER_INFO = {"name": "hyba-mcp-server", "version": "0.1.0"}
MAX_REQUEST_BYTES = 1_048_576

_GATE = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "qubits": {"type": "array"},
        "theta": {"type": "number"},
    },
    "required": ["name", "qubits"],
    "additionalProperties": False,
}
_SPEC = {
    "type": "object",
    "properties": {
        "n_qubits": {"type": "integer", "minimum": 1, "maximum": 30},
        "gates": {"type": "array", "items": _GATE, "maxItems": 64},
        "observables": {
            "type": "array",
            "maxItems": 16,
            "items": {"type": "string", "maxLength": 30},
        },
    },
    "required": ["n_qubits", "gates"],
    "additionalProperties": False,
}

TOOLS: dict[str, dict[str, Any]] = {
    "list_backends": {
        "description": (
            "List TURING maths backends. Only exact statevector is implemented. "
            "Density and hardware paths are reported as not implemented."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "validate_math": {
        "description": (
            "Check qubit bounds, memory cost, and, when the register is small, "
            "unitarity of the composed operator. Does not submit work."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "spec": _SPEC,
                "backend": {"type": "string"},
            },
            "required": ["spec"],
            "additionalProperties": False,
        },
    },
    "execute_circuit": {
        "description": (
            "Build the circuit with TURING operators, apply it to |0...0>, and "
            "return Born probabilities plus expectation values of spec.observables. "
            "Exact numerical mathematics, not a hardware job."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "spec": _SPEC,
                "backend": {"type": "string"},
                "include_amplitudes": {"type": "boolean"},
            },
            "required": ["spec"],
            "additionalProperties": False,
        },
    },
    "compute_expectation": {
        "description": (
            "Expectation value of a Pauli string after the circuit, on the "
            "statevector backend. The string length must equal n_qubits."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "spec": _SPEC,
                "observable": {"type": "string", "maxLength": 30},
                "backend": {"type": "string"},
            },
            "required": ["spec", "observable"],
            "additionalProperties": False,
        },
    },
}


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


class TuringMCPServer:
    """Stateful stdio session. Tools are refused until initialized."""

    def __init__(self, adapter: TuringAdapter | None = None) -> None:
        self.adapter = adapter or TuringAdapter()
        self.name = SERVER_INFO["name"]
        self.version = SERVER_INFO["version"]
        self._initialized = False
        self._ready = False

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

    def execute_tool(self, name: str, arguments: Any) -> dict[str, Any]:
        if name not in TOOLS:
            raise ToolInputError("unknown TURING MCP tool")
        if not isinstance(arguments, dict):
            raise ToolInputError("arguments must be a JSON object")
        schema = TOOLS[name]["inputSchema"]
        properties = schema.get("properties", {})
        if arguments.keys() - properties.keys():
            raise ToolInputError("arguments contain unsupported fields")
        missing = set(schema.get("required", [])) - arguments.keys()
        if missing:
            raise ToolInputError("required tool arguments are missing")
        if name == "list_backends":
            return self.adapter.list_backends()
        backend = arguments.get("backend", "statevector")
        if not isinstance(backend, str):
            raise ToolInputError("backend must be a string")
        spec = arguments["spec"]
        if name == "validate_math":
            return self.adapter.validate_math(spec, backend)
        if name == "execute_circuit":
            include = arguments.get("include_amplitudes")
            if include is not None and not isinstance(include, bool):
                raise ToolInputError("include_amplitudes must be a boolean")
            return self.adapter.execute_circuit(spec, backend, include)
        observable = arguments["observable"]
        if not isinstance(observable, str) or len(observable) > 30:
            raise ToolInputError("observable must be a Pauli string of at most 30 characters")
        return self.adapter.compute_expectation(spec, observable, backend)

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
            selected = (
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
                    "protocolVersion": selected,
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
                "result": {"tools": [{"name": key, **value} for key, value in TOOLS.items()]},
            }

        if method == "tools/call":
            if not has_id:
                return None
            tool_name = params.get("name")
            args = params.get("arguments", {})
            try:
                if not isinstance(tool_name, str):
                    raise ToolInputError("name must be a string")
                result = self.execute_tool(tool_name, args)
            except ToolInputError as exc:
                return self._error(rid, -32602, str(exc))
            except (ValueError, TypeError, KeyError):
                return self._error(rid, -32602, "Invalid tool arguments")
            except Exception:
                return self._error(rid, -32000, "Tool execution failed")
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                result,
                                sort_keys=True,
                                separators=(",", ":"),
                                allow_nan=False,
                            ),
                        }
                    ],
                    "isError": False,
                },
            }

        return None if not has_id else self._error(rid, -32601, "Method not found")


def run_server(stdin: Any | None = None, stdout: Any | None = None) -> None:
    """Serve one JSON object per line. Notifications produce no response line."""
    server = TuringMCPServer()
    reader = stdin if stdin is not None else sys.stdin
    writer = stdout if stdout is not None else sys.stdout
    while True:
        text = reader.readline(MAX_REQUEST_BYTES + 1)
        if not text:
            break
        if len(text.encode("utf-8", errors="replace")) > MAX_REQUEST_BYTES:
            while text and not text.endswith("\n"):
                text = reader.readline(MAX_REQUEST_BYTES + 1)
            writer.write(
                json.dumps(TuringMCPServer._error(None, -32600, "Request exceeds maximum size"))
                + "\n"
            )
            writer.flush()
            continue
        text = text.strip()
        if not text:
            continue
        try:
            request = json.loads(
                text,
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_json_constant,
            )
        except (json.JSONDecodeError, ValueError):
            writer.write(json.dumps(TuringMCPServer._error(None, -32700, "Parse error")) + "\n")
            writer.flush()
            continue
        response = server.handle_request(request)
        if response is not None:
            writer.write(json.dumps(response, allow_nan=False) + "\n")
            writer.flush()


# Enterprise clients import this name from hyba_mcp.server.
HybaMCPServer = TuringMCPServer


if __name__ == "__main__":
    run_server()
