"""Non-mining regressions: synthetic fixtures, not deployment qualification."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from hyba_services.catalogue import capture_notebook
from hyba_services.core import ProofService
from hyba_services.platform import ModelRegistry, PromotionBlocked


class EnterpriseAuditGuardrails(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.registry = ModelRegistry(self.tmp.name)
        self.evidence = {k: 'synthetic-fixture' for k in (
            'dataset_snapshot_hash', 'code_and_environment_hash',
            'backend_certificate', 'evaluation_suite', 'baselines')}
        self.sha = self.registry.register(b'fixture', {}, self.evidence, 'tenant')

    def state(self):
        return json.loads((Path(self.tmp.name)/'tenant'/self.sha/'state.json').read_text())['state']

    def test_empty_checks_cannot_promote(self):
        with self.assertRaises(PromotionBlocked):
            self.registry.promote('tenant', self.sha, 'EVALUATED', ())
        self.assertEqual(self.state(), 'DRAFT')

    def test_empty_generator_cannot_promote(self):
        with self.assertRaises(PromotionBlocked):
            self.registry.promote('tenant', self.sha, 'EVALUATED', iter(()))

    def test_truthy_non_boolean_check_is_not_approval(self):
        with self.assertRaises(PromotionBlocked):
            self.registry.promote('tenant', self.sha, 'EVALUATED', [lambda *_: 'PASS'])

    def test_cannot_skip_to_deployment(self):
        with self.assertRaises(PromotionBlocked):
            self.registry.promote('tenant', self.sha, 'DEPLOYED', [lambda *_: True])
        self.assertEqual(self.state(), 'DRAFT')

    def test_sequential_promotion(self):
        for target in ('EVALUATED', 'APPROVED', 'DEPLOYED', 'RETIRED'):
            self.registry.promote('tenant', self.sha, target, iter([lambda *_: True]))
            self.assertEqual(self.state(), target)

    def test_cannot_move_backwards(self):
        for target in ('EVALUATED', 'APPROVED'):
            self.registry.promote('tenant', self.sha, target, [lambda *_: True])
        with self.assertRaises(PromotionBlocked):
            self.registry.promote('tenant', self.sha, 'EVALUATED', [lambda *_: True])
        self.assertEqual(self.state(), 'APPROVED')

    def test_failed_check_leaves_state_unchanged(self):
        with self.assertRaises(PromotionBlocked):
            self.registry.promote('tenant', self.sha, 'EVALUATED', [lambda *_: False])
        self.assertEqual(self.state(), 'DRAFT')

    def test_exception_leaves_state_unchanged(self):
        def fail(*_):
            raise RuntimeError('fixture failure')
        with self.assertRaises(RuntimeError):
            self.registry.promote('tenant', self.sha, 'EVALUATED', [fail])
        self.assertEqual(self.state(), 'DRAFT')

    def test_approval_still_requires_evidence(self):
        sha = self.registry.register(b'other', {}, {}, 'tenant')
        self.registry.promote('tenant', sha, 'EVALUATED', [lambda *_: True])
        with self.assertRaises(PromotionBlocked):
            self.registry.promote('tenant', sha, 'APPROVED', [lambda *_: True])

    def test_notebook_capture_does_not_claim_replay(self):
        result = capture_notebook({'cells': ['1+1'], 'outputs': [999]}, {'python': 'fixture'})
        self.assertFalse(result['reproducible'])
        self.assertEqual(result['replay_status'], 'NOT_RUN')

    def test_capture_preserves_provenance(self):
        session = {'cells': ['1+1'], 'outputs': [2], 'data_references': ['fixture']}
        first = capture_notebook(session, {'python': 'fixture'})
        second = capture_notebook(session, {'python': 'fixture'})
        self.assertEqual(first['session_hash'], second['session_hash'])
        self.assertEqual(first['outputs'], [2])
        self.assertEqual(first['data_refs'], ['fixture'])

    def test_empty_invariants_cannot_be_certified(self):
        obj = SimpleNamespace(object_id='fixture', residual_boundary=0)
        with self.assertRaises(ValueError):
            ProofService(b'x'*32).certify('identity', obj, obj, {}, {})

    def test_truthy_non_boolean_is_not_invariant_proof(self):
        obj = SimpleNamespace(object_id='fixture', residual_boundary=0)
        with self.assertRaises(ValueError):
            ProofService(b'x'*32).certify('identity', obj, obj, {'same': lambda *_: 'PASS'}, {})

    def test_literal_invariant_success_still_signs(self):
        obj = SimpleNamespace(object_id='fixture', residual_boundary=0)
        proof = ProofService(b'x'*32).certify('identity', obj, obj, {'same': lambda *_: True}, {})
        self.assertEqual(proof.invariant_results, (True,))
        self.assertTrue(proof.signature)

if __name__ == '__main__':
    unittest.main()
