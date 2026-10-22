"""
HYBA_DATA Python SDK — Programmatic access to the optimization framework.

Usage (direct, no API server needed):
    from hyba_data.sdk import HybaDataClient
    client = HybaDataClient()
    result = client.optimize(manifold_type="m32", oracle_type="phi_resonance")

Usage (remote API):
    client = HybaDataClient(base_url="http://localhost:8080")
    result = client.optimize(manifold_type="m32", oracle_type="phi_resonance")
"""
from .client import HybaDataClient

__all__ = ["HybaDataClient"]
