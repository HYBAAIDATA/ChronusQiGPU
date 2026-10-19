"""Local real Ed25519/SQLite authorization tests; no independent assurance claim."""
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from euclid.emergence.models.candidate import DiscoveryEnvelope, EmergentCandidate, ReproductionProtocol
from euclid.emergence.models.substrate import SubstrateProperties
from euclid.emergence.substrate.executors import StandardSyncExecutor, AsyncIsolatedExecutor
from euclid.emergence.trusted_core.access_control import (
    GovernanceToken, QualificationAuthorization, InvalidGovernanceTokenError,
)
from euclid.emergence.trusted_core.qualification_service import EmergentQualificationService


def make_candidate():
    return EmergentCandidate("authorized-candidate", "behavior", "discovery",
        DiscoveryEnvelope(10, .1, 1),
        ReproductionProtocol("task", (1,), "manifest", "environment", ("observed",),
                             steps=({"action": "observe"},)), "observed")


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.path = self.root/"replay.sqlite"
        self.key = Ed25519PrivateKey.generate(); self.now = 1000
        self.candidate = make_candidate(); self.fingerprint = self.candidate.compute_fingerprint()
        self.keys = {("issuer", "officer"): self.key.public_key()}
        self.authority = self.verifier()
        self.service = EmergentQualificationService(authorization=self.authority)

    def verifier(self, **changes):
        args = dict(trusted_signers=self.keys, audience="euclid-philos-test", replay_path=self.path,
                    clock=lambda: self.now)
        args.update(changes)
        return QualificationAuthorization(**args)

    def token(self, **changes):
        args = dict(issuer="issuer", audience="euclid-philos-test",
                    candidate_fingerprint=self.fingerprint, now=self.now)
        args.update(changes)
        return GovernanceToken.issue("officer", self.key, **args)

    def authorize(self, token, verifier=None):
        (verifier or self.authority).authorize(token, candidate_fingerprint=self.fingerprint)

    def resign(self, token):
        return replace(token, token_digest=self.key.sign(token.body()).hex())

    def substrates(self):
        return (StandardSyncExecutor(SubstrateProperties("sync",1,"atomic","cpu",sandbox_id="a")),
                AsyncIsolatedExecutor(SubstrateProperties("async",10,"batch","gpu",sandbox_id="b")))

    def test_no_default_authority_or_signing_secret(self):
        service = EmergentQualificationService()
        self.assertIsNone(service.authorization)
        self.assertFalse(hasattr(service, "governance_secret_key"))
        with self.assertRaises(InvalidGovernanceTokenError):
            service.qualify(self.candidate, *self.substrates(), governance_token=self.token())
        with self.assertRaises(TypeError):
            EmergentQualificationService(governance_secret_key="public legacy secret")

    def test_public_key_cannot_issue(self):
        with self.assertRaises(TypeError):
            GovernanceToken.issue("officer",self.key.public_key(), issuer="issuer",
                audience="euclid-philos-test",candidate_fingerprint=self.fingerprint)

    def test_all_security_fields_are_signed(self):
        token = self.token()
        for field, value in {"issuer":"other", "officer_id":"other", "audience":"other",
                "candidate_fingerprint":"a"*64, "issued_at":999, "expires_at":1061,
                "nonce":"a"*64, "operation":"promote", "schema":"other"}.items():
            with self.subTest(field=field), self.assertRaises(InvalidGovernanceTokenError):
                self.authorize(replace(token, **{field:value}))

    def test_self_signed_unknown_issuer_or_officer_refused(self):
        for principal in (("unknown","officer"),("issuer","unknown")):
            token = replace(self.token(),issuer=principal[0],officer_id=principal[1])
            with self.subTest(principal=principal), self.assertRaises(InvalidGovernanceTokenError):
                self.authorize(self.resign(token))

    def test_wrong_key_and_tampered_signature_refused(self):
        token = self.token()
        bad = replace(token,token_digest=Ed25519PrivateKey.generate().sign(token.body()).hex())
        with self.assertRaises(InvalidGovernanceTokenError): self.authorize(bad)
        with self.assertRaises(InvalidGovernanceTokenError): self.authorize(replace(token,token_digest="0"*128))

    def test_nonfinite_bool_and_excessive_issue_lifetimes_refused(self):
        for ttl in (float("nan"),float("inf"),True,0,-1,301,1.5):
            with self.subTest(ttl=ttl), self.assertRaises(ValueError): self.token(ttl_seconds=ttl)

    def test_signed_time_and_operation_constraints_are_enforced(self):
        token = self.token()
        changes = ({"issued_at":1001}, {"expires_at":1000}, {"expires_at":1400},
                   {"operation":"promote"}, {"issued_at":True})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(InvalidGovernanceTokenError):
                self.authorize(self.resign(replace(token, **change)))
        self.assertFalse(replace(token,expires_at=float("nan")).verify(self.key.public_key(),
            audience=token.audience,candidate_fingerprint=self.fingerprint,now=self.now))

    def test_protocol_mutation_and_cross_candidate_token_refused(self):
        token = self.token()
        self.candidate.reproduction_steps.steps[0]["action"]="changed"
        with self.assertRaises(InvalidGovernanceTokenError):
            self.authority.authorize(token,candidate_fingerprint=self.candidate.compute_fingerprint())
        self.assertEqual(0,len(self.service.journal.get_entries()))

    def test_same_token_refused_across_verifier_restarts(self):
        token = self.token(); self.authorize(token)
        with self.assertRaises(InvalidGovernanceTokenError): self.authorize(token,self.verifier())

    def test_concurrent_verifiers_admit_exactly_once(self):
        token = self.token(); other = self.verifier(); outcomes=[]; barrier=threading.Barrier(2)
        def run(verifier):
            barrier.wait()
            try: self.authorize(token,verifier); outcomes.append("admitted")
            except InvalidGovernanceTokenError: outcomes.append("refused")
        threads=[threading.Thread(target=run,args=(v,)) for v in (self.authority,other)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(5)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertCountEqual(outcomes,["admitted","refused"])

    def test_expired_token_refused(self):
        token = self.token(); self.now=token.expires_at
        with self.assertRaises(InvalidGovernanceTokenError): self.authorize(token)

    def test_full_ledger_refuses_without_evicting_live_authorization(self):
        verifier=self.verifier(max_outstanding=1); first=self.token(); self.authorize(first,verifier)
        with self.assertRaises(InvalidGovernanceTokenError): self.authorize(self.token(),verifier)
        with self.assertRaises(InvalidGovernanceTokenError): self.authorize(first,verifier)
        self.now += 61
        self.authorize(self.token(),verifier)

    def test_persisted_clock_rollback_refused(self):
        self.authorize(self.token()); self.now -= 1
        with self.assertRaises(InvalidGovernanceTokenError): self.authorize(self.token())

    def test_ledger_cannot_be_rebound_to_other_audience(self):
        with self.assertRaises(ValueError): self.verifier(audience="another-service")

    def test_host_key_mapping_is_detached_and_revocation_refuses(self):
        token=self.token(); self.keys.clear(); self.authorize(token)
        self.keys={("issuer","officer"):Ed25519PrivateKey.generate().public_key()}
        with self.assertRaises(InvalidGovernanceTokenError): self.authorize(self.token(),self.verifier())

    def test_unavailable_replay_ledger_refuses(self):
        self.path.unlink(); self.path.mkdir()
        with self.assertRaises(InvalidGovernanceTokenError): self.authorize(self.token())

    def test_service_consumes_authorization_even_when_simulation_refused(self):
        token=self.token(); result=self.service.qualify(self.candidate,*self.substrates(),governance_token=token)
        self.assertIn("lacks measured reproduction",result.reason)
        with self.assertRaises(InvalidGovernanceTokenError):
            self.service.qualify(self.candidate,*self.substrates(),governance_token=token)
        self.assertFalse(self.service.is_qualified(self.candidate.candidate_id))
        self.assertEqual("AUTHORIZATION_REFUSED",self.service.journal.get_entries()[-1].action)

    def test_valid_authorization_does_not_qualify(self):
        self.authorize(self.token())
        self.assertFalse(self.service.is_qualified(self.candidate.candidate_id))

    def test_invalid_margin_and_configuration_fail_closed(self):
        for margin in (0,1,1.4,float("nan"),float("inf"),True):
            with self.subTest(margin=margin), self.assertRaises(ValueError):
                EmergentQualificationService(margin=margin)
        with self.assertRaises(ValueError): self.verifier(trusted_signers={})
        with self.assertRaises(TypeError): self.verifier(trusted_signers={("issuer","officer"):self.key})
