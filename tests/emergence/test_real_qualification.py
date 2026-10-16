"""Real native execution, subprocess, Ed25519 and SQLite tests; no success-path mocks."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import copy
import json
import math
import os
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from euclid.emergence.models.candidate import DiscoveryEnvelope, EmergentCandidate, ReproductionProtocol
from euclid.emergence.models.qualification import QualifiedEmergent, RejectedQualification, SuspendedQualification
from euclid.emergence.models.substrate import SubstrateProperties
from euclid.emergence.substrate import engine
from euclid.emergence.substrate.executors import StandardSyncExecutor, AsyncIsolatedExecutor
from euclid.emergence.trusted_core.access_control import GovernanceToken, QualificationAuthorization, InvalidGovernanceTokenError
from euclid.emergence.trusted_core.measured import RegisteredSubstrate, MeasuredEvidenceVerifier
from euclid.emergence.trusted_core.custody import CandidateCustodyError
from euclid.emergence.trusted_core.qualification_service import EmergentQualificationService
from euclid.emergence.trusted_core.receipts import QualificationReceiptAdmission, QualificationReceiptIssuer, QualificationReceipt
from euclid.emergence.trusted_core.stress import stress_test


class MeasuredCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root, self.now = Path(self.temp.name), 2000000000
        self.officer, self.receipt_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
        self.ka, self.kb = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
        self.pa = SubstrateProperties('sync', 1, 'atomic', 'cpu', sandbox_id='parent')
        self.pb = SubstrateProperties('worker', 1, 'atomic', 'cpu', sandbox_id='worker')
        self.a = StandardSyncExecutor(self.pa, signing_key=self.ka)
        self.b = AsyncIsolatedExecutor(self.pb, signing_key=self.kb)
        self.registrations = {p.compute_id(): RegisteredSubstrate(p, key.public_key(), executor.backend,
            engine.artifact_hash(), engine.environment_hash(), 'manifest')
            for p, key, executor in ((self.pa, self.ka, self.a), (self.pb, self.kb, self.b))}
        self.c = self.make_candidate()
        self.auth = QualificationAuthorization(trusted_signers={('officer-issuer', 'officer'): self.officer.public_key()},
            audience='eqs', replay_path=self.root/'invoke.sqlite', clock=lambda: self.now)
        self.issuer = QualificationReceiptIssuer(signing_key=self.receipt_key, issuer='eqs-results',
            audience='admission', clock=lambda: self.now)
        self.service = self.make_service()

    def make_candidate(self, steps=8, expected=None):
        # Matches requested recurrence: a=b=1, eight additions -> 55, residue=1722.
        sequence = ({'action':'init_state'},) + ({'action':'lucas_step'},) * steps + (
            {'action':'modular_invariant'}, {'action':'assert_observables',
                'expected': expected or {'accumulator':55, 'invariant_residue':1722}, 'tolerance':0})
        protocol = ReproductionProtocol('native-lucas', (42,), 'manifest', engine.environment_hash(),
            ('accumulator', 'invariant_residue'), steps=copy.deepcopy(sequence))
        return EmergentCandidate('cand-lucas', 'recurrence-invariant', 'discovery',
            DiscoveryEnvelope(100, 0, 1), protocol, 'lucas_step')

    def make_service(self, **changes):
        args = dict(authorization=self.auth, registered_substrates=self.registrations, receipt_issuer=self.issuer)
        args.update(changes)
        return EmergentQualificationService(**args)

    def token(self):
        return GovernanceToken.issue('officer', self.officer, issuer='officer-issuer', audience='eqs',
            candidate_fingerprint=self.c.compute_fingerprint(), now=self.now)

    def qualify(self, **changes):
        args = dict(candidate=self.c, executor_A=self.a, executor_B=self.b, governance_token=self.token())
        args.update(changes)
        return self.service.qualify(**args)

    def verify(self, evidence, **changes):
        args = dict(fingerprint=self.c.compute_fingerprint(), challenge='challenge')
        args.update(changes)
        return self.service.evidence_verifier.verify(evidence, self.c.reproduction_steps, **args)

    def evidence(self, executor=None, **changes):
        args = dict(challenge='challenge', candidate_fingerprint=self.c.compute_fingerprint())
        args.update(changes)
        return (executor or self.a).reproduce(self.c.reproduction_steps, **args)

    def admission(self, **changes):
        args = dict(trusted_issuers={'eqs-results':self.receipt_key.public_key()}, audience='admission',
                    replay_path=self.root/'admit.sqlite', clock=lambda:self.now,
                    is_active=lambda receipt: self.service.is_receipt_active(receipt))
        args.update(changes)
        return QualificationReceiptAdmission(**args)

    def test_real_sync_state_and_latency(self):
        evidence = self.evidence()
        self.assertTrue(evidence.observed)
        self.assertEqual(55, evidence.details['trials'][-1]['state']['accumulator'])
        self.assertEqual(1722, evidence.details['trials'][-1]['state']['invariant_residue'])
        self.assertGreater(evidence.details['elapsed_ms'], 0)
        self.assertEqual(1, evidence.execution_metrics['stability'])
        self.verify(evidence)

    def test_requested_two_step_example(self):
        self.c = self.make_candidate(2, {'accumulator':3,'invariant_residue':110})
        self.assertTrue(self.evidence().observed)

    def test_real_worker_disjoint_pid(self):
        evidence = self.evidence(self.b)
        self.assertTrue(evidence.observed, evidence.details)
        self.assertNotEqual(os.getpid(), evidence.details['trials'][0]['pid'])
        self.verify(evidence)

    def test_missing_observable_refused(self):
        p = self.c.reproduction_steps
        self.c.reproduction_steps = replace(p, steps=p.steps[:-2] + (p.steps[-1],))
        evidence = self.evidence()
        self.assertFalse(evidence.observed)
        self.assertNotIn('invariant_residue', evidence.details['trials'][0]['state'])

    def test_wrong_observable_refused(self):
        self.c.reproduction_steps.steps[-1]['expected']['accumulator'] = 999
        self.assertFalse(self.evidence().observed)

    def test_absolute_tolerance(self):
        step = self.c.reproduction_steps.steps[-1]
        step['expected']['accumulator'], step['tolerance'] = 55.125, .125
        self.assertTrue(self.evidence().observed)
        step['tolerance'] = .1249
        self.assertFalse(self.evidence().observed)

    def test_unknown_action_fails_both_backends(self):
        self.c.reproduction_steps.steps[1]['action'] = 'not-an-action'
        for executor in (self.a, self.b):
            self.assertFalse(self.evidence(executor).observed)

    def test_handler_error_fails_closed(self):
        self.c.reproduction_steps.steps[-2]['args'] = {'modulus':0}
        self.assertFalse(self.evidence().observed)

    def test_nonfinite_inputs_fail_closed(self):
        for value in (float('nan'), float('inf'), True, -1):
            self.c.reproduction_steps.steps[-1]['tolerance'] = value
            with self.subTest(value=value):
                # Nonfinite protocol hashing itself fails before execution.
                try: result = self.evidence()
                except ValueError: continue
                self.assertFalse(result.observed)

    def test_no_signer_no_measurement_authority(self):
        executor = StandardSyncExecutor(self.pa)
        self.assertFalse(self.evidence(executor).observed)

    def test_no_failure_switch(self):
        with self.assertRaises(TypeError): StandardSyncExecutor(self.pa, simulate_failure=True)

    def test_stability_is_outputs_not_latency(self):
        self.assertEqual(1, engine.stability([[0, -4, 3], [0, -4, 3]]))
        expected = max(0, 1 - math.sqrt(2) / (2 + 1e-12))
        self.assertAlmostEqual(expected, engine.stability([[1], [3]]))
        self.assertEqual(0, engine.stability([[1]]))
        self.assertEqual(0, engine.stability([[-1], [1]]))

    def test_every_repetition_checked(self):
        evidence = self.evidence()
        trials = evidence.details['trials']
        trials[0]['state']['accumulator'] = 999
        summary = engine.summarize(asdict(self.c.reproduction_steps), trials, 5)
        self.assertFalse(summary['observed'])
        self.assertEqual(.8, summary['reproduction_rate'])

    def test_evidence_tamper_refused(self):
        for field in ('observed', 'execution_metrics', 'details'):
            evidence = self.evidence()
            if field == 'observed': evidence.observed = False
            elif field == 'execution_metrics': evidence.execution_metrics['entropy'] = 0
            else: evidence.details['trials'][0]['state']['accumulator'] = 0
            with self.subTest(field=field), self.assertRaises(CandidateCustodyError): self.verify(evidence)

    def test_evidence_wrong_key_refused(self):
        evidence = self.evidence()
        evidence.details['custody_signature'] = self.kb.sign(evidence.signing_body()).hex()
        with self.assertRaises(CandidateCustodyError): self.verify(evidence)

    def test_challenge_replay_refused(self):
        with self.assertRaises(CandidateCustodyError): self.verify(self.evidence(), challenge='new')

    def test_cross_candidate_evidence_refused(self):
        with self.assertRaises(CandidateCustodyError): self.verify(self.evidence(), fingerprint='0'*64)

    def test_environment_manifest_binding(self):
        for key in ('manifest_hash','environment_snapshot_hash'):
            old = self.c.reproduction_steps
            self.c.reproduction_steps = replace(old, **{key:'mismatch'})
            with self.subTest(key=key), self.assertRaises(CandidateCustodyError): self.verify(self.evidence())
            self.c.reproduction_steps = old

    def test_full_pipeline_real_success(self):
        outcome = self.qualify()
        self.assertIsInstance(outcome, QualifiedEmergent, outcome)
        self.assertTrue(self.service.is_qualified(self.c.candidate_id))
        self.assertEqual(8, outcome.gate_2_stress_envelope['execution']['details']['repetitions'])
        self.assertEqual('isolated_worker', outcome.gate_1_reproduction['executor_B']['details']['backend'])
        self.assertEqual(10, len(outcome.gate_3_monitoring['window_digests']))
        self.assertEqual(128, len(outcome.governance_signature))
        self.assertEqual(outcome.certification_token, outcome.qualification_receipt)

    def test_same_substrate_refused(self):
        outcome = self.qualify(executor_B=self.a)
        self.assertIsInstance(outcome, RejectedQualification)
        self.assertIn('INSUFFICIENT_SUBSTRATE_DIVERSITY', outcome.reason)

    def test_labels_alone_do_not_prove_diversity(self):
        self.registrations[self.pb.compute_id()] = replace(self.registrations[self.pb.compute_id()], backend='in_process')
        self.service = self.make_service()
        outcome = self.qualify()
        self.assertIsInstance(outcome, RejectedQualification)
        self.assertIn('INSUFFICIENT_SUBSTRATE_DIVERSITY', outcome.reason)

    def test_unregistered_substrate_refused(self):
        self.service = self.make_service(registered_substrates={})
        self.assertIn('unregistered substrate', self.qualify().reason)

    def test_no_receipt_signer_refused(self):
        self.service = self.make_service(receipt_issuer=None)
        self.assertIsInstance(self.qualify(), RejectedQualification)

    def test_stress_is_real_and_ceil_scaled(self):
        ok, details = stress_test(self.c, self.c.discovery_envelope.scale_margin(1.5), self.a)
        self.assertTrue(ok)
        self.assertTrue(details['executor_invoked'])
        self.assertEqual(8, details['execution']['details']['repetitions'])
        self.assertIn('noise_injection', details['untested_axes'])

    def test_stress_failure_on_real_budget(self):
        self.c.discovery_envelope = DiscoveryEnvelope(100, 0, 1e-12)
        outcome = self.qualify()
        self.assertIsInstance(outcome, RejectedQualification)
        self.assertIn('Gate 2', outcome.gate_failed)

    def test_entropy_tripwire_from_real_actions(self):
        self.service = self.make_service(entropy_tripwire=.1)
        outcome = self.qualify()
        self.assertIsInstance(outcome, SuspendedQualification)
        self.assertEqual('TRIPWIRE_BREACH', outcome.reason)
        self.assertFalse(self.service.is_qualified(self.c.candidate_id))

    def test_supplied_empty_or_foreign_window_refused(self):
        self.assertIsInstance(self.qualify(post_qualification_window=()), RejectedQualification)
        # An empty manually supplied window never substitutes for the real complete window.

    def test_authorization_consumed_on_qualification(self):
        token = self.token()
        self.assertIsInstance(self.qualify(governance_token=token), QualifiedEmergent)
        with self.assertRaises(InvalidGovernanceTokenError): self.qualify(governance_token=token)

    def test_receipt_single_use_and_restart(self):
        outcome = self.qualify()
        for i in range(2):
            admission = self.admission()
            if i == 0:
                receipt = admission.consume(outcome.qualification_receipt, candidate=self.c, gates_digest=outcome.gates_digest)
                self.assertEqual(self.c.candidate_id, receipt.candidate_id)
            else:
                with self.assertRaises(PermissionError):
                    admission.consume(outcome.qualification_receipt, candidate=self.c, gates_digest=outcome.gates_digest)

    def test_receipt_concurrent_exactly_once(self):
        outcome = self.qualify()
        verifiers = [self.admission(), self.admission()]
        def consume(verifier):
            try:
                verifier.consume(outcome.qualification_receipt, candidate=self.c, gates_digest=outcome.gates_digest)
                return True
            except PermissionError: return False
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual([False, True], sorted(pool.map(consume, verifiers)))

    def test_receipt_fields_tamper_fail_closed(self):
        outcome = self.qualify()
        original = json.loads(outcome.qualification_receipt)
        for field, value in {'audience':'other','candidate_fingerprint':'0'*64,'candidate_id':'other',
                'issuer':'other','gates_digest':'0'*64,'nonce':'0'*64,'expires_at':self.now+200,
                'operation':'qualify','schema':'other','signature':'0'*128}.items():
            data = {**original, field:value}
            with self.subTest(field=field), self.assertRaises(PermissionError):
                self.admission().consume(json.dumps(data), candidate=self.c, gates_digest=outcome.gates_digest)

    def test_receipt_expiry_and_clock_rollback(self):
        outcome = self.qualify()
        self.now += 60
        with self.assertRaises(PermissionError):
            self.admission().consume(outcome.qualification_receipt, candidate=self.c, gates_digest=outcome.gates_digest)

    def test_receipt_revocation_and_unavailable_ledger(self):
        outcome = self.qualify()
        verifier = self.admission(trusted_issuers={'eqs-results':self.ka.public_key()})
        with self.assertRaises(PermissionError):
            verifier.consume(outcome.qualification_receipt, candidate=self.c, gates_digest=outcome.gates_digest)
        verifier = self.admission()
        verifier.path.unlink()
        verifier.path.mkdir()
        with self.assertRaises(PermissionError):
            verifier.consume(outcome.qualification_receipt, candidate=self.c, gates_digest=outcome.gates_digest)

    def test_invocation_token_not_qualification_receipt(self):
        with self.assertRaises(PermissionError):
            self.admission().consume(json.dumps(asdict(self.token())), candidate=self.c, gates_digest='0'*64)

    def test_registry_requires_distinct_substrate_keys(self):
        bindings = dict(self.registrations)
        bindings[self.pb.compute_id()] = replace(bindings[self.pb.compute_id()], public_key=self.ka.public_key())
        with self.assertRaises(ValueError): MeasuredEvidenceVerifier(bindings)

    def test_actual_worker_timeout_fails_closed(self):
        executor = AsyncIsolatedExecutor(self.pb, signing_key=self.kb, timeout_seconds=1e-9)
        evidence = self.evidence(executor)
        self.assertFalse(evidence.observed)
        self.assertEqual('UNAVAILABLE', evidence.details['execution_kind'])
        self.assertIn('TimeoutExpired', evidence.details['error'])

    def test_incomplete_signed_trials_refused(self):
        evidence = self.evidence()
        evidence.details['trials'].pop()
        body = dict(evidence.details)
        body.pop('custody_signature')
        evidence.signed_journal_hash = engine.digest(body)
        evidence.details['custody_signature'] = self.ka.sign(evidence.signing_body()).hex()
        with self.assertRaises(CandidateCustodyError): self.verify(evidence)

    def test_receipt_revoked_by_suspension(self):
        outcome = self.qualify()
        self.service.suspend(self.c, {'reason':'operator suspension'})
        with self.assertRaises(PermissionError):
            self.admission().consume(outcome.qualification_receipt, candidate=self.c, gates_digest=outcome.gates_digest)

    def test_receipt_clock_rollback(self):
        first = self.qualify()
        self.admission().consume(first.qualification_receipt, candidate=self.c, gates_digest=first.gates_digest)
        self.now -= 1
        receipt = self.issuer.issue(self.c, {'new':'gates'})
        # Re-sign an otherwise valid older receipt and host-approve it to isolate the clock custody check.
        with self.assertRaises(PermissionError):
            self.admission(is_active=lambda r: True).consume(receipt.encode(), candidate=self.c,
                                                            gates_digest=receipt.gates_digest)

    def test_qualification_case_preserves_real_executor_bindings(self):
        from euclid.emergence.integration import QualificationCase
        case = QualificationCase.capture(self.c, self.a, self.b)
        self.assertIs(case.executor_A, self.a)
        self.assertIs(case.executor_B, self.b)
        self.assertEqual((), case.observation_window)
        self.assertEqual(self.c.compute_fingerprint(), case.candidate.fingerprint)

    def test_every_numeric_trajectory_affects_stability(self):
        # Latency does not enter this metric, but a transient trajectory coordinate does.
        self.assertLess(engine.stability([[1, 2, 3], [1, 100, 3], [1, 2, 3]]), .70)

    def test_receipt_restarted_service_missing_state_refuses(self):
        outcome = self.qualify()
        self.service = self.make_service()
        with self.assertRaises(PermissionError):
            self.admission().consume(outcome.qualification_receipt, candidate=self.c, gates_digest=outcome.gates_digest)

    def test_only_one_executor_fails_closed(self):
        outcome = self.qualify(executor_B=None)
        self.assertIsInstance(outcome, RejectedQualification)
        self.assertIn('INSUFFICIENT_SUBSTRATE_DIVERSITY', outcome.reason)
