"""Real constructors, persistence and adversarial boundaries; no startup doubles.

These qualify the bounded in-process review surface, NOT a deployed service or
production organism with all specialist owners and canonical remote custody.
"""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from euclid import EuclidRuntime
from euclid.evidence import EvidenceChain
from salamander import AgentCapabilitySuite
from salamander.control_plane import EvidenceLedger, FailClosed
from salamander.models import ActionKind, ActionRequest
from salamander.runtime import DurableEvidenceLedger

ROOT = Path(__file__).resolve().parents[1]


class RealRuntimeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.runtime = EuclidRuntime(creator_id='owner', state_dir=self.directory.name)
        self.addCleanup(self.runtime.close)

    def compose(self):
        self.runtime.compose_organism(tenant_id='tenant-a')
        return self.runtime

    def review(self, runtime=None, **overrides):
        args = dict(tenant_id='tenant-a', target='src/example.py', source='x=1')
        args.update(overrides)
        return (runtime or self.runtime).review_repository_capabilities(**args)

    def test_normal_constructor_and_canonical_composition(self):
        runtime = self.compose()
        report = self.review()
        self.assertEqual(len(report['capabilities']), 10)
        self.assertIs(runtime._agent_capabilities.ledger, runtime.autonomic.ledger)
        self.assertEqual(report['actuation'], 'NOT_PERFORMED')
        records = [r for r in runtime.evidence.records if r.kind == 'salamander-action']
        self.assertEqual(records[-1].payload['evidence_sha256'], report['evidence_ref'])
        self.assertTrue(runtime.autonomic.ledger.verify())
        runtime.evidence.verify()

    def test_uncomposed_real_runtime_refuses(self):
        with self.assertRaisesRegex(RuntimeError, 'not composed'):
            self.review()

    def test_cross_tenant_refused_without_evidence_append(self):
        runtime = self.compose()
        before = runtime.autonomic.ledger.head
        with self.assertRaisesRegex(ValueError, 'tenant'):
            self.review(tenant_id='tenant-b')
        self.assertEqual(before, runtime.autonomic.ledger.head)

    def test_closed_real_runtime_refuses(self):
        self.compose().close()
        with self.assertRaisesRegex(RuntimeError, 'closed'):
            self.review()

    def test_recomposition_drops_old_suite_binding(self):
        runtime = self.compose()
        self.review()
        old = runtime._agent_capabilities
        runtime.compose_organism(tenant_id='tenant-b')
        self.review(tenant_id='tenant-b')
        self.assertIsNot(old, runtime._agent_capabilities)
        self.assertIs(runtime._agent_capabilities.ledger, runtime.autonomic.ledger)
        with self.assertRaises(ValueError):
            self.review()

    def test_no_source_execution(self):
        runtime = self.compose()
        marker = Path(self.directory.name) / 'must-not-exist'
        self.review(source=f"open({str(marker)!r}, 'w').write('executed')")
        self.assertFalse(marker.exists())
        self.assertFalse(runtime._actuation_ready)

    def test_diagnostics_do_not_authorize_owner_action(self):
        runtime = self.compose()
        self.review()
        request = ActionRequest('attempt', ActionKind.REPLAN, 'unconfigured',
                                'tenant-a', 'worker', 'test', {'max_attempts': 1},
                                idempotency_key='attempt', actor_id='owner')
        with self.assertRaises(FailClosed):
            runtime.autonomic.execute(request)
        self.assertTrue(runtime.autonomic.ledger.verify())

    def test_real_runtime_concurrent_reviews_and_observations(self):
        runtime = self.compose()
        def writer(i):
            if i % 2:
                return runtime.autonomic.observe(())
            return self.review(source=f'x={i}')
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(writer, range(80)))
        self.assertTrue(runtime.autonomic.ledger.verify())
        runtime.evidence.verify()
        self.assertEqual(sum(r['kind'] == 'agent-capability-review'
                             for r in runtime.autonomic.ledger.records), 40)

    def test_checkpoint_evidence_survives_fresh_process(self):
        runtime = self.compose()
        report = self.review()
        checkpoint = Path(self.directory.name) / 'checkpoint.json'
        runtime.save(checkpoint)
        # This intentionally tests persisted evidence, not full production restore.
        code = '''import json,sys
from euclid.contracts import domain_hash
from euclid.evidence import EvidenceChain
p=json.load(open(sys.argv[1])); seal=p.pop('seal')
assert seal==domain_hash('euclid.runtime-checkpoint.seal.v1',p)
e=EvidenceChain.from_payload(p['evidence']); e.verify()
r=[x for x in e.records if x.kind=='salamander-action']
assert r[-1].payload['evidence_sha256']==sys.argv[2]
print('fresh-process checkpoint evidence verified')
'''
        completed = subprocess.run([sys.executable, '-c', code, str(checkpoint), report['evidence_ref']],
                                   cwd=ROOT, check=True, text=True, capture_output=True, timeout=30)
        self.assertIn('verified', completed.stdout)

    def test_checkpoint_evidence_tampering_refused(self):
        self.compose()
        self.review()
        payload = copy.deepcopy(self.runtime.snapshot()['evidence'])
        payload['records'][-1]['payload']['kind'] = 'tampered'
        with self.assertRaises(ValueError):
            EvidenceChain.from_payload(payload)


class EvidenceConcurrencyTests(unittest.TestCase):
    def test_reentrant_sink_append_refused_without_chain_corruption(self):
        ledger = EvidenceLedger()
        ledger._sink = lambda record: ledger.append('recursive', {}, at_ns=0)
        with self.assertRaisesRegex(FailClosed, 'reentrant'):
            ledger.append('outer', {}, at_ns=1)
        self.assertEqual(ledger.records, ())
        self.assertTrue(ledger.verify())
        ledger._sink = None
        ledger.append('retry', {}, at_ns=2)
        self.assertTrue(ledger.verify())

    def test_multiple_suites_and_owner_writers_share_one_ledger(self):
        ledger = EvidenceLedger()
        suites = [AgentCapabilitySuite(ledger) for _ in range(4)]
        def writer(i):
            if i % 5 == 0:
                return ledger.append('owner-observation', {'i': i}, at_ns=i)
            return suites[i % 4].inspect(tenant_id='a', target='x.py', source=f'x={i}')['evidence_ref']
        with ThreadPoolExecutor(max_workers=10) as pool:
            refs = list(pool.map(writer, range(160)))
        self.assertEqual(len(set(refs)), 160)
        self.assertTrue(ledger.verify())
        restored = EvidenceLedger.from_payload(ledger.to_payload())
        self.assertEqual(restored.head, ledger.head)

    def test_sink_failure_does_not_commit_in_memory(self):
        def failing_sink(_record):
            raise OSError('sink unavailable')
        ledger = EvidenceLedger(sink=failing_sink)
        with self.assertRaises(OSError):
            AgentCapabilitySuite(ledger).inspect(tenant_id='a', target='x.py', source='pass')
        self.assertEqual(ledger.records, ())
        self.assertEqual(ledger.head, '0' * 64)
        self.assertTrue(ledger.verify())

    def test_durable_concurrent_append_and_fresh_process_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ledger.jsonl'
            ledger = DurableEvidenceLedger(path)
            def writer(i):
                return ledger.append('concurrent-test', {'i': i}, at_ns=i)
            with ThreadPoolExecutor(max_workers=8) as pool:
                refs = list(pool.map(writer, range(80)))
            self.assertTrue(ledger.verify())
            self.assertEqual(len(set(refs)), 80)
            code = '''import sys
from salamander.runtime import DurableEvidenceLedger
ledger=DurableEvidenceLedger(sys.argv[1])
assert ledger.verify() and len(ledger.records)==80
assert ledger.head==sys.argv[2]
'''
            subprocess.run([sys.executable, '-c', code, str(path), ledger.head],
                           cwd=ROOT, check=True, timeout=30)
            record = json.loads(path.read_text().splitlines()[0])
            record['payload']['i'] = -1
            lines = path.read_text().splitlines()
            path.write_text(json.dumps(record)+'\n'+'\n'.join(lines[1:])+'\n')
            with self.assertRaises(FailClosed):
                DurableEvidenceLedger(path)


class BoundedInputTests(unittest.TestCase):
    def reject(self, evidence):
        ledger = EvidenceLedger()
        with self.assertRaises(ValueError):
            AgentCapabilitySuite(ledger).inspect(tenant_id='a', target='x.py',
                                                 source='pass', evidence=evidence)
        self.assertEqual(ledger.records, ())

    def test_cycle_rejected(self):
        value = {}; value['self'] = value
        self.reject(value)

    def test_depth_rejected(self):
        value = {}
        for _ in range(30): value = {'child': value}
        self.reject(value)

    def test_item_budget_rejected(self): self.reject({'items': [0] * 10001})
    def test_big_integer_rejected(self): self.reject({'integer': 2 ** 4097})
    def test_nonstring_keys_rejected(self): self.reject({1: 'not-json'})
    def test_custom_mapping_not_invoked(self):
        class Untrusted(dict):
            def items(self): raise AssertionError('must not execute callback')
        self.reject(Untrusted())
    def test_custom_scalar_not_invoked(self):
        class Untrusted(str):
            def __str__(self): raise AssertionError('must not execute callback')
        self.reject({'value': Untrusted('x')})
    def test_falsey_nonmapping_rejected(self): self.reject([])
    def test_custom_source_not_invoked(self):
        class Untrusted(str):
            def encode(self, *args, **kwargs):
                raise AssertionError('must not execute callback')
        with self.assertRaises(ValueError):
            AgentCapabilitySuite().inspect(tenant_id='a', target='x.py', source=Untrusted('pass'))
    def test_detached_input(self):
        value = {'pins': {'p': False}}
        report = AgentCapabilitySuite().inspect(tenant_id='a',target='x.py',source='p=False',evidence=value)
        value['pins']['p'] = True
        self.assertEqual(report['capabilities']['pin_verifier']['status'], 'PASS')


if __name__ == '__main__': unittest.main()
