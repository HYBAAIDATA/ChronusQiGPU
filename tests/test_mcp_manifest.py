"""Contract tests for the root MCP server registrations."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hyba_and_cogito_use_module_form_launches():
    manifest = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    servers = {server["name"]: server for server in manifest["servers"]}

    assert servers["hyba-mcp"]["args"] == ["-m", "hyba_mcp.server"]
    assert servers["cogito"]["args"] == ["-m", "mcp.cogito.server"]
    assert servers["cogito"]["status"] == "production"
    assert "12 EUCLID/TOE capabilities" in servers["cogito"]["description"]
