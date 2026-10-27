"""HYBA Sovereign Model Context Protocol (MCP) Gateway & Exact-Kernel Suite.

HYBA MCP provides a sovereign, contract-bound tools and exact-kernel gateway.
It does NOT serve or augment narrow AI models. Narrow AI systems receive zero
credit, zero authority, and zero decision rights. HYBA adapts environments,
tools, and curricula under strict AL HARAS zero-trust containment.
"""

from __future__ import annotations

from .server import HybaMCPServer, run_server
from .client import HybaMCPClient
from .control_plane import ControlPlane, SandboxConfig

__version__ = "2.0.0"
__all__ = ["HybaMCPServer", "HybaMCPClient", "ControlPlane", "SandboxConfig", "run_server"]
