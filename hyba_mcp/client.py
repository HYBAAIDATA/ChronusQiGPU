"""HYBA Sovereign MCP Client.

Provides in-process session management, tool execution, and evidence-digest
collection for the local HYBA MCP server.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from .server import HybaMCPServer


@dataclass
class MCPSession:
    session_id: str
    started_at: float = field(default_factory=time.time)
    tools_called: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    theorem_proven: bool = False


class HybaMCPClient:
    """In-process client for invoking local HYBA MCP capabilities."""

    def __init__(self, server: Optional[HybaMCPServer] = None) -> None:
        self.server = server or HybaMCPServer()
        self.session: Optional[MCPSession] = None
        self._next_id = 1

    def start_session(self) -> MCPSession:
        sid = secrets.token_hex(16)
        session = MCPSession(session_id=sid)
        resp = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": self._next_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "hyba-mcp-client", "version": "1.0.0"},
                },
            }
        )
        self._next_id += 1
        if not resp or "error" in resp:
            raise RuntimeError(
                f"MCP initialize failed: {resp.get('error') if resp else 'no response'}"
            )
        session.evidence.append({"handshake": resp.get("result")})
        self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
        )
        self.session = session
        return session

    def list_tools(self) -> list[dict[str, Any]]:
        resp = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": self._next_id,
                "method": "tools/list",
                "params": {},
            }
        )
        self._next_id += 1
        if "error" in resp:
            raise RuntimeError(f"MCP tools/list failed: {resp['error']}")
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        if not self.session:
            raise RuntimeError("no active MCP session; call start_session() first")
        resp = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": self._next_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": dict(arguments)},
            }
        )
        self._next_id += 1
        if "error" in resp:
            raise RuntimeError(f"MCP tool {name!r} failed: {resp['error']}")
        content = resp.get("result", {}).get("content", [])
        if not content:
            return {}
        result_payload = json.loads(content[0]["text"])
        if resp.get("result", {}).get("isError"):
            raise RuntimeError(
                f"MCP tool {name!r} failed: {result_payload.get('error', 'tool error')}"
            )
        self.session.tools_called.append(name)
        self.session.evidence.append({"tool": name, "output": result_payload})
        return result_payload

    def produce_evidence_pack(self) -> dict[str, Any]:
        if not self.session:
            raise RuntimeError("no active MCP session")
        pack = {
            "session_id": self.session.session_id,
            "tools_called": list(self.session.tools_called),
            "evidence": deepcopy(self.session.evidence),
            "evidence_entries": len(self.session.evidence),
            "theorem_proven": False,
            "sovereignty": "HYBA_SOVEREIGN_CNS",
            "narrow_ai_credit": "NONE_FORBIDDEN",
            "timestamp": time.time(),
        }
        canonical = json.dumps(
            pack,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        digest = hashlib.sha256(canonical).hexdigest()
        pack["evidence_digest"] = digest
        return pack

    def scale_intelligence(
        self,
        target_rung: Optional[int] = None,
        task_type: Optional[str] = None,
        complexity: Optional[float] = None,
        step_direction: Optional[str] = None,
    ) -> dict[str, Any]:
        args: dict[str, Any] = {}
        if target_rung is not None:
            args["target_rung"] = target_rung
        if task_type is not None:
            args["task_type"] = task_type
        if complexity is not None:
            args["complexity"] = complexity
        if step_direction is not None:
            args["step_direction"] = step_direction
        return self.call_tool("scale_intelligence", args)

    def end_session(self) -> dict[str, Any]:
        pack = self.produce_evidence_pack()
        self.session = None
        return pack
