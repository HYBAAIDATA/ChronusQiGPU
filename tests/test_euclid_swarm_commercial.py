"""Commercial entrypoint integration and legacy-claim correction."""
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from euclid.commercial.team_orchestrator import CommercialTeamOrchestrator
from euclid.capability_qualification import CapabilityQualificationRegistry
from euclid.swarm_evolution import (
    LEADER_SKILLS, QualifiedAgent, SwarmActivator,
    SwarmJournal, SwarmMission, SwarmRefused, SwarmTask,
    VerificationAttestation, verification_payload,
)


class Policy(CapabilityQualificationRegistry):
    def __init__(self):
        self.signer = Ed25519PrivateKey.generate()
        super().__init__(trusted_verifiers={"test": self.signer.public_key()})

    def authorize(self, *, claim_id, source_revision, domain, task_scope, authority):
        if not claim_id.endswith("." + authority) or domain != "euclid.agent.skill":
            raise PermissionError("not qualified")
        if source_revision != "c" * 40 or task_scope != "case":
            raise PermissionError("scope mismatch")
        return True

    def attest(self, mission, item, result):
        return VerificationAttestation(
            "test", self.signer.sign(
                verification_payload(mission, item, result)
            ).hex(),
        )


class CommercialIntegration(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.journal = SwarmJournal(Path(self.directory.name) / "events.sqlite")
        self.addCleanup(self.journal.close)

        def member(identifier, skills):
            return QualifiedAgent(
                identifier, "c" * 40, "case", tuple(sorted(skills)),
                {skill: identifier + "." + skill for skill in skills},
            )
        self.agents = [member("lead", LEADER_SKILLS), member("agent", {"task.run"})]
        self.policy = Policy()
        self.activator = SwarmActivator(
            qualification=self.policy, journal=self.journal, agents=self.agents,
            clock_ns=lambda: 1000,
        )
        self.mission = SwarmMission(
            "case1", "lead", "case", 3, 2000,
            (SwarmTask("work", "agent", "task.run", 3),),
        )

    def test_commercial_qualified_entrypoint_e2e(self):
        calls = []
        result = CommercialTeamOrchestrator(cost_meter=lambda: 0.0).run_qualified_swarm(
            self.activator, self.mission,
            dispatch=lambda item: calls.append(item.task_id) or {"ok": True},
            verify=self.policy.attest,
        )
        self.assertEqual(calls, ["work"])
        self.assertEqual(result["verified_tasks"], ["work"])
        self.assertTrue(result["journal_verified"])

    def test_qualified_swarm_requires_measured_cost_enforcement(self):
        with self.assertRaisesRegex(RuntimeError, "cost enforcement"):
            CommercialTeamOrchestrator().run_qualified_swarm(
                self.activator, self.mission,
                dispatch=lambda _: {"ok": True},
                verify=lambda *_: True,
            )

    def test_commercial_budget_is_checked_around_dispatch(self):
        samples = iter([0.0, 0.0, 2.0])
        orchestrator = CommercialTeamOrchestrator(
            team_budget_usd=1.0, cost_meter=lambda: next(samples), clock=lambda: 0.0
        )
        with self.assertRaisesRegex(RuntimeError, "budget exceeded"):
            orchestrator.run_qualified_swarm(
                self.activator, self.mission,
                dispatch=lambda _: {"ok": True},
                verify=lambda *_: True,
            )

    def test_legacy_hooks_not_falsely_approved(self):
        result = CommercialTeamOrchestrator().run_collaborative_task(
            "example", {"EUCLID": lambda objective: "draft"},
        )
        self.assertEqual(result.verdict, "UNVERIFIED_LEGACY")
        self.assertIsNone(result.total_cost_usd)

    def test_legacy_result_does_not_bypass_qualification(self):
        legacy = CommercialTeamOrchestrator().run_collaborative_task(
            "example", {"EUCLID": lambda objective: "draft"},
        )
        self.assertNotEqual(legacy.verdict, "APPROVED_BY_CONSENSUS")
        with self.assertRaises(SwarmRefused):
            CommercialTeamOrchestrator(cost_meter=lambda: 0.0).run_qualified_swarm(
                self.activator,
                SwarmMission("case2", "not-authorized", "case", 3, 2000, self.mission.tasks),
                dispatch=lambda _: {"ok": True},
                verify=lambda *_: True,
            )


if __name__ == "__main__":
    unittest.main()
