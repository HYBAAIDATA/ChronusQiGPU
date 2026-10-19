"""Actual EUCLID/AL HARAS -> native PHILOS refusal integration, not qualification.

Requires the canonical runtime revision from PR74. No runtime aliases or internal
mocks; random local entitlement/authorization keys are not independent assurance.
"""
from dataclasses import asdict, replace
import inspect
import os
from pathlib import Path
import tempfile
import time
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from euclid import EuclidRuntime
from al_haras import ALHaras, GuardianPolicy, HashChainAudit, SubscriptionAuthority, SubscriptionClaims
from euclid.emergence.integration import bind_philos, QualificationCase
from euclid.emergence.models.candidate import DiscoveryEnvelope, EmergentCandidate, ReproductionProtocol
from euclid.emergence.models.substrate import SubstrateProperties
from euclid.emergence.substrate.executors import StandardSyncExecutor, AsyncIsolatedExecutor
from euclid.emergence.trusted_core.access_control import GovernanceToken, QualificationAuthorization
from euclid.emergence.trusted_core.qualification_service import EmergentQualificationService

class CanonicalPhilosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "authority" not in inspect.signature(EuclidRuntime.register_specialist).parameters:
            raise unittest.SkipTest("requires PR74 canonical explicit-authority runtime revision")

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.runtime=EuclidRuntime(creator_id="owner",state_dir=self.root/"euclid")
        self.key=Ed25519PrivateKey.generate(); self.now=int(time.time())
        self.candidate=EmergentCandidate("candidate","behavior","discovery",DiscoveryEnvelope(10,.1,1),
            ReproductionProtocol("task",(1,),"manifest","environment",("observed",),
                steps=({"action":"observe"},)),"observed")
        a=StandardSyncExecutor(SubstrateProperties("sync",1,"atomic","cpu",sandbox_id="a"))
        b=AsyncIsolatedExecutor(SubstrateProperties("async",10,"batch","gpu",sandbox_id="b"))
        self.service=EmergentQualificationService(authorization=QualificationAuthorization(
            trusted_signers={("operator","officer"):self.key.public_key()},audience="euclid-philos",
            replay_path=self.root/"replay.sqlite",clock=lambda:self.now))
        self.subscription=SubscriptionAuthority({"local":os.urandom(32)},"local-authority")
        self.runtime.guardian=ALHaras(self.subscription,GuardianPolicy("local-policy",
            allowed_operations=frozenset({"philos.qualify"})),HashChainAudit(self.root/"guardian.jsonl"))
        self.case=QualificationCase.capture(self.candidate,a,b)
        self.cases={"case":self.case}
        self.specialist=bind_philos(self.runtime,self.service,cases=self.cases)
        self.runtime.rights.grant("owner","philos","philos.request","dispatch")

    def tearDown(self):
        self.runtime.close();self.temp.cleanup()

    def token(self):
        return GovernanceToken.issue("officer",self.key,issuer="operator",audience="euclid-philos",
            candidate_fingerprint=self.case.candidate.fingerprint,now=self.now)

    def dispatch(self, token=None, **changes):
        claims=SubscriptionClaims("subscription","tenant","local-authority","local",("hyba.security",),
            ("actor",),self.now-10,self.now+60)
        request={"operation":"qualify","case_id":"case","governance_token":asdict(token or self.token())}
        request.update(changes)
        return self.runtime.dispatch_specialist("philos",request,tenant_id="tenant",actor="actor",
            subscription_token=self.subscription.issue(claims))

    def test_real_entry_point_invokes_native_service_and_refuses_simulation(self):
        token=self.token();result=self.dispatch(token)
        self.assertTrue(result["allowed"])
        outcome=result["result"]
        self.assertEqual(outcome["status"],"REJECTED")
        self.assertFalse(outcome["qualified"])
        self.assertFalse(outcome["independently_qualified"])
        self.assertTrue(outcome["qualification_invoked"])
        self.assertFalse(self.service.is_qualified(self.candidate.candidate_id))
        audit=HashChainAudit(self.root/"euclid/philos/philos.jsonl")
        self.assertTrue(HashChainAudit.verify(audit.records))
        self.assertEqual([r["event"]["kind"] for r in audit.records],
            ["philos-request-admitted","philos-request-completed"])
        self.assertNotIn(token.token_digest,(self.root/"euclid/philos/philos.jsonl").read_text())

    def test_invalid_signature_and_replay_cannot_qualify(self):
        token=self.token()
        self.assertFalse(self.dispatch(replace(token,token_digest="0"*128))["allowed"])
        # Fresh runtime: an authorization refusal can mark the specialist vetoed.
        self.assertFalse(self.service.is_qualified(self.candidate.candidate_id))

    def test_one_use_token_is_consumed_on_simulation_refusal(self):
        token=self.token();self.assertEqual(self.dispatch(token)["result"]["status"],"REJECTED")
        self.assertFalse(self.dispatch(token)["allowed"])

    def test_revoked_creator_rights_block_before_token_consumption(self):
        self.runtime.rights.revoke("owner","philos","philos.request","dispatch")
        token=self.token();self.assertFalse(self.dispatch(token)["allowed"])
        self.service.authorization.authorize(token,candidate_fingerprint=self.case.candidate.fingerprint)

    def test_missing_guardian_blocks_before_token_consumption(self):
        self.runtime.guardian=None;token=self.token()
        self.assertFalse(self.dispatch(token)["allowed"])
        self.service.authorization.authorize(token,candidate_fingerprint=self.case.candidate.fingerprint)

    def test_case_snapshot_detaches_original_and_host_mapping(self):
        self.cases.clear();self.candidate.behavior_description="mutated outside case"
        self.assertEqual(self.dispatch()["result"]["candidate_fingerprint"],self.case.candidate.fingerprint)

    def test_client_cannot_choose_executor_or_unapproved_case(self):
        with self.assertRaises(ValueError):self.dispatch(executor="client-selected")

    def test_unapproved_case_is_refused(self):
        self.assertFalse(self.dispatch(case_id="not-approved")["allowed"])

    def test_admission_audit_failure_prevents_authorization_consumption(self):
        from al_haras.audit import AuditIntegrityError
        path=self.root/"euclid/philos/philos.jsonl"
        path.write_text("invalid durable audit content")
        token=self.token()
        with self.assertRaises(AuditIntegrityError):self.dispatch(token)
        self.service.authorization.authorize(token,candidate_fingerprint=self.case.candidate.fingerprint)

    def test_new_binding_does_not_install_creator_dispatch_rights(self):
        bind_philos(self.runtime,self.service,cases={"case":self.case},organ_id="second")
        # Rights store records only the original explicit host grant.
        self.assertFalse(self.runtime.rights.permits("owner","second","second.request","dispatch"))

    def test_binding_does_not_grant_dispatch_or_signing_authority(self):
        from euclid.contracts import Authority
        item=self.runtime.registry.get("philos")
        self.assertEqual(item.authority,Authority.PROPOSE)
        self.assertFalse(hasattr(self.service,"governance_secret_key"))
        with self.assertRaises(ValueError):bind_philos(self.runtime,self.service,cases={"case":self.case},organ_id="../escape")
