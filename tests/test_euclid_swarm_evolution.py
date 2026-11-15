"""Unit, property, adversarial, integration and restart checks for EUCLID swarm.

A controlled authorization stub is used for scheduler mechanics only; it is
NOT evidence of training or independent promotion. The real registry rejects
unpromoted leaders in the integration gate below.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from euclid.capability_qualification import CapabilityQualificationRegistry
from euclid.swarm_evolution import (
    LEADER_SKILLS, QualifiedAgent, SwarmActivator, SwarmJournal,
    SwarmMission, SwarmRefused, SwarmTask, VerificationAttestation,
    verification_payload,
)

SHA = "a" * 40
NOW = 1_000_000_000
DEADLINE = NOW + 10000


class ScopedQualification(CapabilityQualificationRegistry):
    """Test-only controlled registry subclass; never represents training evidence."""
    def __init__(self):
        self.signer = Ed25519PrivateKey.generate()
        super().__init__(trusted_verifiers={"test": self.signer.public_key()})
        self.allowed = set()
        self.calls = []

    def authorize(self, *, claim_id, source_revision, domain, task_scope, authority):
        self.calls.append((claim_id, source_revision, domain, task_scope, authority))
        if (claim_id, task_scope, authority) not in self.allowed:
            raise PermissionError("not promoted")
        return True

    def attest(self, mission, item, result):
        return VerificationAttestation(
            "test", self.signer.sign(
                verification_payload(mission, item, result)
            ).hex(),
        )


def agent(name, skills, scope="mission"):
    return QualifiedAgent(
        name, SHA, scope, tuple(sorted(skills)),
        {skill: name + "." + skill for skill in skills},
    )


def task(name, worker="worker", skill="job.execute", dependencies=(), cost=2):
    return SwarmTask(name, worker, skill, cost, tuple(dependencies))


def mission(tasks=None, *, leader="leader", budget=12, scope="mission", mission_id="run"):
    return SwarmMission(mission_id, leader, scope, budget, DEADLINE, tuple(tasks or (task("one"),)))


class SwarmTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "swarm.db"
        self.journal = SwarmJournal(self.path)
        self.addCleanup(self.journal.close)
        self.policy = ScopedQualification()
        self.leader = agent("leader", LEADER_SKILLS)
        self.worker = agent("worker", {"job.execute"})
        for member in (self.leader, self.worker):
            for skill, claim in member.capability_claims.items():
                self.policy.allowed.add((claim, "mission", skill))
        self.activator = SwarmActivator(
            qualification=self.policy, journal=self.journal,
            agents=[self.leader, self.worker], clock_ns=lambda: NOW,
        )
        self.dispatched = []

    def dispatch(self, item):
        self.dispatched.append(item.task_id)
        return {"task": item.task_id, "accepted": True}

    def verify(self, active_mission, item, result):
        if result["task"] != item.task_id or result["accepted"] is not True:
            raise AssertionError("invalid test result")
        return self.policy.attest(active_mission, item, result)

    def test_end_to_end_dependencies_are_ordered(self):
        plan = mission((task("c", dependencies=("b",)), task("a"),
                        task("b", dependencies=("a",))))
        report = self.activator.activate(plan, dispatch=self.dispatch, verify=self.verify)
        self.assertEqual(self.dispatched, ["a", "b", "c"])
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["verified_tasks"], ["a", "b", "c"])
        self.assertEqual(report["reserved_budget_units"], 6)
        self.assertTrue(report["journal_verified"])
        self.assertTrue(self.journal.verify("run"))

    def test_leader_all_skills_required_prior_to_first_dispatch(self):
        for omitted in sorted(LEADER_SKILLS):
            with self.subTest(skill=omitted):
                policy = ScopedQualification()
                for tup in self.policy.allowed:
                    if tup != (self.leader.capability_claims[omitted], "mission", omitted):
                        policy.allowed.add(tup)
                candidate = SwarmActivator(qualification=policy, journal=self.journal,
                                           agents=[self.leader, self.worker],
                                           clock_ns=lambda: NOW)
                with self.assertRaises(SwarmRefused):
                    candidate.activate(mission(mission_id="missing-" + omitted),
                                       dispatch=self.dispatch, verify=self.verify)
        self.assertEqual(self.dispatched, [])

    def test_real_registry_refuses_untrained_and_unsigned_leader(self):
        real = CapabilityQualificationRegistry(
            trusted_verifiers={"test-verifier": Ed25519PrivateKey.generate().public_key()}
        )
        candidate = SwarmActivator(qualification=real, journal=self.journal,
                                   agents=[self.leader, self.worker], clock_ns=lambda: NOW)
        with self.assertRaises(SwarmRefused):
            candidate.activate(mission(), dispatch=self.dispatch, verify=self.verify)
        self.assertEqual(self.dispatched, [])

    def test_scope_mismatch_cannot_inherit_skill_authority(self):
        wrong = agent("worker", {"job.execute"}, scope="another")
        candidate = SwarmActivator(qualification=self.policy, journal=self.journal,
                                   agents=[self.leader, wrong], clock_ns=lambda: NOW)
        with self.assertRaises(SwarmRefused):
            candidate.activate(mission(), dispatch=self.dispatch, verify=self.verify)
        self.assertEqual(self.dispatched, [])

    def test_mid_swarm_revocation_fails_closed(self):
        def revoke_after_first(item):
            if item.task_id == "a":
                self.policy.allowed.remove(("leader.swarm.delegate", "mission", "swarm.delegate"))
            return self.dispatch(item)
        with self.assertRaises(SwarmRefused):
            self.activator.activate(mission((task("a"), task("b", dependencies=("a",)))),
                                    dispatch=revoke_after_first, verify=self.verify)
        self.assertEqual(self.dispatched, ["a"])
        self.assertTrue(self.journal.verify("run"))

    def test_verifier_refusal_blocks_all_dependents(self):
        with self.assertRaisesRegex(SwarmRefused, "verification"):
            self.activator.activate(mission((task("a"), task("b", dependencies=("a",)))),
                                    dispatch=self.dispatch, verify=lambda *_: False)
        self.assertEqual(self.dispatched, ["a"])
        self.assertTrue(self.journal.verify("run"))

    def test_callback_exception_is_fail_closed(self):
        def denied(_item):
            raise RuntimeError("host unavailable")
        with self.assertRaises(RuntimeError):
            self.activator.activate(mission(), dispatch=denied, verify=self.verify)
        self.assertTrue(self.journal.verify("run"))

    def test_deadline_precheck(self):
        candidate = SwarmActivator(qualification=self.policy, journal=self.journal,
                                   agents=[self.leader, self.worker],
                                   clock_ns=lambda: DEADLINE)
        with self.assertRaisesRegex(SwarmRefused, "expired"):
            candidate.activate(mission(), dispatch=self.dispatch, verify=self.verify)
        self.assertEqual(self.dispatched, [])

    def test_deadline_during_execution(self):
        count = 0

        def ticking():
            nonlocal count
            count += 1
            return NOW if count <= 2 else DEADLINE
        candidate = SwarmActivator(qualification=self.policy, journal=self.journal,
                                   agents=[self.leader, self.worker], clock_ns=ticking)
        with self.assertRaisesRegex(SwarmRefused, "deadline"):
            candidate.activate(mission((task("a"), task("b"))),
                               dispatch=self.dispatch, verify=self.verify)
        self.assertEqual(self.dispatched, ["a"])

    def test_restart_replay_duplicate_refused_before_dispatch(self):
        plan = mission()
        self.activator.activate(plan, dispatch=self.dispatch, verify=self.verify)
        self.journal.close()
        replacement = SwarmJournal(self.path)
        self.addCleanup(replacement.close)
        recovered = SwarmActivator(qualification=self.policy, journal=replacement,
                                   agents=[self.leader, self.worker], clock_ns=lambda: NOW)
        with self.assertRaisesRegex(SwarmRefused, "replay"):
            recovered.activate(plan, dispatch=self.dispatch, verify=self.verify)
        self.assertEqual(self.dispatched, ["one"])
        self.assertTrue(replacement.verify("run"))

    def test_crash_journal_mission_also_not_replayed(self):
        plan = mission()
        self.journal.admit(plan)
        self.journal.append("run", {"kind": "activated"})
        self.journal.close()
        replacement = SwarmJournal(self.path)
        self.addCleanup(replacement.close)
        recovered = SwarmActivator(qualification=self.policy, journal=replacement,
                                   agents=[self.leader, self.worker], clock_ns=lambda: NOW)
        with self.assertRaises(SwarmRefused):
            recovered.activate(plan, dispatch=self.dispatch, verify=self.verify)
        self.assertEqual(self.dispatched, [])

    def test_tampered_chain_is_detected(self):
        self.activator.activate(mission(), dispatch=self.dispatch, verify=self.verify)
        db = sqlite3.connect(self.path)
        db.execute("UPDATE events SET payload=? WHERE mission_id=? AND seq=2",
                   ('{"kind":"forged"}', "run"))
        db.commit()
        db.close()
        self.assertFalse(self.journal.verify("run"))

    def test_invalid_result_is_rejected(self):
        with self.assertRaises(SwarmRefused):
            self.activator.activate(mission(), dispatch=lambda _: {"bad": float("nan")},
                                    verify=lambda *_: True)
        self.assertTrue(self.journal.verify("run"))

    def test_verifier_must_be_literal_true(self):
        with self.assertRaises(SwarmRefused):
            self.activator.activate(mission(), dispatch=self.dispatch,
                                    verify=lambda *_: 1)

    def test_property_acyclic_graphs_execute_once(self):
        for size in range(1, 20):
            plan = mission(tuple(task(f"t{i}", dependencies=(f"t{i-1}",) if i else (),
                                      cost=1) for i in reversed(range(size))),
                           budget=size, mission_id=f"chain-{size}")
            self.dispatched.clear()
            result = self.activator.activate(plan, dispatch=self.dispatch, verify=self.verify)
            self.assertEqual(self.dispatched, [f"t{i}" for i in range(size)])
            self.assertEqual(len(result["verified_tasks"]), size)
            self.assertEqual(result["reserved_budget_units"], size)

    def test_cycle_and_unknown_dependency_rejected(self):
        for tasks in (
            (task("a", dependencies=("b",)), task("b", dependencies=("a",))),
            (task("a", dependencies=("unknown",)),),
            (task("a", dependencies=("a",)),),
        ):
            with self.subTest(tasks=tasks), self.assertRaises(SwarmRefused):
                mission(tasks)
        self.assertEqual(self.dispatched, [])

    def test_budget_invariant_exhaustive_small_teams(self):
        for n in range(1, 20):
            for cost in range(1, 6):
                tasks = tuple(task(f"t{i}", cost=cost) for i in range(n))
                if n * cost > MAX_BUDGET_FOR_TEST:
                    with self.assertRaises(SwarmRefused):
                        mission(tasks, budget=MAX_BUDGET_FOR_TEST)
                else:
                    plan = mission(tasks, budget=MAX_BUDGET_FOR_TEST,
                                   mission_id=f"budget-{n}-{cost}")
                    result = self.activator.activate(plan, dispatch=self.dispatch,
                                                     verify=self.verify)
                    self.assertLessEqual(result["reserved_budget_units"], MAX_BUDGET_FOR_TEST)

    def test_boolean_and_duplicate_identity_edge_cases(self):
        with self.assertRaises(SwarmRefused):
            SwarmTask("x", "worker", "job.execute", True)
        with self.assertRaises(SwarmRefused):
            SwarmMission("x", "leader", "mission", True, DEADLINE, (task("a"),))
        with self.assertRaises(SwarmRefused):
            SwarmActivator(qualification=self.policy, journal=self.journal,
                           agents=[self.leader, self.leader])
        with self.assertRaises(SwarmRefused):
            QualifiedAgent("leader", SHA, "mission", ("swarm.plan", "swarm.plan"),
                           {"swarm.plan": "claim"})

    def test_required_dispatcher_and_verifier(self):
        with self.assertRaises(SwarmRefused):
            self.activator.activate(mission(), dispatch=None, verify=self.verify)
        self.assertEqual(self.dispatched, [])


MAX_BUDGET_FOR_TEST = 30


if __name__ == "__main__":
    unittest.main()
