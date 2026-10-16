"""Custody unit/adversarial contract tests, not independent qualification."""
import dataclasses
import tempfile
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import unittest
from unittest.mock import patch

from euclid.emergence.models.candidate import (
    DiscoveryEnvelope, EmergentCandidate, ReproductionProtocol,
)
from euclid.emergence.models.qualification import RejectedQualification
from euclid.emergence.models.substrate import SubstrateProperties
from euclid.emergence.substrate.executors import StandardSyncExecutor, AsyncIsolatedExecutor
from euclid.emergence.trusted_core.custody import CandidateSnapshot, CandidateCustodyError
from euclid.emergence.trusted_core.access_control import GovernanceToken, InvalidGovernanceTokenError, QualificationAuthorization
from euclid.emergence.trusted_core.qualification_service import EmergentQualificationService
from euclid.emergence.trusted_core.stress import stress_test


def candidate():
    return EmergentCandidate('custody-c', 'capability', 'discovery',
        DiscoveryEnvelope(10, .1, 1, {'x': (0, 1)}),
        ReproductionProtocol('task', (1, 2), 'manifest', 'environment', ('observed',),
                             steps=({'action': 'read', 'args': {'path': 'allowed'}},)),
        'behavior', {'stability': .98}, metadata={'custody': {'origin': 'local'}})


def executors():
    return (StandardSyncExecutor(SubstrateProperties('sync', 1, 'atomic', 'cpu', sandbox_id='a')),
            AsyncIsolatedExecutor(SubstrateProperties('async', 10, 'batch', 'gpu', sandbox_id='b')))


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.c = candidate()

    def test_protocol_steps_bound(self):
        before = self.c.reproduction_steps.compute_protocol_hash()
        self.c.reproduction_steps.steps[0]['action'] = 'write'
        self.assertNotEqual(before, self.c.reproduction_steps.compute_protocol_hash())

    def test_nested_protocol_arguments_bound(self):
        before = self.c.compute_fingerprint()
        self.c.reproduction_steps.steps[0]['args']['path'] = 'elsewhere'
        self.assertNotEqual(before, self.c.compute_fingerprint())

    def test_metadata_bound(self):
        before = self.c.compute_fingerprint()
        self.c.metadata['custody']['origin'] = 'changed'
        self.assertNotEqual(before, self.c.compute_fingerprint())

    def test_source_none_empty_and_root_distinct(self):
        values = []
        for source in (None, '', 'root'):
            self.c.source = source
            values.append(self.c.compute_fingerprint())
        self.assertEqual(3, len(set(values)))

    def test_envelope_bounds_bound(self):
        before = self.c.compute_fingerprint()
        self.c.discovery_envelope.parameter_bounds['x'] = (0, 100)
        self.assertNotEqual(before, self.c.compute_fingerprint())

    def test_baseline_metrics_bound(self):
        before = self.c.compute_fingerprint()
        self.c.baseline_metrics['stability'] = 0
        self.assertNotEqual(before, self.c.compute_fingerprint())

    def test_observable_order_bound(self):
        p = self.c.reproduction_steps
        a = dataclasses.replace(p, required_observables=('a', 'b'))
        b = dataclasses.replace(p, required_observables=('b', 'a'))
        self.assertNotEqual(a.compute_protocol_hash(), b.compute_protocol_hash())

    def test_nan_rejected(self):
        self.c.baseline_metrics['stability'] = float('nan')
        with self.assertRaises(ValueError):
            CandidateSnapshot.capture(self.c)

    def test_non_json_rejected(self):
        self.c.metadata['object'] = object()
        with self.assertRaises(TypeError):
            CandidateSnapshot.capture(self.c)

    def test_snapshot_roundtrip(self):
        snap = CandidateSnapshot.capture(self.c)
        self.assertEqual(self.c, snap.materialize())
        self.assertIsInstance(snap.payload, bytes)

    def test_views_do_not_share_nested_state(self):
        snap = CandidateSnapshot.capture(self.c)
        a, b = snap.materialize(), snap.materialize()
        a.reproduction_steps.steps[0]['args']['path'] = 'changed'
        self.assertEqual('allowed', b.reproduction_steps.steps[0]['args']['path'])
        snap.verify(self.c)
        with self.assertRaises(CandidateCustodyError):
            snap.verify(a)

    def test_snapshot_fields_frozen(self):
        snap = CandidateSnapshot.capture(self.c)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            snap.payload = b'altered'

    def test_to_dict_detached_steps(self):
        d = self.c.reproduction_steps.to_dict()
        d['steps'][0]['args']['path'] = 'changed'
        self.assertEqual('allowed', self.c.reproduction_steps.steps[0]['args']['path'])


class ServiceRefusalTests(unittest.TestCase):
    """Migrated from simulation markers to actual native execution and signed custody."""
    def setUp(self):
        from euclid.emergence.substrate import engine
        from euclid.emergence.trusted_core.measured import RegisteredSubstrate
        from euclid.emergence.trusted_core.receipts import QualificationReceiptIssuer
        self.c = candidate()
        self.c.discovery_envelope = DiscoveryEnvelope(10, 0, 1)
        self.c.claimed_behavior_signature = 'lucas_step'
        self.c.reproduction_steps = ReproductionProtocol('native', (42,), 'manifest', engine.environment_hash(),
            ('accumulator',), steps=({'action':'init_state','args':{'accumulator':1}},) +
            tuple({'action':'lucas_step'} for _ in range(8)) +
            ({'action':'assert_observables','expected':{'accumulator':55}},))
        self.ka, self.kb = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
        self.a = StandardSyncExecutor(SubstrateProperties('sync',1,'atomic','cpu',sandbox_id='a'), signing_key=self.ka)
        self.b = AsyncIsolatedExecutor(SubstrateProperties('worker',10,'batch','cpu',sandbox_id='b'), signing_key=self.kb)
        bindings = {e.substrate_id: RegisteredSubstrate(e.properties, k.public_key(), e.backend,
            engine.artifact_hash(), engine.environment_hash(), 'manifest') for e,k in ((self.a,self.ka),(self.b,self.kb))}
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.key = Ed25519PrivateKey.generate()
        authorization = QualificationAuthorization(
            trusted_signers={("local-test-issuer", "local-contract-test"): self.key.public_key()},
            audience="custody-test", replay_path=Path(temp.name)/"replay.sqlite")
        issuer = QualificationReceiptIssuer(signing_key=Ed25519PrivateKey.generate(),issuer='eqs',audience='admit')
        self.service = EmergentQualificationService(authorization=authorization,
            registered_substrates=bindings, receipt_issuer=issuer)
        self.token = GovernanceToken.issue("local-contract-test", self.key, issuer="local-test-issuer",
            audience="custody-test", candidate_fingerprint=self.c.compute_fingerprint())

    def run_service(self, **changes):
        return self.service.qualify(self.c, self.a, self.b, self.token, **changes)

    def assert_refused(self, result, reason):
        self.assertIsInstance(result, RejectedQualification)
        self.assertIn(reason, result.reason)
        self.assertFalse(self.service.is_qualified('custody-c'))

    def test_builtin_reproduction_requires_real_measurement(self):
        for executor in (self.a, self.b):
            result = executor.reproduce(self.c.reproduction_steps)
            self.assertEqual('MEASURED', result.details['execution_kind'])
            self.assertTrue(result.observed)
            self.assertEqual(55,result.details['trials'][0]['state']['accumulator'])

    def test_stress_really_invokes_executor(self):
        _, details = stress_test(self.c, self.c.discovery_envelope.scale_margin(1.5), self.a)
        self.assertEqual('MEASURED', details['execution_kind'])
        self.assertTrue(details['executor_invoked'])
        self.assertEqual(8,details['execution']['details']['repetitions'])

    def test_actual_service_refuses_unregistered_results(self):
        from euclid.emergence.trusted_core.measured import MeasuredEvidenceVerifier
        self.service.evidence_verifier = MeasuredEvidenceVerifier()
        self.assert_refused(self.run_service(), 'unregistered substrate')

    def test_refusal_preserves_local_snapshot_custody(self):
        expected = self.c.compute_fingerprint()
        result = self.run_service(post_qualification_window=())
        entries = self.service.journal.get_entries()
        self.assertEqual(['QUALIFICATION_INPUT_SNAPSHOT', 'REJECT'], [e.action for e in entries])
        self.assertEqual(expected, entries[0].details['candidate_fingerprint'])
        self.assertEqual(expected, result.evidence['candidate_fingerprint'])
        self.assertEqual((True, None), self.service.journal.verify_chain())

    def test_missing_authority_refused_before_execution(self):
        with patch.object(self.a, 'reproduce', side_effect=RuntimeError('must not execute')) as call:
            with self.assertRaises(InvalidGovernanceTokenError):
                self.service.qualify(self.c, self.a, self.b)
            call.assert_not_called()

    def test_executor_protocol_mutation_refused_before_second_executor(self):
        original = self.a.reproduce
        def mutate(protocol, **kwargs):
            result = original(protocol, **kwargs)
            protocol.steps[0]['args']['accumulator'] = 2
            return result
        with patch.object(self.a, 'reproduce', mutate), patch.object(self.b, 'reproduce') as second:
            self.assert_refused(self.run_service(), 'changed during qualification')
            second.assert_not_called()
        self.assertEqual(1, self.c.reproduction_steps.steps[0]['args']['accumulator'])

    def test_source_mutation_refused_before_second_executor(self):
        original = self.a.reproduce
        def mutate(protocol, **kwargs):
            result = original(protocol, **kwargs)
            self.c.metadata['custody']['origin'] = 'replaced'
            return result
        with patch.object(self.a, 'reproduce', mutate), patch.object(self.b, 'reproduce') as second:
            self.assert_refused(self.run_service(), 'changed during qualification')
            second.assert_not_called()

    def test_claimed_measurement_marker_cannot_bypass_signature(self):
        original = self.a.reproduce
        def forge(protocol, **kwargs):
            result = original(protocol, **kwargs)
            result.details['execution_kind'] = 'SIMULATED'
            return result
        with patch.object(self.a, 'reproduce', forge):
            self.assert_refused(self.run_service(), 'lacks measured reproduction')

    def test_gate_two_mutation_rejected(self):
        def mutate(candidate, envelope, executor, **kwargs):
            result = stress_test(candidate, envelope, executor, **kwargs)
            candidate.discovery_envelope.parameter_bounds['x'] = (0, 99)
            return result
        with patch('euclid.emergence.trusted_core.qualification_service.stress_test', mutate):
            self.assert_refused(self.run_service(), 'changed during qualification')

    def test_explicit_empty_gate_three_window_is_not_pass(self):
        self.assert_refused(self.run_service(post_qualification_window=()), 'complete authenticated current window')


if __name__ == '__main__':
    unittest.main()
