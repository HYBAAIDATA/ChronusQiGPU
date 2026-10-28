"""Verification tests for the production HYBA Sovereign MCP Suite."""

from __future__ import annotations

import hashlib
import io
import json
import hmac
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

import hyba_mcp.server as server_module
from hyba_mcp.server import HybaMCPServer, MAX_N, TOOLS
from hyba_mcp.client import HybaMCPClient, verify_evidence_pack
from hyba_mcp.server import run_server


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
        exact_math_tools = {
            "lucas",
            "fibonacci",
            "cassini",
            "zeckendorf",
            "ladder_verify",
            "ladder_capacity",
            "largest_feasible_tile",
            "sha256d_verify",
            "scale_intelligence",
        }
        assert exact_math_tools <= tools.keys()
        assert len(tools) == len(exact_math_tools) + 2 + 5
        assert tools["fibonacci"]["inputSchema"]["properties"]["n"]["maximum"] == MAX_N

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

    def test_lucas_10_benchmark_anchor_is_exact(self) -> None:
        response = HybaMCPServer().handle_request({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "lucas", "arguments": {"n": 10}},
        })
        payload = json.loads(response["result"]["content"][0]["text"])
        assert payload["n"] == 10
        assert payload["L_n"] == 123
        assert payload["F_n"] == 55
        assert payload["cassini_holds"] is True
        assert payload["left"] == payload["right"] == 4
        assert payload["theorem_proven"] is False

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
    def test_tool_validation_returns_safe_json_rpc_error(
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
        assert response["error"]["code"] == -32602
        assert "Traceback" not in response["error"]["message"]
        assert "TypeError" not in response["error"]["message"]

    def test_tool_call_unknown_name_is_a_safe_json_rpc_error(self) -> None:
        response = _ready_server().handle_request(
            {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {"name": "does_not_exist", "arguments": {}},
            }
        )
        assert response["error"]["code"] == -32602

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
        assert response["error"]["code"] == -32602

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
        tool_names = {tool["name"] for tool in tools}
        assert {
            "lucas",
            "fibonacci",
            "cassini",
            "zeckendorf",
            "ladder_verify",
            "ladder_capacity",
            "largest_feasible_tile",
            "sha256d_verify",
            "scale_intelligence",
        } <= tool_names

        res = client.call_tool("zeckendorf", {"n": 1364})
        assert res["valid"] is True
        assert res["non_adjacency"] is True
        res["valid"] = False

        signing_key = client._session_secret
        pack = client.end_session()
        assert client.session is None
        assert pack["sovereignty"] == "HYBA_SOVEREIGN_CNS"
        assert pack["narrow_ai_credit"] == "NONE_FORBIDDEN"
        assert pack["evidence_digest"] is not None
        assert pack["evidence_entries"] == 2
        assert pack["evidence"][-1]["output"]["n"] == 1364
        assert pack["evidence"][-1]["output"]["valid"] is True
        assert pack["evidence_signature"] is not None
        assert client._session_secret is None
        assert verify_evidence_pack(pack, signing_key, expected_session_id=session.session_id)

        next_session = client.start_session()
        assert next_session.session_id != session.session_id
        client.end_session()

    def test_client_with_injected_server_requires_new_connection_after_end(self) -> None:
        client = HybaMCPClient(server=HybaMCPServer())
        client.start_session()
        client.end_session()
        with pytest.raises(RuntimeError, match="already initialized"):
            client.start_session()


@pytest.mark.parametrize("name", ["lucas", "fibonacci", "cassini", "zeckendorf"])
@pytest.mark.parametrize("n", [-1, MAX_N + 1, 1.5, "15", True, None, [], {}])
def test_sequence_inputs_rejected_before_kernel(name, n, monkeypatch):
    def forbidden(*args):
        pytest.fail("invalid inputs must not reach arithmetic")

    monkeypatch.setattr(server_module, "lucas", forbidden)
    monkeypatch.setattr(server_module, "fibonacci", forbidden)
    response = _ready_server().handle_request(
        {
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {"name": name, "arguments": {"n": n}},
        }
    )
    assert response["id"] == 42
    assert response["error"]["code"] == -32602
    assert "n must be" in response["error"]["message"]


@pytest.mark.parametrize("name", ["lucas", "fibonacci", "cassini", "zeckendorf"])
@pytest.mark.parametrize("n", [0, MAX_N])
def test_sequence_bounds_are_inclusive(name, n):
    result = HybaMCPServer().execute_tool(name, {"n": n})
    assert result
    assert result["theorem_proven"] is False
    json.dumps(result)
    assert TOOLS[name]["inputSchema"]["properties"]["n"]["maximum"] == MAX_N
    if "cassini_holds" in result:
        assert result["cassini_holds"] is True
    if name == "zeckendorf":
        assert result["valid"] is True


@pytest.mark.parametrize("arguments", [{}, None, [], False])
def test_missing_or_malformed_arguments(arguments):
    response = _ready_server().handle_request(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "lucas", "arguments": arguments},
        }
    )
    assert response["id"] == 7
    assert response["error"]["code"] == -32602


@pytest.mark.parametrize(
    "arguments",
    [
        {"target_rung": 11},
        {"target_rung": True},
        {"step_direction": "sideways"},
        {"complexity": -0.01},
        {"complexity": 1.01},
        {"complexity": float("nan")},
        {"complexity": float("inf")},
        {"complexity": "0.5"},
        {"complexity": True},
        {"task_type": 10},
    ],
)
def test_scaler_rejects_invalid_arguments(arguments):
    with pytest.raises(ValueError):
        HybaMCPServer().execute_tool("scale_intelligence", arguments)


@pytest.mark.parametrize(
    ("complexity", "rung"),
    [(0, 10), (0.15, 12), (0.35, 15), (0.55, 18), (0.75, 20), (0.90, 31), (1, 31)],
)
def test_scaler_complexity_thresholds(complexity, rung):
    result = HybaMCPServer().execute_tool("scale_intelligence", {"complexity": complexity})
    assert result["current_scale"] == rung
    assert result["cassini"]["cassini_holds"] is True


@pytest.mark.parametrize(
    ("arguments", "rung"),
    [
        ({}, 31),
        ({"task_type": "unknown"}, 31),
        ({"task_type": "FAST PING CHAT"}, 10),
        ({"task_type": "chat enterprise"}, 31),
        ({"task_type": "chat", "complexity": 0.8}, 20),
        ({"target_rung": 15, "step_direction": "up", "complexity": 0}, 18),
        ({"target_rung": 15, "step_direction": "hold", "complexity": 1}, 15),
        ({"target_rung": 10, "step_direction": "down"}, 10),
        ({"target_rung": 31, "step_direction": "up"}, 31),
    ],
)
def test_scaler_precedence_and_endpoints(arguments, rung):
    assert HybaMCPServer().execute_tool("scale_intelligence", arguments)["current_scale"] == rung


def test_missing_scaler_fails_closed_but_exact_tools_work(monkeypatch):
    monkeypatch.setattr(server_module, "LucasIntelligenceScaler", None)
    server = _ready_server()
    result = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {"name": "scale_intelligence"},
        }
    )
    assert result["id"] == 9
    assert result["error"]["code"] == -32000
    assert "unavailable" in result["error"]["message"]
    assert server.execute_tool("fibonacci", {"n": 15})["F_n"] == 610


def test_scaler_dependency_is_detected_at_module_load():
    code = """
import builtins
original_import = builtins.__import__
def unavailable(name, *args, **kwargs):
    if name == "Intelligence.lucas_scaler":
        raise ImportError("dependency absent")
    return original_import(name, *args, **kwargs)
builtins.__import__ = unavailable
import hyba_mcp.server as server
assert server.LucasIntelligenceScaler is None
assert server.TOOLS["scale_intelligence"]["_meta"]["hyba/status"] == "unavailable"
assert server.HybaMCPServer().execute_tool("lucas", {"n": 15})["L_n"] == 1364
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "scale_intelligence unavailable" in result.stderr


def test_evidence_pack_signature_covers_actual_evidence():
    key = secrets.token_bytes(32)
    client = HybaMCPClient()
    session = client.start_session(signing_key=key)
    client.call_tool("lucas", {"n": 15})
    pack = client.produce_evidence_pack()
    assert pack["evidence"][1]["arguments"] == {"n": 15}
    assert pack["evidence"][1]["output"]["L_n"] == 1364
    assert pack["evidence_entries"] == len(pack["evidence"]) == 2
    assert client.verify_evidence_pack(pack)
    assert verify_evidence_pack(pack, key, expected_session_id=session.session_id)
    unsigned = {k: v for k, v in pack.items() if k not in ("evidence_digest", "evidence_signature")}

    def canonical(obj):
        return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )

    assert pack["evidence_digest"] == hashlib.sha256(canonical(unsigned)).hexdigest()
    unsigned["evidence_digest"] = pack["evidence_digest"]
    assert (
        pack["evidence_signature"] == hmac.new(key, canonical(unsigned), hashlib.sha256).hexdigest()
    )
    assert key.hex() not in json.dumps(pack)
    assert not verify_evidence_pack(pack, secrets.token_bytes(32))
    assert not verify_evidence_pack(pack, key, expected_session_id="other-session")
    pack["evidence"][1]["output"]["L_n"] = 0
    assert client.session.evidence[1]["output"]["L_n"] == 1364
    assert not verify_evidence_pack(pack, key)
    unsigned = {k: v for k, v in pack.items() if k not in ("evidence_digest", "evidence_signature")}
    pack["evidence_digest"] = hashlib.sha256(canonical(unsigned)).hexdigest()
    assert not verify_evidence_pack(pack, key)


@pytest.mark.parametrize(
    "field",
    [
        "evidence_signature",
        "evidence_digest",
        "signature_algorithm",
        "session_id",
        "tools_called",
        "evidence_entries",
        "theorem_proven",
        "sovereignty",
        "narrow_ai_credit",
        "timestamp",
    ],
)
def test_evidence_metadata_cannot_be_tampered_with(field):
    client = HybaMCPClient()
    client.start_session()
    pack = client.produce_evidence_pack()
    pack[field] = "tampered"
    assert not client.verify_evidence_pack(pack)


@pytest.mark.parametrize(
    "pack",
    [{}, None, {"evidence_digest": "x"}, {"evidence_signature": None, "evidence_digest": "x"}],
)
def test_unsigned_or_malformed_packs_fail_closed(pack):
    assert not verify_evidence_pack(pack, secrets.token_bytes(32))


def test_session_randomness_and_key_lifecycle(monkeypatch):
    monkeypatch.setattr("hyba_mcp.client.time.time", lambda: 0)
    client = HybaMCPClient()
    first = client.start_session()
    first_key = client._session_secret
    assert len(first.session_id) == 32
    assert len(bytes.fromhex(first.session_id)) == 16
    with pytest.raises(RuntimeError, match="already active"):
        client.start_session()
    pack = client.end_session()
    assert verify_evidence_pack(pack, first_key)
    assert client._session_secret is None
    assert not client.verify_evidence_pack(pack)
    second = client.start_session()
    assert second.session_id != first.session_id
    assert client._session_secret != first_key
    assert not client.verify_evidence_pack(pack)


@pytest.mark.parametrize("key", [b"", b"short", "not-bytes", bytearray(32)])
def test_invalid_signing_keys_rejected(key):
    client = HybaMCPClient()
    with pytest.raises(ValueError, match="at least 32 bytes"):
        client.start_session(signing_key=key)
    assert client.session is None
    assert client._session_secret is None
    assert not verify_evidence_pack({}, key)


def test_session_key_released_if_pack_generation_fails(monkeypatch):
    client = HybaMCPClient()
    client.start_session()
    monkeypatch.setattr("hyba_mcp.client.time.time", lambda: float("nan"))
    with pytest.raises(ValueError):
        client.end_session()
    assert client.session is None
    assert client._session_secret is None


def test_failed_handshake_does_not_create_session():
    class FailedServer:
        def handle_request(self, request):
            return {"error": {"code": -32000}}

    client = HybaMCPClient(server=FailedServer())
    with pytest.raises(RuntimeError, match="initialization failed"):
        client.start_session()
    assert client.session is None
    assert client._session_secret is None


def test_recorded_evidence_is_not_mutated_by_tool_caller():
    client = HybaMCPClient()
    client.start_session()
    arguments = {"n": 15}
    result = client.call_tool("lucas", arguments)
    arguments["n"] = 20
    result["L_n"] = 0
    pack = client.produce_evidence_pack()
    assert pack["evidence"][1]["arguments"] == {"n": 15}
    assert pack["evidence"][1]["output"]["L_n"] == 1364
    assert client.verify_evidence_pack(pack)


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("largest_feasible_tile", {"max_size": 64, "alignment": 0}),
        ("largest_feasible_tile", {"max_size": -1}),
        ("ladder_capacity", {"bound": False}),
        ("sha256d_verify", {"payload_hex": 15}),
        ("sha256d_verify", {"payload_hex": "not-hex"}),
    ],
)
def test_other_tool_contracts_fail_closed(name, arguments):
    with pytest.raises(ValueError):
        HybaMCPServer().execute_tool(name, arguments)


def test_documentation_and_manifest_cover_registered_tools():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README_MCP.md").read_text()
    assert all(f"`{name}`" in readme for name in TOOLS)
    manifest = json.loads((root / ".mcp.json").read_text())
    statuses = {entry["name"]: entry["status"] for entry in manifest["servers"]}
    assert statuses == {
        "hyba-mcp": "production",
        "exact-kernel": "stable-standalone",
        "cogito": "experimental",
    }
