"""Commercial Enterprise LLM Gateway Integration.

Provides a unified gateway interface connecting frontend clients and external
services to the EUCLID intelligence organism, AL HARAS security boundaries,
SALAMANDER autonomic resilience, and PYTHIA knowledge retrieval.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from euclid.commercial import (
    CommercialCoordinator,
    CommercialGuardrails,
    CommercialSelfHealingSLA,
    CommercialTeamOrchestrator,
    CommercialToolGateway,
    ContextCacheManager,
    EnterpriseRAG,
    StructuredExtractor,
)


@dataclass(frozen=True)
class GatewayRequest:
    prompt: str
    client_id: str = "default_client"
    session_id: Optional[str] = None
    structured_schema: Optional[Dict[str, Any]] = None
    tools_enabled: bool = True
    rag_enabled: bool = True
    cache_enabled: bool = True
    latency_budget_ms: float = 3000.0


@dataclass(frozen=True)
class GatewayResponse:
    request_id: str
    status: str
    output_text: str
    structured_data: Optional[Dict[str, Any]] = None
    cached: bool = False
    latency_ms: float = 0.0
    security_verdict: str = "APPROVED"
    audit_trail: Dict[str, Any] = field(default_factory=dict)


class LLMGateway:
    """Enterprise gateway bridging client interfaces to the intelligence substrate."""

    def __init__(
        self,
        *,
        guardrails: Optional[CommercialGuardrails] = None,
        sla: Optional[CommercialSelfHealingSLA] = None,
        cache: Optional[ContextCacheManager] = None,
        rag: Optional[EnterpriseRAG] = None,
        tools: Optional[CommercialToolGateway] = None,
        coordinator: Optional[CommercialCoordinator] = None,
    ) -> None:
        self.guardrails = guardrails or CommercialGuardrails()
        self.sla = sla or CommercialSelfHealingSLA()
        self.cache = cache or ContextCacheManager()
        self.rag = rag or EnterpriseRAG()
        self.tools = tools or CommercialToolGateway()
        self.coordinator = coordinator or CommercialCoordinator()
        self.extractor = StructuredExtractor()

    def process(self, request: GatewayRequest) -> GatewayResponse:
        """Process an enterprise client request through the full intelligence pipeline."""
        req_id = f"gw_{int(time.time() * 1000)}"
        t0 = time.perf_counter()

        # 1. Security Gatekeeper (AL HARAS)
        verdict = self.guardrails.inspect_request(request.prompt, client_id=request.client_id)
        if not verdict.allowed:
            elapsed = (time.perf_counter() - t0) * 1000.0
            return GatewayResponse(
                request_id=req_id,
                status="REJECTED_SECURITY",
                output_text="Request rejected by AL HARAS security policy.",
                security_verdict="DENIED",
                latency_ms=elapsed,
                audit_trail={"violations": verdict.violations},
            )

        sanitized_prompt = verdict.sanitized_content or request.prompt

        # 2. Cache Lookup (PYTHIA)
        cache_key = self.cache.compute_key(sanitized_prompt, context_prefix=request.client_id)
        if request.cache_enabled:
            cached_val = self.cache.get(cache_key)
            if cached_val is not None:
                elapsed = (time.perf_counter() - t0) * 1000.0
                return GatewayResponse(
                    request_id=req_id,
                    status="SUCCESS_CACHED",
                    output_text=cached_val if isinstance(cached_val, str) else str(cached_val),
                    cached=True,
                    latency_ms=elapsed,
                    security_verdict="APPROVED",
                )

        # 3. Knowledge Retrieval (PYTHIA RAG)
        context_chunks: List[str] = []
        if request.rag_enabled:
            retrievals = self.rag.retrieve(sanitized_prompt, top_k=3)
            context_chunks = [r.chunk.content for r in retrievals]

        # 4. Cognitive Execution with Self-Healing (EUCLID + SALAMANDER)
        def _core_execution() -> str:
            # Native cognitive synthesis
            context_block = "\n---\n".join(context_chunks) if context_chunks else ""
            if context_block:
                return f"[EUCLID Intelligence Response with Pythia Context]\n{sanitized_prompt}\nContext:\n{context_block}"
            return f"[EUCLID Intelligence Response]\n{sanitized_prompt}"

        raw_output, sla_metrics = self.sla.execute_with_self_healing(
            _core_execution,
            latency_budget_ms=request.latency_budget_ms,
        )

        # 5. Outbound Security Sanitization (AL HARAS)
        egress_verdict = self.guardrails.inspect_response(raw_output, client_id=request.client_id)
        final_output = egress_verdict.sanitized_content or raw_output

        # 6. Structured Output Extraction (EUCLID)
        structured_dict: Optional[Dict[str, Any]] = None
        if request.structured_schema:
            parsed = self.extractor.extract_json(final_output)
            if parsed:
                structured_dict = parsed

        # Store in cache
        if request.cache_enabled:
            self.cache.set(cache_key, final_output)

        elapsed = (time.perf_counter() - t0) * 1000.0
        return GatewayResponse(
            request_id=req_id,
            status="SUCCESS",
            output_text=final_output,
            structured_data=structured_dict,
            cached=False,
            latency_ms=elapsed,
            security_verdict="APPROVED",
            audit_trail={"sla": sla_metrics.status, "healed": sla_metrics.healed},
        )
