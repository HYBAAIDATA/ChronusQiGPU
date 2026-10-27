"""Regression coverage for Cogito's initialize and stateless MCP surface."""

import io
import json

import pytest

from mcp.cogito import server


@pytest.fixture
def cogito_request(monkeypatch, capsys):
    def send(method, params=None):
        payload = {"jsonrpc": "2.0", "id": 42, "method": method, "params": params or {}}
        monkeypatch.setattr(server.sys, "stdin", io.StringIO(json.dumps(payload) + "\n"))
        server.main()
        response = json.loads(capsys.readouterr().out)
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 42
        return response

    return send


def test_initialize(cogito_request):
    response = cogito_request(
        "initialize",
        {
            "protocolVersion": "2026-07-28",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    )
    assert response["result"] == {
        "protocolVersion": "2026-07-28",
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": "cogito", "version": "0.1.0"},
    }
    assert response["_meta"] == {
        "io.modelcontextprotocol/serverInfo": {"name": "cogito", "version": "0.1.0"}
    }


def test_discover_remains_compatible(cogito_request):
    assert cogito_request("server/discover")["result"] == {
        "protocolVersions": ["2026-07-28"],
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": "cogito", "version": "0.1.0"},
    }


@pytest.mark.parametrize("with_meta", [False, True])
def test_tools_list_is_stateless_and_has_twelve_capabilities(cogito_request, with_meta):
    params = (
        {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}} if with_meta else {}
    )
    tools = cogito_request("tools/list", params)["result"]["tools"]
    assert len(tools) == 12
    assert {tool["name"] for tool in tools} == {
        "represent",
        "model",
        "identify",
        "intervene",
        "counterfactual",
        "evaluate_futures",
        "uncertainty",
        "plan",
        "request_information",
        "explain",
        "revise",
        "run",
    }


@pytest.mark.parametrize("method", ["initialize", "server/discover", "tools/list", "tools/call"])
def test_unsupported_meta_version_is_rejected(cogito_request, method):
    response = cogito_request(
        method, {"_meta": {"io.modelcontextprotocol/protocolVersion": "2024-11-05"}}
    )
    assert "result" not in response
    assert response["error"] == {
        "code": -32022,
        "message": "Unsupported protocol version",
        "data": {"supported": ["2026-07-28"], "requested": "2024-11-05"},
    }


def test_unknown_capability_returns_error(cogito_request):
    response = cogito_request("tools/call", {"name": "unknown", "arguments": {"problem": {}}})
    assert "result" not in response
    assert response["error"] == {"code": -32000, "message": "unknown capability unknown"}


def test_unknown_capability_raises():
    with pytest.raises(ValueError, match="unknown TOE capability 'unknown'"):
        server.TOECapabilityAdapter().invoke("unknown", {})
