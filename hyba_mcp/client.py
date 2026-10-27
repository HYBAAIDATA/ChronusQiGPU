"""HYBA Sovereign MCP Client.

Provides session management, tool execution, and authenticated evidence collection
over Model Context Protocol servers.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from .server import HybaMCPServer


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def verify_evidence_pack(
    pack: Mapping[str, Any], signing_key: bytes, *, expected_session_id: Optional[str] = None
) -> bool:
    """Verify a pack using a trusted, out-of-band key; unsigned packs fail closed."""
    if not isinstance(signing_key, bytes) or len(signing_key) < 32:
        return False
    try:
        signed = dict(pack)
        signature = signed.pop("evidence_signature")
        digest = signed.pop("evidence_digest")
        if not isinstance(signature, str) or not isinstance(digest, str):
            return False
        if signed.get("signature_algorithm") != "HMAC-SHA256":
            return False
        if expected_session_id is not None and signed.get("session_id") != expected_session_id:
            return False
        computed_digest = hashlib.sha256(_canonical_json(signed)).hexdigest()
        signed["evidence_digest"] = digest
        computed_signature = hmac.new(
            signing_key, _canonical_json(signed), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(digest, computed_digest) and hmac.compare_digest(
            signature, computed_signature
        )
    except (KeyError, TypeError, ValueError, UnicodeError):
        return False


@dataclass
class MCPSession:
    session_id: str
    started_at: float = field(default_factory=time.time)
    tools_called: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    theorem_proven: bool = False


class HybaMCPClient:
    """Production client for invoking HYBA MCP capabilities."""

    def __init__(self, server: Optional[HybaMCPServer] = None) -> None:
        self.server = server or HybaMCPServer()
        self.session: Optional[MCPSession] = None
        self._session_secret: Optional[bytes] = None
        self._next_id = 1

    def start_session(self, *, signing_key: Optional[bytes] = None) -> MCPSession:
        """Start with an ephemeral 256-bit key, or a caller-managed key of >=32 bytes."""
        if self.session is not None:
            raise RuntimeError("an MCP session is already active; end it before starting another")
        if signing_key is not None and (
            not isinstance(signing_key, bytes) or len(signing_key) < 32
        ):
            raise ValueError("signing_key must contain at least 32 bytes")
        session = MCPSession(session_id=secrets.token_hex(16))
        # Verify handshake with server
        resp = self.server.handle_request({
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": "initialize",
            "params": {},
        })
        self._next_id += 1
        if "error" in resp or not isinstance(resp.get("result"), dict):
            raise RuntimeError("MCP initialization failed")
        session.evidence.append({"handshake": resp["result"]})
        self._session_secret = signing_key if signing_key is not None else secrets.token_bytes(32)
        self.session = session
        return session

    def list_tools(self) -> list[dict[str, Any]]:
        resp = self.server.handle_request({
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": "tools/list",
            "params": {},
        })
        self._next_id += 1
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        if not self.session:
            raise RuntimeError("no active MCP session; call start_session() first")
        resp = self.server.handle_request({
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": dict(arguments)},
        })
        self._next_id += 1
        if "error" in resp:
            raise RuntimeError(f"MCP tool {name!r} failed: {resp['error']}")
        content = resp.get("result", {}).get("content", [])
        if not content:
            return {}
        result_payload = json.loads(content[0]["text"])
        self.session.tools_called.append(name)
        self.session.evidence.append(
            json.loads(
                _canonical_json(
                    {"tool": name, "arguments": dict(arguments), "output": result_payload}
                )
            )
        )
        return result_payload

    def produce_evidence_pack(self) -> dict[str, Any]:
        if not self.session or self._session_secret is None:
            raise RuntimeError("no active MCP session")
        pack = {
            "session_id": self.session.session_id,
            "tools_called": list(self.session.tools_called),
            "evidence_entries": len(self.session.evidence),
            "evidence": self.session.evidence,
            "theorem_proven": False,
            "sovereignty": "HYBA_SOVEREIGN_CNS",
            "narrow_ai_credit": "NONE_FORBIDDEN",
            "timestamp": time.time(),
            "signature_algorithm": "HMAC-SHA256",
        }
        # Snapshot mutable evidence so exported packs cannot mutate the live session.
        pack = json.loads(_canonical_json(pack))
        pack["evidence_digest"] = hashlib.sha256(_canonical_json(pack)).hexdigest()
        pack["evidence_signature"] = hmac.new(
            self._session_secret, _canonical_json(pack), hashlib.sha256
        ).hexdigest()
        return pack

    def verify_evidence_pack(self, pack: Mapping[str, Any]) -> bool:
        """Verify against this active session's identity and private key."""
        if self.session is None or self._session_secret is None:
            return False
        return verify_evidence_pack(
            pack, self._session_secret, expected_session_id=self.session.session_id
        )

    def scale_intelligence(
        self,
        target_rung: Optional[int] = None,
        task_type: Optional[str] = None,
        complexity: Optional[float] = None,
        step_direction: Optional[str] = None,
    ) -> dict[str, Any]:
        """Invoke the stateless scaler; see the server tool schema and README_MCP.md."""
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
        try:
            return self.produce_evidence_pack()
        finally:
            self.session = None
            self._session_secret = None
