"""Tests for EUCLID Commercial Enterprise Intelligence Suite.

Validates that all commercial capabilities (teams, coordinator, guardrails,
self-healing, RAG, tool gateway, structured extraction, evals, cache)
execute cleanly under first-principles native logic.
"""

from __future__ import annotations

import unittest
from euclid.commercial import (
    CommercialCoordinator,
    CommercialGuardrails,
    CommercialSelfHealingSLA,
    CommercialTeamOrchestrator,
    CommercialToolGateway,
    ContextCacheManager,
    EnterpriseRAG,
    EvaluationEngine,
    StructuredExtractor,
)


class TestCommercialSuite(unittest.TestCase):
    def test_guardrails_al_haras(self) -> None:
        guard = CommercialGuardrails(max_prompt_bytes=500)
        ok_verdict = guard.inspect_request("Hello, enterprise service!")
        self.assertTrue(ok_verdict.allowed)

        bad_verdict = guard.inspect_request("eval('danger')")
        self.assertFalse(bad_verdict.allowed)
        self.assertIn("matches restricted pattern", bad_verdict.violations[0])

    def test_self_healing_salamander(self) -> None:
        sla = CommercialSelfHealingSLA(max_retries=2)
        call_count = 0

        def flaky_service() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Transient network hiccup")
            return "recovered"

        res, metrics = sla.execute_with_self_healing(flaky_service)
        self.assertEqual(res, "recovered")
        self.assertTrue(metrics.healed)
        self.assertEqual(metrics.status, "SUCCESS")

    def test_coordinator_euclid(self) -> None:
        coordinator = CommercialCoordinator()
        plan = coordinator.plan_task("Deliver financial report to enterprise client")
        self.assertEqual(len(plan.steps), 4)

        executions = coordinator.execute_plan(plan, lambda step: f"Completed: {step['name']}")
        self.assertEqual(len(executions), 4)
        self.assertTrue(all(e.success for e in executions))

    def test_team_orchestrator(self) -> None:
        orchestrator = CommercialTeamOrchestrator()
        result = orchestrator.run_collaborative_task(
            "Security and knowledge synthesis",
            execution_hooks={
                "AL_HARAS": lambda obj: "AL_HARAS: Clean",
                "PYTHIA": lambda obj: "PYTHIA: Context loaded",
                "EUCLID": lambda obj: "EUCLID: Plan compiled",
                "SALAMANDER": lambda obj: "SALAMANDER: Verified",
            },
        )
        self.assertEqual(result.verdict, "UNVERIFIED_LEGACY")
        self.assertIsNone(result.total_cost_usd)
        self.assertIn("security_verdict", result.contributions)

    def test_structured_extractor(self) -> None:
        extractor = StructuredExtractor()
        raw = "```json\n{\"client_name\": \"Acme Corp\", \"contract_value\": 100000}\n```"
        parsed = extractor.extract_json(raw)
        self.assertIsNotNone(parsed)
        validation = extractor.validate_schema(parsed, required_fields=["client_name", "contract_value"])
        self.assertTrue(validation.valid)
        self.assertEqual(validation.data["client_name"], "Acme Corp")

    def test_enterprise_rag_pythia(self) -> None:
        rag = EnterpriseRAG(score_threshold=0.3)
        rag.index_document("doc1", "Quantum linear algebra over complex field C is substrate-agnostic.")
        rag.index_document("doc2", "Salamander autonomic closed loop handles recovery.")
        results = rag.retrieve("quantum linear algebra")
        self.assertGreater(len(results), 0)
        self.assertIn("Quantum", results[0].chunk.content)

    def test_tool_gateway(self) -> None:
        gateway = CommercialToolGateway()
        gateway.register_tool(
            "compute_compound",
            "Computes exact interest",
            {"type": "object", "properties": {"rate": {"type": "number"}}},
            lambda rate: rate * 1.05,
        )
        call_res = gateway.execute_tool_call("compute_compound", {"rate": 100})
        self.assertTrue(call_res.success)
        self.assertEqual(call_res.result, 105.0)

    def test_eval_engine(self) -> None:
        evaluator = EvaluationEngine()
        evaluator.register_case("case1", 2, 4, lambda actual, expected: actual == expected)
        eval_res = evaluator.evaluate_runner(lambda x: x * 2)
        self.assertEqual(eval_res.pass_rate, 1.0)

    def test_cache_manager(self) -> None:
        cache = ContextCacheManager(ttl_seconds=10.0)
        key = cache.compute_key("Translate this into Arabic", "system_prompt_v1")
        self.assertIsNone(cache.get(key))
        cache.set(key, "مرحبا")
        self.assertEqual(cache.get(key), "مرحبا")
        stats = cache.stats()
        self.assertEqual(stats["total_hits"], 1)


if __name__ == "__main__":
    unittest.main()
