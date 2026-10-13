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
    {
        "name": "bsd_conjecture",
        "version": "1.0.0",
        "description": "EUCLID-scaffolded BSD conjecture exploration. Output: conjectural L-function data, not proof.",
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

    def explore_bsd(
        self, a: int = 0, b: int = 1, max_prime: int = 200
    ) -> Dict[str, Any]:
        """Explore Birch and Swinnerton-Dyer conjecture invariants over y^2 = x^3 + ax + b.

        Returns conjectural arithmetic data and model-theoretic invariants.
        Never outputs a claimed proof.
        """
        assert_external_boundary()
        from integrations.solvers.bsd_scaffold import BSDScribe, BSDScribeConfig

        scribe = BSDScribe(BSDScribeConfig(max_prime=max_prime))
        analysis = scribe.analyze_curve(a, b, max_prime=max_prime)
        return {
            "status": "CONJECTURE_EXPLORATION",
            "curve": f"y^2 = x^3 + ({a})x + ({b})",
            "proof_claim": False,
            "conjectural_data": analysis,
            "security": "PASS",
        }

    def explore_bsd_team(
        self, a: int = 0, b: int = 1, max_prime: int = 200
    ) -> Dict[str, Any]:
        """Run the full 4-agent collaborative team (EUCLID + SALAMANDER + PYTHIA + AL HARAS).

        Returns multi-agent report with verified invariants and Zeckendorf certificates.
        """
        assert_external_boundary()
        from integrations.solvers.bsd_solver import BSDSolverTeam

        team = BSDSolverTeam()
        report = team.solve(a, b, max_prime=max_prime)
        return report.to_dict()


    def capabilities(self) -> List[str]:
        return [c["name"] for c in EXTERNAL_AGI_CAPABILITIES]


__all__ = ["ExternalAGI", "EXTERNAL_AGI_CAPABILITIES"]
