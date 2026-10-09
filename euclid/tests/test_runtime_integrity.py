"""Local component regressions; unit doubles do NOT certify production composition."""
import ast
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

from euclid import EuclidRuntime
from euclid.contracts import Authority, Experience, RewardAuthority, domain_hash
from euclid.evidence import EvidenceChain, atomic_write
from euclid.governance import Organ
from euclid.memory_database import MemoryDatabase, MemoryScope
from euclid.learning_service import LearningService
from euclid.cognition.problem import CognitionProblem
from euclid.cognition.state import CognitiveState


class EvidenceIntegrityTests(unittest.TestCase):
    def test_input_is_detached(self):
        chain = EvidenceChain(); payload = {'nested': {'x': [1]}}
        chain.append('observed', payload); payload['nested']['x'].append(2)
        self.assertEqual(chain.records[0].payload['nested']['x'], [1]); chain.verify()

    def test_append_result_is_detached(self):
        chain = EvidenceChain(); record = chain.append('observed', {'x': [1]})
        record.payload['x'].append(2)
        self.assertEqual(chain.records[0].payload['x'], [1]); chain.verify()

    def test_records_are_detached(self):
        chain = EvidenceChain(); chain.append('observed', {'x': [1]})
        chain.records[0].payload['x'].append(2)
        self.assertEqual(chain.records[0].payload['x'], [1]); chain.verify()

    def test_constructor_is_detached(self):
        source = EvidenceChain(); source.append('observed', {'x': [1]})
        records = source.records; restored = EvidenceChain(records)
        records[0].payload['x'].append(2)
        self.assertEqual(restored.records[0].payload['x'], [1]); restored.verify()

    def test_legacy_hash_shape_preserved(self):
        with patch('euclid.evidence.time.time', return_value=123.0):
            chain = EvidenceChain(); record = chain.append('observed', {'x': 1})
        base = {'sequence': 0, 'timestamp': 123.0, 'kind': 'observed', 'payload': {'x': 1}, 'previous_hash': None}
        self.assertEqual(record.record_hash, domain_hash('euclid.evidence.v1', base))
        self.assertEqual(EvidenceChain.from_payload(chain.to_payload()).head, chain.head)

    def test_tamper_rejected(self):
        chain = EvidenceChain(); chain.append('observed', {'x': 1})
        payload = chain.to_payload(); payload['records'][0]['payload']['x'] = 2
        with self.assertRaisesRegex(ValueError, 'seal mismatch'): EvidenceChain.from_payload(payload)

    def test_concurrent_append_and_snapshot(self):
        chain = EvidenceChain(); original_hash = domain_hash
        def slow_hash(domain, value):
            time.sleep(0.0001)
            return original_hash(domain, value)
        def writer(n):
            for i in range(12):
                chain.append('observed', {'writer': n, 'i': i})
                EvidenceChain.from_payload(chain.to_payload()).verify()
        with patch('euclid.evidence.domain_hash', side_effect=slow_hash):
            with ThreadPoolExecutor(max_workers=6) as pool: list(pool.map(writer, range(6)))
        self.assertEqual(len(chain.records), 72); chain.verify()
        self.assertEqual([r.sequence for r in chain.records], list(range(72)))


class CognitiveLedgerTests(unittest.TestCase):
    def test_transition_input_and_return_detached(self):
        state = CognitiveState('p', {'features': ['a']}, clock=lambda: 1.0)
        details = {'nested': [1]}; rec = state.record_transition('observe', 'observed', details)
        details['nested'].append(2); rec.details['nested'].append(3)
        self.assertEqual(state.transitions[0].details['nested'], [1]); state.verify_transitions()

    def test_transition_view_detached(self):
        state = CognitiveState('p', {}); state.record_transition('observe', 'observed', {'x': [1]})
        state.transitions[0].details['x'].append(2)
        self.assertEqual(state.transitions[0].details['x'], [1]); state.verify_transitions()

    def test_payload_and_representation_detached(self):
        original = {'x': [1]}; state = CognitiveState('p', original)
        original['x'].append(2); state.to_payload()['representation']['x'].append(3)
        self.assertEqual(state.representation['x'], [1])
        CognitiveState.from_payload(state.to_payload()).verify_transitions()

    def test_clock_does_not_change_content_seal(self):
        a = CognitiveState('p', {}, clock=lambda: 1.0); b = CognitiveState('p', {}, clock=lambda: 2.0)
        for s in (a, b): s.record_transition('observe', 'observed', {'x': 1})
        self.assertEqual(a.to_payload()['seal'], b.to_payload()['seal'])


class ProblemBoundaryTests(unittest.TestCase):
    def test_reserved_metadata_rejected(self):
        keys = ('problem_id', 'goal', 'problem_class', 'structure', 'observations', 'declared_objectives', 'measured_reward', 'reward_authority', 'constraints', 'problem_digest')
        for key in keys:
            with self.subTest(key=key):
                p = CognitionProblem('p', 'g', 'c', metadata={key: 'spoof'})
                with self.assertRaisesRegex(ValueError, 'metadata'): p.to_mapping()

    def test_mutated_metadata_cannot_bypass_dispatch_check(self):
        metadata = {'strategy': 'abductive'}; p = CognitionProblem('p', 'g', 'c', metadata=metadata)
        metadata['measured_reward'] = 1.0
        with self.assertRaises(ValueError): p.to_mapping()

    def test_legitimate_metadata_preserved(self):
        p = CognitionProblem('p', 'g', 'c', metadata={'strategy': 'abductive', 'initial_code': 'x = 1'})
        self.assertEqual(p.to_mapping()['strategy'], 'abductive')
        self.assertEqual(p.to_mapping()['reward_authority'], 'none')


class RuntimeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.runtime = EuclidRuntime(creator_id='owner', state_dir=self.tmp.name)
    def tearDown(self):
        self.runtime.close(); self.tmp.cleanup()

    def test_failed_episode_revokes_rights_without_success_persistence(self):
        # The failure double tests lifecycle only, never production readiness.
        class FailureAgent:
            def solve(self, *args, **kwargs): raise RuntimeError('injected episode failure')
        self.runtime.adaptive = FailureAgent()
        with self.assertRaisesRegex(RuntimeError, 'injected'): self.runtime.solve_task(SimpleNamespace(task_id='p'), object())
        self.assertFalse(self.runtime.rights.permits('owner', 'task-world-1', 'task-world-1.execute', 'dispatch'))
        self.assertEqual(self.runtime.rights.snapshot()['grants'], [])
        self.assertFalse((Path(self.tmp.name) / 'adaptive_knowledge.json').exists())
        self.assertTrue(any(r.kind == 'right-revoked' for r in self.runtime.evidence.records))
        self.runtime.evidence.verify()

    def test_baseexception_revokes_rights(self):
        class CancelledAgent:
            def solve(self, *args, **kwargs): raise KeyboardInterrupt()
        self.runtime.adaptive = CancelledAgent()
        with self.assertRaises(KeyboardInterrupt): self.runtime.solve_task(SimpleNamespace(task_id='p'), object())
        self.assertEqual(self.runtime.rights.snapshot()['grants'], [])

    def test_closed_runtime_does_not_register_or_grant(self):
        self.runtime.close(); before = self.runtime.registry.report()
        with self.assertRaisesRegex(RuntimeError, 'closed'): self.runtime.solve_task(SimpleNamespace(task_id='p'), object())
        self.assertEqual(self.runtime.registry.report(), before)
        self.assertEqual(self.runtime.rights.snapshot()['grants'], [])

    def test_shutdown_reports_failures_and_still_closes_database(self):
        class FailingStore:
            def save(self): raise OSError('sensitive external error')
        self.runtime.learning.store = FailingStore(); self.runtime.close()
        report = self.runtime.shutdown_report()
        self.assertEqual(report['store_save'], 'failed')
        self.assertEqual(report['database_close'], 'completed')
        self.assertEqual(report['failures'], [{'operation': 'store-save', 'error_type': 'OSError'}])
        self.assertFalse(report['durability_verified'])
        self.assertNotIn('sensitive', json.dumps(report))
        self.assertNotIn('sensitive', json.dumps(self.runtime.evidence.to_payload()))
        with self.assertRaises(Exception): self.runtime.learning.memory_database.verify()
        self.runtime.close(); self.assertEqual(self.runtime.shutdown_report(), report)

    def test_shutdown_report_detached_and_initial_not_executed(self):
        self.assertFalse(self.runtime.shutdown_report()['closed'])
        self.runtime.close(); report = self.runtime.shutdown_report(); report['failures'].append({'spoof': True})
        self.assertEqual(self.runtime.shutdown_report()['failures'], [])

    def test_shutdown_revokes_direct_delegator_rights(self):
        effects = []
        self.runtime.register_organ(Organ('owned', frozenset({'write'}), Authority.PROPOSE, lambda r: effects.append(1) or {}))
        self.runtime.rights.grant('owner', 'owned', 'write', 'dispatch')
        self.runtime.close()
        with self.assertRaises(PermissionError): self.runtime.delegator.dispatch('owned', 'write', {}, confident=True, safe=True)
        self.assertEqual(effects, [])

    def test_closed_repository_solver_cannot_call_core(self):
        calls = []
        self.runtime.cognition = SimpleNamespace(solve=lambda *a, **k: calls.append(1))
        self.runtime.close()
        with self.assertRaisesRegex(RuntimeError, 'closed'): self.runtime.solve_repository_problem({'problem_id': 'p'})
        self.assertEqual(calls, [])

    def test_missing_guardian_cannot_execute_specialist(self):
        effects = []
        self.runtime.register_organ(Organ('owned', frozenset({'owned.request'}), Authority.PROPOSE, lambda r: effects.append(1) or {}))
        self.runtime.rights.grant('owner', 'owned', 'owned.request', 'dispatch')
        result = self.runtime.dispatch_specialist('owned', {'operation': 'write'}, tenant_id='tenant-a', actor='actor-a')
        self.assertFalse(result['allowed'])
        self.assertEqual(result['governance']['reason'], 'GOVERNANCE_UNAVAILABLE')
        self.assertEqual(effects, [])

    def test_real_al_haras_allow_denial_cross_tenant_and_expiry(self):
        from al_haras import ALHaras, GuardianPolicy, HashChainAudit, SubscriptionAuthority, SubscriptionClaims
        authority = SubscriptionAuthority({'test-key': b'local-fixture-key-only-not-a-deployment-key'}, 'local-test-issuer')
        audit = HashChainAudit(Path(self.tmp.name) / 'guardian.jsonl')
        self.runtime.guardian = ALHaras(authority, GuardianPolicy(version='local-fixture-policy', allowed_operations=frozenset({'owned.write'})), audit)
        effects = []
        self.runtime.register_organ(Organ('owned', frozenset({'owned.request'}), Authority.PROPOSE, lambda r: effects.append(r['value']) or {'observed': effects[-1]}))
        self.runtime.rights.grant('owner', 'owned', 'owned.request', 'dispatch')
        now = int(time.time())
        claims = SubscriptionClaims('local-subscription', 'tenant-a', 'local-test-issuer', 'test-key', ('hyba.security',), ('actor-a',), now-1, now+60)
        token = authority.issue(claims)
        denied = self.runtime.dispatch_specialist('owned', {'operation':'write','value':7},tenant_id='tenant-a',actor='actor-a',subscription_token='')
        self.assertFalse(denied['allowed']); self.assertEqual(effects, [])
        cross = self.runtime.dispatch_specialist('owned', {'operation':'write','value':7},tenant_id='tenant-b',actor='actor-a',subscription_token=token)
        self.assertFalse(cross['allowed']); self.assertEqual(effects, [])
        expired_claims = SubscriptionClaims('expired-subscription', 'tenant-a', 'local-test-issuer', 'test-key', ('hyba.security',), ('actor-a',), now-10, now-1)
        expired = self.runtime.dispatch_specialist('owned', {'operation':'write','value':7},tenant_id='tenant-a',actor='actor-a',subscription_token=authority.issue(expired_claims))
        self.assertFalse(expired['allowed']); self.assertEqual(effects, [])
        allowed = self.runtime.dispatch_specialist('owned', {'operation':'write','value':7},tenant_id='tenant-a',actor='actor-a',subscription_token=token)
        self.assertTrue(allowed['allowed']); self.assertEqual(effects, [7]); self.assertTrue(allowed['governance']['evidence_id'])
        self.runtime.evidence.verify()
        self.assertTrue((Path(self.tmp.name) / 'guardian.jsonl').is_file())
        # Real AL HARAS + runtime delegation; local fixture policy, not live approval.

    def test_real_dispatch_denial_and_execution(self):
        effects = []
        self.runtime.register_organ(Organ('owned-software', frozenset({'write'}), Authority.PROPOSE, lambda request: effects.append(request['x']) or {'observed': effects[-1]}))
        with self.assertRaises(PermissionError): self.runtime.delegator.dispatch('owned-software', 'write', {'x': 7}, confident=True, safe=True)
        self.assertEqual(effects, [])
        self.runtime.rights.grant('owner', 'owned-software', 'write', 'dispatch')
        result = self.runtime.delegator.dispatch('owned-software', 'write', {'x': 7}, confident=True, safe=True)
        self.assertEqual(effects, [7]); self.assertEqual(result['observed'], 7)
        self.runtime.evidence.verify()
        # Real creator-scoped delegation, NOT AL HARAS production certification.


class DurableComponentTests(unittest.TestCase):
    def test_fresh_process_readback_and_rewardless_replay_denial(self):
        with tempfile.TemporaryDirectory() as root:
            db = MemoryDatabase(Path(root) / 'memory.sqlite3')
            service = LearningService(memory_database=db, replay_journal_path=Path(root) / 'replay.json')
            exp = Experience('e', 'm', 'd', 'component-test', {'x': 1}, 'observe', {'y': 2}, None, RewardAuthority.NONE, 'local-observation', 0.0, 'replay-1', created_at=1.0)
            service.record(exp); self.assertTrue(db.verify()['valid']); db.close()
            script = '''import sys\nfrom pathlib import Path\nfrom euclid.memory_database import MemoryDatabase, MemoryScope\nfrom euclid.learning_service import LearningService\nfrom euclid.contracts import Experience, RewardAuthority\nr=Path(sys.argv[1]); db=MemoryDatabase(r/'memory.sqlite3'); svc=LearningService(memory_database=db,replay_journal_path=r/'replay.json')\nassert db.get('e',scope=MemoryScope('local','m','d')).content['outcome']=={'y':2}\nassert db.verify()['valid']\ne=Experience('e','m','d','component-test',{'x':1},'observe',{'y':2},None,RewardAuthority.NONE,'local-observation',0.0,'replay-1',created_at=999.0)\ntry: svc.record(e)\nexcept ValueError as error: assert 'duplicate' in str(error)\nelse: raise AssertionError('duplicate applied')\ndb.close();print('FRESH_PROCESS_COMPONENT_REPLAY_VERIFIED')'''
            out = subprocess.run([sys.executable, '-c', script, root], capture_output=True, text=True, check=True)
            self.assertIn('FRESH_PROCESS_COMPONENT_REPLAY_VERIFIED', out.stdout)
            # This is canonical local memory/replay, NOT THESEUS/OVID composition.

    def test_memory_scope_and_integrity(self):
        with tempfile.TemporaryDirectory() as root:
            db = MemoryDatabase(Path(root) / 'memory.sqlite3'); a = MemoryScope('a', 'm', 'd'); b = MemoryScope('b', 'm', 'd')
            db.put(scope=a, tier='episodic', content={'x': 1}, provenance='test', reward_authority=RewardAuthority.NONE, uncertainty=0.0, replay_id='r', memory_id='e')
            with self.assertRaises(KeyError): db.get('e', scope=b)
            db._connection.execute("UPDATE memories SET content_json=? WHERE memory_id=?", ('{"x":2}', 'e'))
            with self.assertRaisesRegex(ValueError, 'hash mismatch'): db.verify()
            db.close()

    def test_learned_strategy_survives_fresh_process(self):
        from euclid.cognition.baselines import BanditMetaLearner
        with tempfile.TemporaryDirectory() as root:
            learner = BanditMetaLearner()
            self.assertEqual(learner.select_strategy('context-a', ('a', 'b')).strategy_id, 'a')
            learner.update('context-a', 'a', False)
            learner.update('context-a', 'b', True)
            self.assertEqual(learner.select_strategy('context-a', ('a', 'b')).strategy_id, 'b')
            db = MemoryDatabase(Path(root) / 'memory.sqlite3')
            db.put(scope=MemoryScope('tenant-a', 'm', 'strategy'), tier='semantic',
                   content=learner.to_dict(), provenance='observed-component-trials',
                   reward_authority=RewardAuthority.NONE, uncertainty=0.0,
                   replay_id='strategy-checkpoint', memory_id='strategy')
            db.close()
            script = """import sys
from pathlib import Path
from euclid.memory_database import MemoryDatabase,MemoryScope
from euclid.cognition.baselines import BanditMetaLearner
r=Path(sys.argv[1]); db=MemoryDatabase(r/'memory.sqlite3')
record=db.get('strategy',scope=MemoryScope('tenant-a','m','strategy'))
learner=BanditMetaLearner.from_dict(record.content)
assert learner.select_strategy('context-a',('a','b')).strategy_id=='b'
assert learner.select_strategy('context-b',('a','b')).strategy_id=='a'
db.close(); print('SCOPED_STRATEGY_RESTART_VERIFIED')
"""
            out = subprocess.run([sys.executable, '-c', script, root], capture_output=True, text=True, check=True)
            self.assertIn('SCOPED_STRATEGY_RESTART_VERIFIED', out.stdout)

    def test_no_eager_optional_service_import(self):
        script = '''import importlib.abc,sys\nclass RejectOptional(importlib.abc.MetaPathFinder):\n def find_spec(self,fullname,path=None,target=None):\n  if fullname=='euclid.cognition.service': raise AssertionError('optional service imported eagerly')\nsys.meta_path.insert(0,RejectOptional())\nfrom euclid import EuclidRuntime\nfrom euclid.cognition import CognitiveState,GeneralIntelligenceCore\nassert 'euclid.cognition.service' not in sys.modules\nfrom euclid.cognition.state import CognitiveState as Direct\nassert CognitiveState is Direct\n'''
        subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, check=True)


class AdaptiveTransferTests(unittest.TestCase):
    def learner(self):
        from euclid.cognition.integrated.control import ContextualStrategyLearner
        learner = ContextualStrategyLearner(seed=7)
        learner.global_stats['imported-strategy'] = [9.0, 10.0]
        return learner

    def test_harmful_transfer_changes_allowed_selection(self):
        learner = self.learner()
        reports = [learner.record_episode('target', 'imported-strategy', 0.0) for _ in range(3)]
        guard = reports[-1]['negative_transfer']
        self.assertEqual(guard['evidence_class'], 'MODELED')
        self.assertEqual(guard['source_trials'], 10)
        self.assertEqual(guard['target_trials'], 3)
        choice = learner.select_strategy('target', ('imported-strategy', 'class-local-fallback'))
        self.assertEqual(choice.strategy_id, 'class-local-fallback')
        self.assertNotIn('imported-strategy', choice.alternatives)
        self.assertIn('negative-transfer guard suppressed', choice.basis)
        self.assertTrue(any(e.get('event') == 'abandon_negative_transfer' for e in learner.events))

    def test_guard_is_context_scoped_and_survives_payload_restore(self):
        from euclid.cognition.integrated.control import ContextualStrategyLearner
        learner = self.learner()
        for _ in range(3): learner.record_episode('target', 'imported-strategy', 0.0)
        restored = ContextualStrategyLearner.from_payload(learner.to_payload())
        self.assertEqual(restored.select_strategy('target', ('imported-strategy', 'fallback')).strategy_id, 'fallback')
        self.assertEqual(restored.select_strategy('unrelated', ('imported-strategy',)).strategy_id, 'imported-strategy')
        # The strategy remains present; it is not retired globally.
        self.assertIn('imported-strategy', restored.global_stats)

    def test_all_suppressed_escalates_instead_of_repeating_bad_strategy(self):
        learner = self.learner()
        for _ in range(3): learner.record_episode('target', 'imported-strategy', 0.0)
        with self.assertRaisesRegex(ValueError, 'all available strategies'): learner.select_strategy('target', ('imported-strategy',))

    def test_no_harmful_transfer_claim_without_source_or_sufficient_trials(self):
        learner = self.learner()
        for _ in range(2): self.assertNotIn('negative_transfer', learner.record_episode('target', 'imported-strategy', 0.0))
        from euclid.cognition.integrated.control import ContextualStrategyLearner
        cold = ContextualStrategyLearner()
        for _ in range(6): self.assertNotIn('negative_transfer', cold.record_episode('target', 'cold', 0.0))

    def test_good_transfer_not_suppressed_and_frozen_does_not_learn(self):
        learner = self.learner()
        for _ in range(5): self.assertNotIn('negative_transfer', learner.record_episode('target', 'imported-strategy', 1.0))
        before = copy.deepcopy(learner.to_payload()); learner.frozen = True
        self.assertTrue(learner.record_episode('target', 'imported-strategy', 0.0)['frozen'])
        self.assertEqual(learner.to_payload(), before)

    def test_nonfinite_utilities_rejected_without_mutation(self):
        learner = self.learner(); before = copy.deepcopy(learner.to_payload())
        for value in (float('nan'), float('inf'), -float('inf')):
            with self.assertRaises(ValueError): learner.record_episode('target', 'imported-strategy', value)
        self.assertEqual(learner.to_payload(), before)

    def test_old_payload_and_configurable_evidence_policy(self):
        from euclid.cognition.integrated.control import ContextualStrategyLearner
        old = {'schema':'euclid.contextual-strategy/1', 'class_stats':{}, 'global_stats':{}, 'negative_transfer':[]}
        restored = ContextualStrategyLearner.from_payload(old)
        self.assertEqual(restored.min_transfer_trials, 3)
        strict = ContextualStrategyLearner(min_transfer_trials=5, negative_transfer_probability=0.99)
        payload = ContextualStrategyLearner.from_payload(strict.to_payload())
        self.assertEqual(payload.min_transfer_trials, 5)
        self.assertEqual(payload.negative_transfer_probability, 0.99)

    def test_fresh_process_retains_contextual_transfer_guard(self):
        learner = self.learner()
        for _ in range(3): learner.record_episode('target', 'imported-strategy', 0.0)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'knowledge.json'; atomic_write(path, learner.to_payload())
            script = """import json,sys
from pathlib import Path
from euclid.cognition.integrated.control import ContextualStrategyLearner
learner=ContextualStrategyLearner.from_payload(json.loads(Path(sys.argv[1]).read_text()))
assert learner.select_strategy('target',('imported-strategy','fallback')).strategy_id=='fallback'
assert learner.select_strategy('unrelated',('imported-strategy',)).strategy_id=='imported-strategy'
print('CONTEXTUAL_TRANSFER_FRESH_PROCESS_VERIFIED')
"""
            out = subprocess.run([sys.executable, '-c', script, str(path)], capture_output=True, text=True, check=True)
            self.assertIn('CONTEXTUAL_TRANSFER_FRESH_PROCESS_VERIFIED', out.stdout)
            # A serialized specialist restart, not THESEUS/OVID composition.


if __name__ == '__main__': unittest.main()
