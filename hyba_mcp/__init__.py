"""Experiment MCP surface for the pure-Python TURING library.

This package is the first-principles wrapper moved onto the HYBA MCP stdio
protocol used by ``hyba_mcp`` on ``import/phienterprise-20261111``. It depends
on ``packages/turing`` and never the reverse. It does not parse QASM, load a
vendor SDK, or submit work to hardware.
"""

from .adapter import TuringAdapter
from .client import HybaMCPClient, connect
from .server import PROTOCOL_VERSION, HybaMCPServer, TuringMCPServer

__all__ = [
    "PROTOCOL_VERSION",
    "HybaMCPClient",
    "HybaMCPServer",
    "TuringAdapter",
    "TuringMCPServer",
    "connect",
]
__version__ = "0.1.0"
