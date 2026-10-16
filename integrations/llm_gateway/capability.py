"""Capability registration for the commercial LLM Gateway.

Makes the gateway visible to the Euclid/Salamander intelligence surface.
Registration is a ledgered push; the capability is shared via entanglement.
"""

from __future__ import annotations

from typing import Any, Dict

from integrations.llm_gateway.gateway import GatewayRequest, LLMGateway


def llm_gateway_entry(prompt: str, client_id: str = "default_client", **kwargs: Any) -> Dict[str, Any]:
    """Entry point invoked by the intelligence once-over or external callers."""
    gw = LLMGateway()
    req = GatewayRequest(prompt=prompt, client_id=client_id, **kwargs)
    resp = gw.process(req)
    return {
        "status": resp.status,
        "output_text": resp.output_text,
        "security_verdict": resp.security_verdict,
        "cached": resp.cached,
        "latency_ms": resp.latency_ms,
        "request_id": resp.request_id,
    }


CAPABILITY = {
    "name": "llm_gateway",
    "version": "1.0.0",
    "description": "Commercial LLM gateway bridging frontend clients to AL HARAS, PYTHIA, EUCLID, and SALAMANDER",
    "entry": llm_gateway_entry,
    "source": "integrations/llm_gateway",
}
