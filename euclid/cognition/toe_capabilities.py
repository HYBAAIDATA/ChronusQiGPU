"""EUCLID → TOE capability calls.

EUCLID orchestrates: it decides *when* to ask TOE something and what to do
with the answer. TOE answers with evidence-bearing results and never acts.
This adapter is the clean call surface between the two:

    represent · model · identify · intervene · counterfactual ·
    evaluate_futures · uncertainty · plan · request_information ·
    explain · revise · run

Every invocation is appended to EUCLID's own evidence chain (capability,
problem digest, result digest) so EUCLID's record shows exactly which TOE
answers its decisions consumed. Calls go through the TOE composition root
(``TOEIntelligenceRuntime``) under EUCLID's tenant, so EUCLID's learned TOE
state is isolated from every other tenant's.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

CAPABILITIES = (
    "represent",
    "model",
    "identify",
    "intervene",
    "counterfactual",
    "evaluate_futures",
    "uncertainty",
    "plan",
    "request_information",
    "explain",
    "revise",
    "run",
)


def _digest(value: Any) -> str:
    blob = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class TOECapabilityAdapter:
    """EUCLID's handle on the whole TOE capability surface."""

    def __init__(
        self,
        *,
        runtime: Any = None,
        evidence: Any = None,
        tenant_id: str = "euclid",
    ) -> None:
        from toe.runtime import TenantContext, TOEIntelligenceRuntime, TOEIntelligenceRuntimeConfig

        self.runtime = runtime or TOEIntelligenceRuntime(
            TOEIntelligenceRuntimeConfig(
                enable_feedback=False, enable_asi=False, enable_platform=False
            )
        )
        self.tenant = TenantContext(tenant_id)
        self.evidence = evidence
        self.calls: list[Dict[str, str]] = []

    @property
    def machine(self) -> Any:
        return self.runtime.machine_for(self.tenant)

    def capabilities(self) -> Dict[str, str]:
        return self.machine.capabilities()

    def invoke(self, capability: str, problem: Any, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Ask TOE one question. EUCLID chose to ask; TOE only answers."""
        if capability not in CAPABILITIES:
            raise ValueError(f"unknown TOE capability {capability!r}")
        if isinstance(problem, dict) and capability != "revise":
            from toe.machine import problem_from_content

            problem = problem_from_content(problem.get("domain", "cogito"), problem)
        if capability == "run":
            response = self.runtime.solve(problem, self.tenant)
            result: Dict[str, Any] = (
                response.result if response.ok else {"error": response.error.as_dict()}
            )
        elif capability == "revise":
            response = self.runtime.learn(
                problem.get("episode_sha256", "") if isinstance(problem, dict) else problem,
                args[0] if args else kwargs["observed"],
                self.tenant,
            )
            result = response.result if response.ok else {"error": response.error.as_dict()}
        else:
            method = getattr(self.machine, capability)
            out = method(problem, *args, **kwargs)
            result = out if isinstance(out, dict) else {"result": out}
            if capability == "represent":
                result = {**result, "_state": result["_state"].as_dict()}
        record = {
            "capability": capability,
            "problem_digest": problem.digest() if hasattr(problem, "digest") else _digest(problem),
            "result_digest": _digest(result),
            "authority": "EUCLID invoked; TOE answered with evidence; no action taken by TOE",
        }
        self.calls.append(record)
        if self.evidence is not None:
            self.evidence.append("toe-capability", record)
        return {"capability": capability, "result": result, "evidence": record}


__all__ = ["CAPABILITIES", "TOECapabilityAdapter"]
