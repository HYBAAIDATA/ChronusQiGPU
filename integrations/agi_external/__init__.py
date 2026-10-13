"""External AGI surface.

Offered to clients. Contract-bound, ledgered, and gated by AL HARAS.
ASI internals are withheld by an import-time boundary check.
"""

from __future__ import annotations

from typing import Any, Dict, List

from integrations.llm_gateway import LLMGateway, GatewayRequest, CAPABILITY as GATEWAY_CAP
from integrations.agi_external.boundary import assert_external_boundary

EXTERNAL_AGI_CAPABILITIES: List[Dict[str, Any]] = [
    GATEWAY_CAP,
    {
        "name": "reasoning",
        "version": "1.0.0",
        "description": "Contract-bound reasoning over client context via the commercial gateway",
        "source": "external_agi",
    },
    {
        "name": "retrieval",
        "version": "1.0.0",
        "description": "PYTHIA-backed retrieval, results sanitized by AL HARAS",
        "source": "external_agi",
    },
    {
        "name": "structured_output",
        "version": "1.0.0",
        "description": "Schema-validated structured extraction for commercial consumers",
        "source": "external_agi",
    },
]


class ExternalAGI:
    """Client-facing AGI. Boundary checked on every call."""

    def __init__(self) -> None:
        assert_external_boundary()
        self.gateway = LLMGateway()

    def reason(self, prompt: str, client_id: str = "external") -> Dict[str, Any]:
        assert_external_boundary()
        req = GatewayRequest(prompt=prompt, client_id=client_id, rag_enabled=True, cache_enabled=True)
        resp = self.gateway.process(req)
        return {
            "status": resp.status,
            "output": resp.output_text,
            "security": resp.security_verdict,
            "cached": resp.cached,
            "latency_ms": resp.latency_ms,
        }

    def capabilities(self) -> List[str]:
        return [c["name"] for c in EXTERNAL_AGI_CAPABILITIES]


__all__ = ["ExternalAGI", "EXTERNAL_AGI_CAPABILITIES"]
