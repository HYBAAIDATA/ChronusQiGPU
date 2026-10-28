"""HYBA MCP server and in-process client public API."""

from __future__ import annotations

__version__ = "2.0.0"
__all__ = [
    "HybaMCPServer",
    "HybaMCPClient",
    "ControlPlane",
    "SandboxConfig",
    "run_server",
]


def __getattr__(name: str):
    if name in {"HybaMCPServer", "run_server"}:
        from .server import HybaMCPServer, run_server

        return {"HybaMCPServer": HybaMCPServer, "run_server": run_server}[name]
    if name == "HybaMCPClient":
        from .client import HybaMCPClient

        return HybaMCPClient
    if name in {"ControlPlane", "SandboxConfig"}:
        from .control_plane import ControlPlane, SandboxConfig

        return {"ControlPlane": ControlPlane, "SandboxConfig": SandboxConfig}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
