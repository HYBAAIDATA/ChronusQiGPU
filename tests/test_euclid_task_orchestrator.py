from __future__ import annotations
import unittest
from euclid.delegation import DelegationController, EvidenceSource, ResearchDomain, create_organ
from euclid.task_orchestrator import GoalStatus, TaskOrchestrator

class TaskOrchestratorIntegrationTests(unittest.TestCase):
    def controller(self, domains, external=False):
        c=DelegationController()
        for i, domain in enumerate(domains):
            c.registry.register(create_organ(f"organ-{i}", f"Organ {i}", domain, handler=lambda payload: {"ok": True, "payload": payload}))
        if external:
            ok=lambda *args: (True,"independent validator passed")
            c.integration_gate.wire_validators(coherence=ok,truth=ok,causal=ok,feedback=ok)
        return c

    def test_internal_evidence_executes_but_is_not_external(self):
        domain=ResearchDomain.MATHEMATICAL_ENGINE
        goal, agg, passed, _=TaskOrchestrator(self.controller([domain])).execute("test",[domain])
        self.assertTrue(passed)
        self.assertEqual(goal.status,GoalStatus.COMPLETE)
        self.assertFalse(agg.any_external_evidence)
        self.assertEqual(next(iter(agg.evidence_sources.values())),EvidenceSource.INTERNAL_HEURISTIC)

    def test_external_requirement_rejects_internal_evidence(self):
        domain=ResearchDomain.MATHEMATICAL_ENGINE
        _,agg,passed,reason=TaskOrchestrator(self.controller([domain]),require_external_evidence=True).execute("test",[domain])
        self.assertFalse(passed)
        self.assertFalse(agg.all_external_evidence)
        self.assertIn("external evidence required",reason)

    def test_independent_validators_satisfy_external_requirement(self):
        domain=ResearchDomain.MATHEMATICAL_ENGINE
        _,agg,passed,_=TaskOrchestrator(self.controller([domain],external=True),require_external_evidence=True).execute("test",[domain])
        self.assertTrue(passed)
        self.assertTrue(agg.all_external_evidence)

    def test_dependency_chain_executes_in_order(self):
        domains=[ResearchDomain.MATHEMATICAL_ENGINE,ResearchDomain.EMERGENCE_ENGINE]
        goal,agg,passed,_=TaskOrchestrator(self.controller(domains)).execute("chain",domains)
        self.assertTrue(passed)
        self.assertEqual(goal.accepted_count,2)
        self.assertEqual(agg.completion_ratio,1.0)

    def test_missing_organ_fails_closed(self):
        domain=ResearchDomain.MATHEMATICAL_ENGINE
        goal,agg,passed,_=TaskOrchestrator(DelegationController()).execute("missing",[domain])
        self.assertFalse(passed)
        self.assertEqual(goal.status,GoalStatus.FAILED)
        self.assertEqual(len(agg.failed_subtasks),1)

if __name__ == '__main__': unittest.main()
