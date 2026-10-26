"""HYBA Sovereign Model Context Protocol (MCP) Gateway & Exact-Kernel Suite.

HYBA MCP provides a sovereign, contract-bound tools and exact-kernel gateway.
It does NOT serve or augment narrow AI models. Narrow AI systems receive zero
credit, zero authority, and zero decision rights. HYBA adapts environments,
tools, and curricula under strict AL HARAS zero-trust containment.
"""

from __future__ import annotations

from .server import HybaMCPServer, run_server
from .client import HybaMCPClient

__version__ = "1.0.0"
__all__ = ["HybaMCPServer", "HybaMCPClient", "run_server"]
