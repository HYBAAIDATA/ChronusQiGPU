"""Regression coverage for Cogito's initialize and stateless MCP surface."""

import hashlib
import io
import json

import pytest

from mcp.cogito import server
from toe.problem import Problem


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


@pytest.mark.parametrize("capability", server.CAPABILITIES)
def test_capabilities_accept_empty_json_problem(cogito_request, capability):
    extra = {
        "intervene": {"action": {}},
        "counterfactual": {"action": {}, "outcomes": []},
        "revise": {"observed": {}},
    }.get(capability, {})
    response = cogito_request(
        "tools/call",
        {"name": capability, "arguments": {"problem": {}, "args": extra}},
    )
    assert "error" not in response
    envelope = json.loads(response["result"]["content"][0]["text"])
    assert envelope["capability"] == capability
    assert envelope["truth_class"] in {"ACT", "ACQUIRE_EVIDENCE", "REFUSED"}
    assert envelope["theorem_proven"] is False
    assert len(envelope["evidence"]["problem_digest"]) == 64
    assert len(envelope["evidence"]["result_digest"]) == 64
    result_json = json.dumps(envelope["result"], sort_keys=True, separators=(",", ":"))
    assert envelope["evidence"]["result_digest"] == hashlib.sha256(result_json.encode()).hexdigest()
    if capability == "represent":
        assert envelope["truth_class"] in {"ACT", "ACQUIRE_EVIDENCE"}
    if capability == "revise":
        assert envelope["truth_class"] == "REFUSED"
        assert envelope["result"]["error"]["code"] == "unknown_episode"


def test_represent_json_problem_preserves_identity(cogito_request):
    problem = Problem(domain="test.json", observation=[1, 2, 3])
    response = cogito_request(
        "tools/call",
        {
            "name": "represent",
            "arguments": {"problem": {"domain": problem.domain, **problem.content()}},
        },
    )
    assert "error" not in response
    envelope = json.loads(response["result"]["content"][0]["text"])
    assert envelope["evidence"]["problem_digest"] == problem.digest()
    assert (
        envelope["result"]["_state"]["observation_sha256"]
        == envelope["result"]["observation_sha256"]
    )
