"""Commercial LLM Gateway Package.

Bridges frontend clients to the EUCLID intelligence organism with
AL HARAS security, PYTHIA retrieval, and SALAMANDER self-healing.
"""

from .gateway import GatewayRequest, GatewayResponse, LLMGateway
from .gateway_config import LLMGatewayConfig
from .capability import CAPABILITY, llm_gateway_entry

__all__ = [
    "LLMGateway",
    "GatewayRequest",
    "GatewayResponse",
    "LLMGatewayConfig",
    "CAPABILITY",
    "llm_gateway_entry",
]
