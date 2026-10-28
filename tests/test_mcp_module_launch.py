"""MCP registrations launch servers through importable module paths."""

import json
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("name", "module"),
    [
        ("hyba-mcp", "hyba_mcp.server"),
        ("cogito", "mcp.cogito.server"),
    ],
)
def test_native_server_uses_python_module_form(name, module):
    config_path = Path(__file__).parents[1] / ".mcp.json"
    servers = json.loads(config_path.read_text(encoding="utf-8"))["servers"]
    server = next(server for server in servers if server["name"] == name)

    assert server["command"] == "python3"
    assert server["args"] == ["-m", module]
