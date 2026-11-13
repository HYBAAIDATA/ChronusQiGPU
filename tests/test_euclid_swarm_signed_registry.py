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
from euclid.swarm_evolution import (
    LEADER_SKILLS, QualifiedAgent, SwarmActivator, SwarmJournal, SwarmMission,
    SwarmRefused, SwarmTask,
)

REVISION = "d" * 40
CHECKS = ("domain-acceptance", "proxy-reward-exploitation", "negative-transfer")


def signed_claim(private_key, skill):
    claim_id = "qualification." + skill
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
            artifact_sha256=hashlib.sha256(
                f"test-only-artifact-{skill}-{index}".encode()
            ).hexdigest(),
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
        for skill in sorted(LEADER_SKILLS | {"task.run"}):
            claim = signed_claim(self.signer, skill)
            self.claims[skill] = claim
            self.assertEqual(self.registry.promote(claim).status, QualificationStatus.PROMOTED)
        def agent(name, skills):
            return QualifiedAgent(
                name, REVISION, "mission", tuple(sorted(skills)),
                {skill: self.claims[skill].claim_id for skill in skills},
            )
        self.leader = agent("lead", LEADER_SKILLS)
        self.worker = agent("worker", {"task.run"})
        self.runtime = SwarmActivator(
            qualification=self.registry, journal=self.journal,
            agents=(self.leader, self.worker), clock_ns=lambda: 100,
        )

    def test_real_signed_registry_authorizes_complete_dag(self):
        tasks = (SwarmTask("first", "worker", "task.run", 2),
                 SwarmTask("second", "worker", "task.run", 2, ("first",)))
        result = self.runtime.activate(
            SwarmMission("signed-1", "lead", "mission", 4, 200, tasks),
            dispatch=lambda task: {"task": task.task_id},
            verify=lambda task, output: output["task"] == task.task_id,
        )
        self.assertEqual(result["verified_tasks"], ["first", "second"])
        self.assertTrue(result["journal_verified"])

    def test_real_registry_revocation_stops_activation(self):
        claim = self.claims["swarm.delegate"]
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

    def test_evidence_signature_tampering_cannot_promote(self):
        fresh = CapabilityQualificationRegistry(
            trusted_verifiers={"test-signer": self.signer.public_key()}
        )
        original = self.claims["swarm.plan"]
        mutated = replace(original, evidence=(
            replace(original.evidence[0], summary="changed after signing"),
            *original.evidence[1:],
        ))
        self.assertNotEqual(fresh.promote(mutated).status, QualificationStatus.PROMOTED)


if __name__ == "__main__":
    unittest.main()
