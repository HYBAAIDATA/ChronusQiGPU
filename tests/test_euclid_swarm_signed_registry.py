"""Real signed-registry integration; fixture signatures prove wiring, not training."""
import hashlib
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from euclid.capability_qualification import (
    CapabilityClaim, CapabilityQualificationRegistry, ClaimConclusion,
    EvidenceKind, EvidenceOutcome, EvidenceRecord, EvidenceStatus,
    QualificationStatus,
)
from euclid.swarm_curriculum import LeaderCurriculum, SkillCase, train_qualify_and_activate
from euclid.swarm_evolution import (
    LEADER_SKILLS, QualifiedAgent, SwarmActivator, SwarmJournal, SwarmMission,
    SwarmRefused, SwarmTask, VerificationAttestation, verification_payload,
)

REVISION = "d" * 40
CHECKS = ("domain-acceptance", "proxy-reward-exploitation", "negative-transfer")


def signed_claim(private_key, agent_id, skill, *, artifact_sha256=None):
    claim_id = agent_id + "." + skill
    records = []
    for index, check in enumerate(CHECKS):
        records.append(EvidenceRecord(
            evidence_id=f"evidence.{skill}.{index}",
            check_id=check,
            source_revision=REVISION,
            domain="euclid.agent.skill",
            task_scope="mission",
            claim_binding_digest="0" * 64,
            kind=EvidenceKind.TEST, status=EvidenceStatus.EXECUTED,
            outcome=EvidenceOutcome.PASS,
            artifact_sha256=(artifact_sha256 or hashlib.sha256(
                f"test-only-artifact-{agent_id}-{skill}-{index}".encode()
            ).hexdigest()),
            verifier_id="test-signer",
            independent=True,
            summary="Synthetic test fixture for registry cryptography only",
        ))
    claim = CapabilityClaim(
        claim_id=claim_id,
        statement="Test fixture qualification of " + skill,
        source_revision=REVISION, domain="euclid.agent.skill", task_scope="mission",
        conclusions=(ClaimConclusion("capability", "Test fixture only",
                                     (records[0].evidence_id,)),),
        evidence=tuple(records), acceptance_checks=CHECKS,
        authority_limits=(skill,), rollback_plan="Revoke in test",
    )
    digest = claim.binding_digest
    signed = tuple(
        replace(record, claim_binding_digest=digest,
                signature=private_key.sign(
                    replace(record, claim_binding_digest=digest).body()
                ).hex())
        for record in records
    )
    return replace(claim, evidence=signed)


class SignedQualificationIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.journal = SwarmJournal(Path(self.tmp.name) / "qualifications.sqlite")
        self.addCleanup(self.journal.close)
        self.signer = Ed25519PrivateKey.generate()
        self.registry = CapabilityQualificationRegistry(
            trusted_verifiers={"test-signer": self.signer.public_key()}
        )
        self.claims = {}
        for agent_id, skills in (("lead", LEADER_SKILLS), ("worker", {"task.run"})):
            for skill in sorted(skills):
                claim = signed_claim(self.signer, agent_id, skill)
                self.claims[(agent_id, skill)] = claim
                self.assertEqual(
                    self.registry.promote(claim).status, QualificationStatus.PROMOTED
                )

        def agent(name, skills):
            return QualifiedAgent(
                name, REVISION, "mission", tuple(sorted(skills)),
                {skill: self.claims[(name, skill)].claim_id for skill in skills},
            )
        self.leader = agent("lead", LEADER_SKILLS)
        self.worker = agent("worker", {"task.run"})
        self.runtime = SwarmActivator(
            qualification=self.registry, journal=self.journal,
            agents=(self.leader, self.worker), clock_ns=lambda: 100,
        )

    def attest(self, mission, task, output):
        return VerificationAttestation(
            "test-signer",
            self.signer.sign(verification_payload(mission, task, output)).hex(),
        )

    def test_real_signed_registry_authorizes_complete_dag(self):
        tasks = (SwarmTask("first", "worker", "task.run", 2),
                 SwarmTask("second", "worker", "task.run", 2, ("first",)))
        result = self.runtime.activate(
            SwarmMission("signed-1", "lead", "mission", 4, 200, tasks),
            dispatch=lambda task: {"task": task.task_id},
            verify=self.attest,
        )
        self.assertEqual(result["verified_tasks"], ["first", "second"])
        self.assertTrue(result["journal_verified"])

    def test_real_registry_revocation_stops_activation(self):
        claim = self.claims[("lead", "swarm.delegate")]
        self.registry.revoke(
            claim_id=claim.claim_id, source_revision=REVISION,
            domain="euclid.agent.skill", task_scope="mission",
            reason="test revocation",
        )
        with self.assertRaisesRegex(SwarmRefused, "qualification"):
            self.runtime.activate(
                SwarmMission("revoked", "lead", "mission", 2, 200,
                             (SwarmTask("first", "worker", "task.run", 2),)),
                dispatch=lambda task: {"task": task.task_id},
                verify=lambda *_: True,
            )

    def _test_curriculum(self):
        def partition(name):
            return tuple(SkillCase(
                f"{name}-{i}", f"lineage-{name}-{i}", skill,
                {"case": f"{name}-{i}", "skill": skill}, {"passed": True}
            ) for i, skill in enumerate(sorted(LEADER_SKILLS)))
        return LeaderCurriculum(
            "lead", "mission", REVISION, partition("train"),
            partition("validation"), partition("adversarial"),
            partition("final"),
        )

    def test_training_and_all_skill_acquisition_precede_swarm_activation(self):
        fresh = CapabilityQualificationRegistry(
            trusted_verifiers={"test-signer": self.signer.public_key()}
        )
        runtime = SwarmActivator(
            qualification=fresh, journal=self.journal,
            agents=(self.leader, self.worker), clock_ns=lambda: 100,
        )
        events = []

        def certify(report):
            self.assertEqual(report["outcome"], "READY_FOR_INDEPENDENT_ATTESTATION")
            events.append("attestation")
            fresh.promote(self.claims[("worker", "task.run")])
            for skill in sorted(LEADER_SKILLS):
                claim = signed_claim(
                    self.signer, "lead", skill,
                    artifact_sha256=report["report_sha256"],
                )
                self.assertEqual(
                    fresh.promote(claim).status, QualificationStatus.PROMOTED
                )
        result = train_qualify_and_activate(
            self._test_curriculum(),
            SwarmMission("trained", "lead", "mission", 2, 200,
                         (SwarmTask("one", "worker", "task.run", 2),)),
            activator=runtime,
            train=lambda cases: {
                "checkpoint_id": "test-only",
                "sha256": hashlib.sha256(b"test-only-fixture").hexdigest(),
            },
            evaluate=lambda checkpoint, case: {"passed": True},
            accept=lambda case, output: output["passed"] is True,
            certify=certify,
            dispatch=lambda task: events.append("dispatch") or {"task": task.task_id},
            verify=self.attest,
        )
        self.assertEqual(events, ["attestation", "dispatch"])
        self.assertEqual(result["swarm"]["status"], "completed")
        self.assertFalse(result["training"]["authority_granted"])

    def test_training_report_cannot_self_grant_swarm_authority(self):
        fresh = CapabilityQualificationRegistry(
            trusted_verifiers={"test-signer": self.signer.public_key()}
        )
        runtime = SwarmActivator(
            qualification=fresh, journal=self.journal,
            agents=(self.leader, self.worker), clock_ns=lambda: 100,
        )
        # Pre-existing valid claims are deliberately unrelated to this new report.
        for claim in self.claims.values():
            fresh.promote(claim)
        dispatched = []
        with self.assertRaisesRegex(SwarmRefused, "not bound"):
            train_qualify_and_activate(
                self._test_curriculum(),
                SwarmMission("unqualified", "lead", "mission", 2, 200,
                             (SwarmTask("one", "worker", "task.run", 2),)),
                activator=runtime,
                train=lambda cases: {"checkpoint_id": "test-only", "sha256": "f" * 64},
                evaluate=lambda checkpoint, case: {"passed": True},
                accept=lambda *_: True,
                certify=lambda report: None,
                dispatch=lambda task: dispatched.append(task.task_id) or {},
                verify=lambda *_: True,
            )
        self.assertEqual(dispatched, [])


    def test_cross_agent_claim_reuse_is_rejected(self):
        intruder = QualifiedAgent(
            "intruder", REVISION, "mission", ("task.run",),
            {"task.run": self.claims[("worker", "task.run")].claim_id},
        )
        runtime = SwarmActivator(
            qualification=self.registry, journal=self.journal,
            agents=(self.leader, intruder), clock_ns=lambda: 100,
        )
        with self.assertRaisesRegex(SwarmRefused, "agent identity"):
            runtime.activate(
                SwarmMission("cross-agent", "lead", "mission", 2, 200,
                             (SwarmTask("one", "intruder", "task.run", 2),)),
                dispatch=lambda task: {"task": task.task_id},
                verify=lambda *_: True,
            )

    def test_mutating_certifier_cannot_change_returned_training_report(self):
        fresh = CapabilityQualificationRegistry(
            trusted_verifiers={"test-signer": self.signer.public_key()}
        )
        runtime = SwarmActivator(
            qualification=fresh, journal=self.journal,
            agents=(self.leader, self.worker), clock_ns=lambda: 100,
        )

        def certify(report):
            original_digest = report["report_sha256"]
            report["outcome"] = "MUTATED"
            fresh.promote(self.claims[("worker", "task.run")])
            for skill in sorted(LEADER_SKILLS):
                fresh.promote(signed_claim(
                    self.signer, "lead", skill, artifact_sha256=original_digest
                ))

        result = train_qualify_and_activate(
            self._test_curriculum(),
            SwarmMission("mutating-certifier", "lead", "mission", 2, 200,
                         (SwarmTask("one", "worker", "task.run", 2),)),
            activator=runtime,
            train=lambda _: {"checkpoint_id": "test-only", "sha256": "a" * 64},
            evaluate=lambda *_: {"passed": True},
            accept=lambda *_: True,
            certify=certify,
            dispatch=lambda task: {"task": task.task_id},
            verify=self.attest,
        )
        self.assertEqual(
            result["training"]["outcome"], "READY_FOR_INDEPENDENT_ATTESTATION"
        )

    def test_evidence_signature_tampering_cannot_promote(self):
        fresh = CapabilityQualificationRegistry(
            trusted_verifiers={"test-signer": self.signer.public_key()}
        )
        original = self.claims[("lead", "swarm.plan")]
        mutated = replace(original, evidence=(
            replace(original.evidence[0], summary="changed after signing"),
            *original.evidence[1:],
        ))
        self.assertNotEqual(fresh.promote(mutated).status, QualificationStatus.PROMOTED)


if __name__ == "__main__":
    unittest.main()
