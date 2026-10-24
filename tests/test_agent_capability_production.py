"""Actual production-factory/restart tests, not full enterprise qualification.

Owner dependencies not present remain unavailable; no actuator is exercised.
Explicit injected ledger records below are replay fault fixtures, not claims of
real recovery. The cognitive episode and diagnostic records are actual outputs.
"""
import atexit
from dataclasses import asdict
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from euclid.runtime import EuclidRuntime
from euclid.memory_database import MemoryDatabase
from salamander.control_plane import EvidenceLedger, FailClosed, RecoveryPlan
from salamander.models import ActionKind, ActionRequest


class ProductionRestartTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def runtime(self, name='runtime', **kwargs):
        runtime = EuclidRuntime.production(creator_id='owner', state_dir=self.root/name, **kwargs)
        self.addCleanup(runtime.close)
        return runtime

    def checkpoint(self, runtime):
        path = self.root/'checkpoint.json'
        runtime.save(path)
        return path

    def restore(self, path, **kwargs):
        runtime = EuclidRuntime.restore(path, state_dir=self.root/'restored', **kwargs)
        self.addCleanup(runtime.close)
        return runtime

    def test_actual_cognitive_episode_remains_in_saved_evidence_after_restore(self):
        original = self.runtime()
        path = self.checkpoint(original)
        restored = self.restore(path)
        self.assertIs(restored.cognition.evidence, restored.evidence)
        self.assertIs(restored.learning.evidence, restored.evidence)
        state = restored.solve_repository_problem({
            'problem_id': 'restart-arithmetic', 'goal': 'inspect arithmetic identity',
            'structure': ['arithmetic'], 'initial_code': 'def candidate(x):\n    return x\n',
            'strategy': 'primitive-compose',
        })
        self.assertGreater(len(state.transitions), 0)
        records = [r for r in restored.evidence.records if r.payload.get('problem_id') == state.problem_id]
        self.assertGreater(len(records), 0)
        next_path = self.checkpoint(restored)
        again = self.restore(next_path)
        self.assertTrue(any(r.payload.get('problem_id') == state.problem_id for r in again.evidence.records))
        again.evidence.verify()

    def test_actual_diagnostic_history_continues_without_duplicate_mirrors(self):
        original = self.runtime(tenant_id='tenant-a')
        original.review_repository_capabilities(tenant_id='tenant-a', target='sample.py', source='x = 1')
        records = original.autonomic.ledger.records
        restored = self.restore(self.checkpoint(original), tenant_id='tenant-a')
        self.assertEqual(restored.autonomic.ledger.records, records)
        self.assertIs(restored.discovery_optimisation.control_plane, restored.autonomic)
        restored.review_repository_capabilities(tenant_id='tenant-a', target='sample.py', source='x = 2')
        mirror = [dict(r.payload) for r in restored.evidence.records if r.kind == 'salamander-action']
        self.assertEqual(mirror, list(restored.autonomic.ledger.records))
        self.assertEqual(len(mirror), len(records) + 1)
        self.assertTrue(restored.autonomic.ledger.verify())
        with self.assertRaisesRegex(ValueError, 'tenant'):
            restored.review_repository_capabilities(tenant_id='tenant-b', target='sample.py', source='x = 3')

    def test_tenant_mismatch_refused_before_production_startup(self):
        path = self.checkpoint(self.runtime(tenant_id='tenant-a'))
        with patch.object(EuclidRuntime, 'production') as factory:
            with self.assertRaisesRegex(ValueError, 'expected tenant'):
                self.restore(path, tenant_id='tenant-b')
            factory.assert_not_called()

    def test_legacy_checkpoint_without_tenant_or_mirror_restores_closed(self):
        restored = self.restore(self.checkpoint(self.runtime()))
        self.assertIsNone(restored._service_tenant_id)
        self.assertFalse(restored._actuation_ready)
        self.assertEqual(restored.autonomic.ledger.records, ())

    def test_invalid_tenant_is_rejected_before_opening_database(self):
        with patch('euclid.runtime.MemoryDatabase') as database:
            with self.assertRaisesRegex(ValueError, 'tenant_id'):
                self.runtime(tenant_id='   ')
            database.assert_not_called()

    def test_restored_control_plane_cannot_act_without_fresh_authority(self):
        restored = self.restore(self.checkpoint(self.runtime()))
        request = ActionRequest('new', ActionKind.REQUALIFY, 'requalify-organ',
                                'owner', 'subject', 'qualification', {},
                                idempotency_key='new', actor_id='owner')
        with self.assertRaisesRegex(FailClosed, 'AUTHORIZER_UNAVAILABLE'):
            restored.autonomic.execute(request)

    def test_corrupt_mirror_refused_before_production_startup(self):
        runtime = self.runtime()
        runtime.evidence.append('salamander-action', {
            'schema': 'salamander.autonomic.action.v1', 'kind': 'injected-corrupt',
            'payload': {}, 'at_ns': 1, 'previous_sha256': '0'*64, 'evidence_sha256': '0'*64,
        })
        path = self.checkpoint(runtime)
        with patch.object(EuclidRuntime, 'production') as factory:
            with self.assertRaises(FailClosed):
                self.restore(path)
            factory.assert_not_called()

    def test_injected_replay_fixture_restores_budget_uncertainty_and_circuit(self):
        runtime = self.runtime(tenant_id='tenant-a')
        ledger = runtime.autonomic.ledger
        # Fault-injection evidence, deliberately NOT executed recovery proof.
        for i in range(2):
            ledger.append('recovery-budget-reserved', {'tenant_id':'tenant-a','target':'subject'}, at_ns=i)
        request = ActionRequest('uncertain', ActionKind.REQUALIFY, 'requalify-organ',
                                'tenant-a', 'subject', 'injected-replay', {},
                                idempotency_key='same', actor_id='actor')
        ledger.append('action-proposed', asdict(request), at_ns=3)
        ledger.append('circuit-state', {'key':'tenant-a:subject', 'failure_limit':2,
            'cooldown_ns':100, 'state':'OPEN', 'failures':2, 'opened_at_ns':4}, at_ns=4)
        restored = self.restore(self.checkpoint(runtime), tenant_id='tenant-a')
        plane = restored.autonomic
        self.assertEqual(plane._recoveries[('tenant-a','subject')], 2)
        self.assertEqual(plane.circuits['tenant-a:subject'].state.value, 'OPEN')
        with self.assertRaisesRegex(FailClosed, 'uncertain'):
            plane.execute(request)
        with self.assertRaisesRegex(FailClosed, 'budget exhausted'):
            plane.recover(RecoveryPlan('again','tenant-a','subject',(),1,time.time_ns()+10**9))
        self.assertFalse(restored._actuation_ready)

    def test_primitive_search_repository_is_runtime_local_and_shared_between_engines(self):
        first = self.runtime('one')
        second = self.runtime('two')
        for runtime in (first, second):
            self.assertIs(runtime.cognition.skills.mcts.repository, runtime.cognition.skills.evolution.repository)
            self.assertEqual(Path(runtime.cognition.skills.mcts.repository.storage_path),
                             runtime.state_dir/'primitive_repository.json')
        self.assertNotEqual(first.cognition.skills.mcts.repository.storage_path,
                            second.cognition.skills.mcts.repository.storage_path)

    def test_failed_startup_closes_real_database_without_saving_partial_store(self):
        databases = []
        def database(path):
            result = MemoryDatabase(path)
            databases.append(result)
            return result
        with patch('euclid.runtime.MemoryDatabase', side_effect=database), \
             patch.object(EuclidRuntime, '_compose_cognition', side_effect=RuntimeError('injected startup failure')), \
             patch('atexit.unregister', wraps=atexit.unregister) as unregister:
            with self.assertRaisesRegex(RuntimeError, 'injected startup'):
                self.runtime('failed')
            self.assertGreaterEqual(unregister.call_count, 1)
        self.assertEqual(len(databases), 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            databases[0]._connection.execute('SELECT 1')

    def test_close_unregisters_owned_store_exit_writer_and_is_idempotent(self):
        runtime = self.runtime()
        with patch('atexit.unregister', wraps=atexit.unregister) as unregister:
            runtime.close()
            runtime.close()
            unregister.assert_called_once_with(runtime.learning.store._flush_on_exit)
        with self.assertRaises(sqlite3.ProgrammingError):
            runtime.learning.memory_database._connection.execute('SELECT 1')

    def test_semantically_invalid_replay_closes_database_after_restore_failure(self):
        runtime = self.runtime()
        runtime.autonomic.ledger.append('action-result', {'action_id':'orphan'}, at_ns=1)
        path = self.checkpoint(runtime)
        databases = []
        def database(path):
            result = MemoryDatabase(path)
            databases.append(result)
            return result
        with patch('euclid.runtime.MemoryDatabase', side_effect=database):
            with self.assertRaisesRegex(FailClosed, 'no replayable proposal'):
                self.restore(path)
        self.assertEqual(len(databases), 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            databases[0]._connection.execute('SELECT 1')

    def test_checkpoint_restores_actual_diagnostics_in_fresh_python_process(self):
        runtime = self.runtime(tenant_id='tenant-a')
        runtime.review_repository_capabilities(tenant_id='tenant-a', target='sample.py', source='x=1')
        path = self.checkpoint(runtime)
        expected = runtime.autonomic.ledger.head
        code = '''import sys
from euclid.runtime import EuclidRuntime
r=EuclidRuntime.restore(sys.argv[1],state_dir=sys.argv[2],tenant_id='tenant-a')
try:
 assert r.autonomic.ledger.head==sys.argv[3]
 assert r.cognition.evidence is r.evidence
 assert not r._actuation_ready
 r.review_repository_capabilities(tenant_id='tenant-a',target='sample.py',source='x=2')
 assert r.autonomic.ledger.verify()
 r.evidence.verify()
 print('FRESH_PROCESS_RESTORE_PASS')
finally:r.close()
'''
        result = subprocess.run([sys.executable,'-c',code,str(path),str(self.root/'process'),expected],
                                capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('FRESH_PROCESS_RESTORE_PASS', result.stdout)


class MirrorContractTest(unittest.TestCase):
    def test_verified_mirror_has_defensive_copy_and_does_not_reemit_history(self):
        source = EvidenceLedger()
        source.append('known', {'value': 1}, at_ns=1)
        records = list(source.records)
        seen = []
        rebuilt = EvidenceLedger.from_records(records, sink=seen.append)
        records[0]['payload']['value'] = 2
        self.assertTrue(rebuilt.verify())
        self.assertEqual(seen, [])
        rebuilt.append('next', {}, at_ns=2)
        self.assertEqual(len(seen), 1)

    def test_reordered_or_tampered_mirror_is_refused(self):
        source = EvidenceLedger()
        for i in range(2): source.append('known', {'value': i}, at_ns=i)
        with self.assertRaises(FailClosed): EvidenceLedger.from_records(reversed(source.records))
        records = list(source.records)
        records[0]['payload']['value'] = 100
        with self.assertRaises(FailClosed): EvidenceLedger.from_records(records)


if __name__ == '__main__': unittest.main()
