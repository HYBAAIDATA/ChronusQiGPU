"""Focused tests for the read-only HYBA repository context tools."""

import json

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
    short_preview = context_tools.hyba_context("only", max_files=1, max_chars_per_file=1)
    assert len(short_preview["files"][0]["preview"]) <= 1


def test_verify_requires_an_exact_byte_match_and_reports_line(tmp_path, monkeypatch):
    (tmp_path / "evidence.txt").write_bytes(b"first line\nExact phrase.\n")
    monkeypatch.setattr(context_tools, "REPO_ROOT", str(tmp_path))

    found = context_tools.hyba_verify(
        "claim", ["evidence.txt"], "Exact phrase."
    )
    absent = context_tools.hyba_verify(
        "claim", ["evidence.txt"], "exact phrase."
    )

    assert found["supported"] is True
    assert found["status"] == "supported"
    assert found["matches"] == [{"path": "evidence.txt", "line": 2}]
    assert absent["supported"] is False
    assert absent["status"] == "not_found"
    assert absent["matches"] == []


def test_verify_rejects_paths_outside_repository(tmp_path, monkeypatch):
    (tmp_path / "evidence.txt").write_text("exact phrase", encoding="utf-8")
    monkeypatch.setattr(context_tools, "REPO_ROOT", str(tmp_path))

    result = context_tools.hyba_verify(
        "claim", ["../evidence.txt", "evidence.txt"], "exact phrase"
    )

    assert result["supported"] is True
    assert result["matches"] == [{"path": "evidence.txt", "line": 1}]
    assert context_tools._safe_join(str(tmp_path), "../evidence.txt") is None


def test_server_registers_and_executes_both_tools():
    server = HybaMCPServer()
    listing = server.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    )
    assert len(listing["result"]["tools"]) == 11
    assert {"hyba_context", "hyba_verify"} <= set(TOOLS)

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
