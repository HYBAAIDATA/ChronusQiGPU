"""Focused tests for the read-only HYBA repository context tools."""

import hashlib
import json

import hyba_mcp.hyba_context as context_tools
import pytest
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
    assert result["advisory_only"] is True
    assert result["theorem_proven"] is False
    assert result["sovereignty"] == "HYBA_SOVEREIGN_CNS"
    short_preview = context_tools.hyba_context("only", max_files=1, max_chars_per_file=1)
    assert len(short_preview["files"][0]["preview"]) <= 1
    assert short_preview["budget"] == 10_000_000
    assert short_preview["tile_size"] == 8_388_608


def test_context_budget_tiles_and_pages_are_deterministic(tmp_path, monkeypatch):
    alpha = tmp_path / "alpha.txt"
    beta = tmp_path / "beta.txt"
    alpha.write_text("context alpha", encoding="utf-8")
    beta.write_text("context beta", encoding="utf-8")
    monkeypatch.setattr(context_tools, "REPO_ROOT", str(tmp_path))

    first_page = context_tools.hyba_context("context", max_files=1, budget=4096, page=0)
    second_page = context_tools.hyba_context("context", max_files=1, budget=4096, page=1)
    repeated = context_tools.hyba_context("context", max_files=1, budget=4096, page=0)

    assert [item["path"] for item in first_page["files"]] == ["alpha.txt"]
    assert [item["path"] for item in second_page["files"]] == ["beta.txt"]
    assert first_page["page_count"] == 2
    assert first_page["has_more"] is True
    assert second_page["has_more"] is False
    assert first_page["budget_used"] <= first_page["effective_budget"] <= 4096
    assert sum(tile["bytes"] for tile in first_page["tiles"]) == first_page["budget_used"]
    stream = b"".join(
        len(path).to_bytes(8, "big") + path + content
        for path, content in (
            (b"alpha.txt", b"context alpha"),
            (b"beta.txt", b"context beta"),
        )
    )
    assert first_page["tiles"] == [
        {
            "index": 0,
            "fold_indices": [2],
            "bytes": len(stream),
            "digest": hashlib.sha256(stream).hexdigest(),
        }
    ]
    assert first_page["tiles"] == second_page["tiles"] == repeated["tiles"]
    assert first_page["evidence_digest"] == repeated["evidence_digest"]
    assert first_page["advisory_only"] is True
    assert first_page["theorem_proven"] is False
    assert alpha.read_text(encoding="utf-8") == "context alpha"
    assert beta.read_text(encoding="utf-8") == "context beta"


def test_context_budget_is_finite_and_marks_partial_index(tmp_path, monkeypatch):
    source = tmp_path / "large.txt"
    source.write_text("context " * 20, encoding="utf-8")
    monkeypatch.setattr(context_tools, "REPO_ROOT", str(tmp_path))

    result = context_tools.hyba_context("context", budget=32)

    assert result["budget_used"] <= result["effective_budget"] <= 32
    assert result["index_complete"] is False
    assert result["index_status"] == "UNSEEN"
    assert sum(tile["bytes"] for tile in result["tiles"]) == result["budget_used"]
    assert source.read_text(encoding="utf-8") == "context " * 20

    for invalid_budget in (True, 0, 10_000_001):
        with pytest.raises(ValueError):
            context_tools.hyba_context("context", budget=invalid_budget)


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
    (tmp_path / "context.txt").write_text("TOOLS_PATCH is registered", encoding="utf-8")
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
    context_schema = next(
        tool["inputSchema"] for tool in listing["result"]["tools"] if tool["name"] == "hyba_context"
    )
    assert context_schema["properties"]["budget"]["default"] == 10_000_000
    assert context_schema["properties"]["page"]["default"] == 0

    context_response = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "hyba_context",
                "arguments": {"query": "TOOLS_PATCH", "budget": 4096, "page": 0},
            },
        }
    )
    context_result = json.loads(context_response["result"]["content"][0]["text"])
    assert context_result["files"]
    assert context_result["theorem_proven"] is False
