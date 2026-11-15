"""In-process client for the HYBA MCP stdio session.

This is the connection used by enterprise callers: construct a client, start
a session (initialize plus notifications/initialized), then call a tool.
TURING tools run in this process. Lucas, skill, and Salamander tools are not
registered here; that package was not imported into this checkout.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from .server import HybaMCPServer


class HybaMCPClient:
    """Connect to a local HybaMCPServer and invoke its tools."""

    def __init__(self, server: Optional[HybaMCPServer] = None) -> None:
        self.server = server if server is not None else HybaMCPServer()
        self.connected = False
        self._next_id = 1

    def start_session(self) -> dict[str, Any]:
        """Complete the MCP handshake. Raises if the server rejects it."""
        if self.connected:
            raise RuntimeError("MCP session is already connected")
        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": self._next_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "hyba-mcp-client", "version": "0.1.0"},
                },
            }
        )
        self._next_id += 1
        if not isinstance(response, dict) or "error" in response:
            detail = response.get("error") if isinstance(response, dict) else None
            raise RuntimeError(f"MCP initialization failed: {detail}")
        notice = self.server.handle_request(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        if notice is not None:
            raise RuntimeError("initialized notification must not return a response")
        self.connected = True
        return response["result"]

    def list_tools(self) -> list[dict[str, Any]]:
        self._require_connection()
        response = self._request("tools/list", {})
        return response.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._require_connection()
        response = self._request(
            "tools/call",
            {"name": name, "arguments": dict(arguments or {})},
        )
        if "error" in response:
            raise RuntimeError(f"MCP tool {name!r} failed: {response['error']}")
        content = response.get("result", {}).get("content", [])
        if not content:
            return {}
        payload = json.loads(content[0]["text"])
        if response.get("result", {}).get("isError"):
            raise RuntimeError(f"MCP tool {name!r} failed: {payload}")
        return payload

    def _require_connection(self) -> None:
        if not self.connected:
            raise RuntimeError("no active MCP session; call start_session() first")

    def _request(self, method: str, params: Mapping[str, Any]) -> dict[str, Any]:
        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": self._next_id,
                "method": method,
                "params": dict(params),
            }
        )
        self._next_id += 1
        if not isinstance(response, dict):
            raise RuntimeError(f"MCP {method} returned no response")
        return response


def connect(server: Optional[HybaMCPServer] = None) -> HybaMCPClient:
    """Start a connected session against the local HYBA MCP server."""
    client = HybaMCPClient(server)
    client.start_session()
    return client
