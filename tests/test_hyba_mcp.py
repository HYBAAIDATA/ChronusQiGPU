"""Verification tests for the production HYBA Sovereign MCP Suite."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from hyba_mcp.server import HybaMCPServer, run_server
from hyba_mcp.client import HybaMCPClient


def _ready_server() -> HybaMCPServer:
    server = HybaMCPServer()
    response = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "tests", "version": "1.0"},
            },
        }
    )
    assert response is not None
    server.handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"})
    return server


class TestHybaMCPServer:
    def test_handshake_declares_sovereign_doctrine(self) -> None:
        server = HybaMCPServer()
        resp = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "tests", "version": "1.0"},
                },
            }
        )
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        assert resp["result"]["protocolVersion"] == "2024-11-05"
        assert resp["result"]["serverInfo"]["name"] == "hyba-mcp-server"
        assert resp["result"]["capabilities"] == {"tools": {"listChanged": False}}

    def test_tools_list_contains_exact_mathematical_suite(self) -> None:
        server = _ready_server()
        resp = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }
        )
        tools = {t["name"]: t for t in resp["result"]["tools"]}
        assert "lucas" in tools
        assert "fibonacci" in tools
        assert "cassini" in tools
        assert "zeckendorf" in tools
        assert "ladder_verify" in tools
        assert "ladder_capacity" in tools
        assert "largest_feasible_tile" in tools
        assert "sha256d_verify" in tools
        assert "scale_intelligence" in tools
        assert tools["fibonacci"]["inputSchema"]["properties"]["n"]["maximum"] == 10_000

    def test_lucas_15_and_20_tool_calls_hold_cassini_invariant(self) -> None:
        server = _ready_server()
        # L_15 = 1364, F_15 = 610
        r15 = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "lucas", "arguments": {"n": 15}},
            }
        )
        payload15 = json.loads(r15["result"]["content"][0]["text"])
        assert payload15["L_n"] == 1364
        assert payload15["F_n"] == 610
        assert payload15["cassini_holds"] is True
        assert payload15["left"] == -4

        # L_20 = 15127, F_20 = 6765
        r20 = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "lucas", "arguments": {"n": 20}},
            }
        )
        payload20 = json.loads(r20["result"]["content"][0]["text"])
        assert payload20["L_n"] == 15127
        assert payload20["F_n"] == 6765
        assert payload20["cassini_holds"] is True
        assert payload20["left"] == 4

    def test_sha256d_verify_tool_call(self) -> None:
        server = _ready_server()
        header_hex = "00" * 80
        r = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "sha256d_verify",
                    "arguments": {"payload_hex": header_hex, "compact_bits": 0x1D00FFFF},
                },
            }
        )
        payload = json.loads(r["result"]["content"][0]["text"])
        assert "sha256d_be" in payload
        assert "meets_target" in payload
        assert r["result"]["isError"] is False

    def test_server_enforces_initialize_lifecycle_and_silences_notifications(self) -> None:
        server = HybaMCPServer()
        assert server.handle_request({"jsonrpc": "2.0", "id": "ping-1", "method": "ping"}) == {
            "jsonrpc": "2.0",
            "id": "ping-1",
            "result": {},
        }
        premature = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert premature["error"]["code"] == -32002

        initialized = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "initialize",
                "params": {
                    "protocolVersion": "unsupported",
                    "capabilities": {},
                    "clientInfo": {"name": "tests", "version": "1.0"},
                },
            }
        )
        assert initialized["result"]["protocolVersion"] == "2024-11-05"
        assert (
            server.handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
        )
        assert server.handle_request({"jsonrpc": "2.0", "method": "notifications/unknown"}) is None

    @pytest.mark.parametrize(
        "name,arguments",
        [
            ("fibonacci", {"n": True}),
            ("lucas", {"n": "15"}),
            ("cassini", {"n": 10_001}),
            ("largest_feasible_tile", {"max_size": 32, "extra": 1}),
            ("sha256d_verify", {"payload_hex": "0"}),
            ("sha256d_verify", {"payload_hex": "00", "compact_bits": -1}),
            ("scale_intelligence", {"target_rung": 999}),
        ],
    )
    def test_tool_validation_returns_safe_is_error_result(
        self, name: str, arguments: dict[str, object]
    ) -> None:
        response = _ready_server().handle_request(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        assert response["result"]["isError"] is True
        text = response["result"]["content"][0]["text"]
        assert "Traceback" not in text
        assert "TypeError" not in text

    def test_tool_call_unknown_name_is_a_tool_error(self) -> None:
        response = _ready_server().handle_request(
            {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {"name": "does_not_exist", "arguments": {}},
            }
        )
        assert response["result"]["isError"] is True
        assert json.loads(response["result"]["content"][0]["text"]) == {
            "error": "unknown HYBA MCP tool"
        }

    def test_compact_target_must_fit_uint256(self) -> None:
        response = _ready_server().handle_request(
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {
                    "name": "sha256d_verify",
                    "arguments": {"payload_hex": "00", "compact_bits": 0x2200FFFF},
                },
            }
        )
        result = json.loads(response["result"]["content"][0]["text"])
        assert response["result"]["isError"] is True
        assert result["error"] == "compact_bits decodes to a target larger than uint256"

    def test_stdio_parser_returns_protocol_error_without_exception_details(
        self, monkeypatch
    ) -> None:
        stdin = io.StringIO('{"jsonrpc":"2.0","id":1,"id":2,"method":"tools/list"}\n')
        stdout = io.StringIO()
        monkeypatch.setattr("sys.stdin", stdin)
        monkeypatch.setattr("sys.stdout", stdout)

        run_server()

        response = json.loads(stdout.getvalue())
        assert response["error"]["code"] == -32700
        assert response["error"]["message"] == "Parse error"

    def test_module_entrypoint_has_clean_stdio(self) -> None:
        messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "tests", "version": "1.0"},
                },
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
        ]
        result = subprocess.run(
            [sys.executable, "-m", "hyba_mcp.server"],
            cwd=Path(__file__).resolve().parents[1],
            input="\n".join(json.dumps(message) for message in messages) + "\n",
            text=True,
            capture_output=True,
            check=True,
            timeout=15,
        )
        assert result.stderr == ""
        assert len(result.stdout.splitlines()) == 1
        assert json.loads(result.stdout)["result"]["protocolVersion"] == "2024-11-05"


class TestHybaMCPClient:
    def test_client_session_lifecycle_and_evidence_pack(self) -> None:
        client = HybaMCPClient()
        session = client.start_session()
        assert session.session_id is not None

        tools = client.list_tools()
        assert len(tools) >= 8

        res = client.call_tool("zeckendorf", {"n": 1364})
        assert res["valid"] is True
        assert res["non_adjacency"] is True

        pack = client.end_session()
        assert client.session is None
        assert pack["sovereignty"] == "HYBA_SOVEREIGN_CNS"
        assert pack["narrow_ai_credit"] == "NONE_FORBIDDEN"
        assert pack["evidence_digest"] is not None
        assert pack["evidence_entries"] == 2
        assert pack["evidence"][-1]["output"]["n"] == 1364
        digest = pack.pop("evidence_digest")
        canonical = json.dumps(
            pack,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        assert digest == hashlib.sha256(canonical).hexdigest()
