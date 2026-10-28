"""Focused tests for the read-only HYBA repository context tools."""

import json
import hashlib

import pytest

import hyba_mcp.hyba_context as context_tools
from hyba_mcp.server import HybaMCPServer, TOOLS


def test_context_ranks_previews_and_digest_deterministically(tmp_path, monkeypatch):
    (tmp_path / "alpha.txt").write_text("lucas lucas context", encoding="utf-8")
    (tmp_path / "beta.txt").write_text("context only", encoding="utf-8")
    skipped = tmp_path / "node_modules"
    skipped.mkdir()
    (skipped / "hidden.txt").write_text("lucas lucas lucas", encoding="utf-8")
    monkeypatch.setattr(context_tools, "REPO_ROOT", str(tmp_path))

    result = context_tools.hyba_context("lucas context", max_files=2, max_chars_per_file=50)
    repeated = context_tools.hyba_context("lucas context", max_files=2, max_chars_per_file=50)

    assert [item["path"] for item in result["files"]] == ["alpha.txt", "beta.txt"]
    assert result["files"][0]["score"] > result["files"][1]["score"]
    assert result["evidence_digest"] == repeated["evidence_digest"]
    assert result["theorem_proven"] is False
    assert result["sovereignty"] == "HYBA_SOVEREIGN_CNS"
    assert result["budget"]["within_limit"]
    assert result["budget"]["effective_bytes"] == result["budget"]["indexed_bytes"]
    assert result["source_scope"] == "current_repository"
    short_preview = context_tools.hyba_context("only", max_files=1, max_chars_per_file=1)
    assert len(short_preview["files"][0]["preview"]) <= 1


def test_context_snaps_budget_without_exceeding_requested_or_tier_limit():
    budget = context_tools.resolve_context_budget("T0", 128 * 1024)
    assert budget["requested_bytes"] == 128 * 1024
    assert budget["effective_limit_bytes"] == 131070
    assert budget["effective_limit_bytes"] <= budget["requested_bytes"]

    with pytest.raises(ValueError, match="budget_bytes"):
        context_tools.resolve_context_budget("T0", 1_000_000)


def test_context_tiles_are_budgeted_digest_bound_and_resumable(tmp_path, monkeypatch):
    first_tile = b"lucas" + b"a" * (context_tools.CONTEXT_TILE_BYTES - 5)
    (tmp_path / "alpha.txt").write_bytes(first_tile + b"x" * context_tools.CONTEXT_TILE_BYTES)
    (tmp_path / "beta.txt").write_bytes(b"lucas beta")
    monkeypatch.setattr(context_tools, "REPO_ROOT", str(tmp_path))

    first = context_tools.hyba_context("lucas", max_files=1, budget_bytes=20_000, tier="T1")
    second = context_tools.hyba_context(
        "lucas",
        max_files=1,
        budget_bytes=20_000,
        tier="T1",
        cursor=first["page"]["next_cursor"],
    )

    assert first["files"][0]["path"] == "alpha.txt"
    assert first["files"][0]["sha256"] == hashlib.sha256(first_tile).hexdigest()
    assert first["budget"]["effective_bytes"] == context_tools.CONTEXT_TILE_BYTES
    assert first["budget"]["effective_bytes"] <= first["budget"]["effective_limit_bytes"]
    assert sum(tile["bytes"] for tile in first["tiles"]) == first["budget"]["effective_bytes"]
    serialized_tiles = b"".join(
        json.dumps(tile, sort_keys=True, separators=(",", ":")).encode("utf-8")
        for tile in first["tiles"]
    )
    assert hashlib.sha256(serialized_tiles).hexdigest() == first["budget"]["index_digest"]
    assert first["page"]["has_more"]
    assert second["files"][0]["path"] == "beta.txt"
    assert second["page"]["has_more"] is False
    assert second["budget"]["within_limit"]
    assert (
        context_tools._evidence_digest(
            {key: value for key, value in first.items() if key != "evidence_digest"}
        )
        == first["evidence_digest"]
    )

    with pytest.raises(ValueError, match="cursor"):
        context_tools.hyba_context("different query", cursor=first["page"]["next_cursor"])


def test_verify_requires_an_exact_byte_match_and_reports_line(tmp_path, monkeypatch):
    (tmp_path / "evidence.txt").write_bytes(b"first line\nExact phrase.\n")
    monkeypatch.setattr(context_tools, "REPO_ROOT", str(tmp_path))

    found = context_tools.hyba_verify("claim", ["evidence.txt"], "Exact phrase.")
    absent = context_tools.hyba_verify("claim", ["evidence.txt"], "exact phrase.")

    assert found["supported"] is True
    assert found["status"] == "supported"
    assert found["matches"] == [{"path": "evidence.txt", "line": 2}]
    assert absent["supported"] is False
    assert absent["status"] == "not_found"
    assert absent["matches"] == []


def test_verify_rejects_paths_outside_repository(tmp_path, monkeypatch):
    (tmp_path / "evidence.txt").write_text("exact phrase", encoding="utf-8")
    monkeypatch.setattr(context_tools, "REPO_ROOT", str(tmp_path))

    result = context_tools.hyba_verify("claim", ["../evidence.txt", "evidence.txt"], "exact phrase")

    assert result["supported"] is True
    assert result["matches"] == [{"path": "evidence.txt", "line": 1}]
    assert context_tools._safe_join(str(tmp_path), "../evidence.txt") is None


def test_server_registers_and_executes_both_tools(tmp_path, monkeypatch):
    (tmp_path / "context.txt").write_text("TOOLS_PATCH context", encoding="utf-8")
    monkeypatch.setattr(context_tools, "REPO_ROOT", str(tmp_path))
    server = HybaMCPServer()
    server.handle_request(
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
    server.handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"})
    listing = server.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    )
    names = {tool["name"] for tool in listing["result"]["tools"]}
    assert {"hyba_context", "hyba_verify"} <= set(TOOLS)
    assert {"hyba_context", "hyba_verify"} <= names
    assert len(names) == 16

    context_response = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "hyba_context", "arguments": {"query": "TOOLS_PATCH"}},
        }
    )
    context_result = json.loads(context_response["result"]["content"][0]["text"])
    assert context_result["files"]
    assert context_result["theorem_proven"] is False


def test_server_enforces_context_tier_budget_through_control_plane():
    server = HybaMCPServer()
    with pytest.raises(ValueError, match="budget_bytes"):
        server.execute_tool("hyba_context", {"query": "lucas", "budget_bytes": 1_000_000})
