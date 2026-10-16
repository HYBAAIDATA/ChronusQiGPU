"""Executable learning lifecycle, not whole-system certification."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np
from Intelligence.pythia_learning import PythiaLearning
from Intelligence.pythia_memory import PythiaMemorySystem
from Intelligence.pythia_store import PythiaStore
from euclid.contracts import Experience, RewardAuthority
from euclid.learning_service import LearningService
from euclid.runtime import EuclidRuntime
from euclid.training_pipeline import TrainingCase, TrainingPipeline
from euclid.checkpoint_manifest import load_manifest, verify_manifest
from hyba_substrate.euclid_experience_superlearner import ExperienceSuperlearner
from hyba_substrate.euclid_learning_system import EuclidLearningSystem, EvidenceKind, ClaimStage


def experience(key='one', authority=RewardAuthority.MEASURED_ENVIRONMENT,
               domain='enterprise-routing', pattern=True):
    return Experience('exp-'+key, 'mission', domain, 'test',
                      {'x': 1, **({'learning_pattern': [1.0]*32} if pattern else {})},
                      'b', {'done': True}, None if authority is RewardAuthority.NONE else 0.5,
                      authority, 'test-observation-v1', 0.1, key)


def runtime(root):
    root = Path(root)
    memory, pythia = PythiaMemorySystem(), PythiaLearning()
    store = PythiaStore(memory, pythia, root/'pythia')
    store.load()
    return EuclidRuntime(creator_id='test-owner', state_dir=root,
                         memory=memory, pythia=pythia, store=store,
                         experience_learner=ExperienceSuperlearner(root/'learner.json', seed=5))


class LearningLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def compose(self):
        rt = runtime(self.root)
        self.addCleanup(rt.close)
        return rt

    def test_production_composes_learning_with_cognition_isolated(self):
        # The optional cognition/organism plane is independently tested by its
        # own suites. Here only that plane is isolated; learning engines are real.
        with patch.object(EuclidRuntime, '_compose_cognition'):
            rt = EuclidRuntime.production(creator_id='owner', state_dir=self.root,
                                          organism=False)
        self.addCleanup(rt.close)
        self.assertIs(rt.learning.governed_learning, rt.learning.experience_learner.learning_system)
        rt.learning.record(experience())
        self.assertEqual(len(rt.learning.governed_learning.events), 1)

    def test_runtime_attaches_one_governed_ledger(self):
        rt = self.compose()
        self.assertIs(rt.learning.governed_learning, rt.learning.experience_learner.learning_system)
        rt.learning.record(experience())
        self.assertEqual(len(rt.learning.governed_learning.events), 1)
        self.assertEqual(len(rt.learning.experience_learner.transitions), 1)
        self.assertEqual(len(rt.learning.memory.episodic.events()), 1)
        self.assertEqual(rt.learning.pythia._totals, [0, 0])
        self.assertTrue(rt.learning.experience_learner.transitions[0].done)
        self.assertTrue(rt.learning.memory_database.verify()['valid'])

    def test_observation_never_applies_unverified_reward(self):
        rt = self.compose()
        rt.learning.record(experience(authority=RewardAuthority.NONE))
        self.assertFalse(rt.learning.experience_learner.transitions)
        self.assertEqual(rt.learning.pythia._totals, [0, 0])
        self.assertEqual(len(rt.learning.governed_learning.events), 1)
        self.assertFalse(rt.evidence.records[-1].payload['reward_applied'])

    def test_synthetic_mining_success_is_not_pool_truth(self):
        rt = self.compose()
        event = replace(experience(authority=RewardAuthority.VALIDATED_SIMULATION,
                                   domain='bitcoin-mining'), outcome={'mining_success': True})
        rt.learning.record(event)
        self.assertEqual(rt.learning.pythia._totals, [0, 0])

    def test_measured_mining_success_requires_explicit_boolean(self):
        rt = self.compose()
        event = replace(experience(domain='bitcoin-mining'), outcome={'mining_success': True})
        rt.learning.record(event)
        self.assertEqual(rt.learning.pythia._totals, [1, 1])

    def test_measured_mining_failure_is_retained(self):
        rt = self.compose()
        event = replace(experience(domain='bitcoin-mining'), outcome={'mining_success': False})
        rt.learning.record(event)
        self.assertEqual(rt.learning.pythia._totals, [1, 0])

    def test_missing_pattern_does_not_teach_hash_features(self):
        rt = self.compose()
        rt.learning.record(experience(pattern=False))
        self.assertEqual(rt.learning.pythia._totals, [0, 0])

    def test_bad_pattern_rejected_before_any_mutation(self):
        rt = self.compose()
        event = replace(experience(), observation={'learning_pattern': [float('nan')]*32})
        with self.assertRaises(ValueError): rt.learning.record(event)
        self.assertEqual(rt.learning.replay_state()['journal_entries'], 0)
        self.assertFalse(rt.learning.experience_learner.transitions)

    def test_duplicate_rejected_before_all_engines(self):
        rt = self.compose()
        event = experience()
        rt.learning.record(event)
        with self.assertRaises(ValueError): rt.learning.record(event)
        self.assertEqual(rt.learning.pythia._totals, [0, 0])
        self.assertEqual(len(rt.learning.memory.episodic.events()), 1)

    def test_failure_leaves_durable_pending_reconciliation(self):
        rt = self.compose()
        event = experience()
        with patch.object(rt.learning.store, 'save', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): rt.learning.record(event)
        self.assertEqual(rt.learning.status()['pending_reconciliation'], 1)
        transitions = len(rt.learning.experience_learner.transitions)
        restarted = LearningService(experience_learner=rt.learning.experience_learner,
                                    replay_journal_path=self.root/'replay_journal.json')
        with self.assertRaisesRegex(ValueError, 'reconciliation'): restarted.record(event)
        self.assertEqual(len(rt.learning.experience_learner.transitions), transitions)

    def test_curriculum_and_consolidation_reachable(self):
        rt = self.compose()
        rt.learning.record(experience())
        self.assertEqual(len(rt.learning.curriculum()['experience']), 1)
        snapshot = rt.consolidate_learning()
        self.assertEqual(snapshot['governed']['event_count'], 1)
        self.assertEqual(snapshot['pythia_patterns'], 1)
        self.assertFalse(snapshot['external_validation'])

    def test_store_restart_retains_all_fate_statistics(self):
        rt = self.compose()
        rt.learning.record(replace(experience(domain='bitcoin-mining'), outcome={'mining_success': True}))
        rt.close()
        restarted = self.compose()
        self.assertEqual(restarted.learning.pythia._totals, [1, 1])
        self.assertEqual(len(restarted.learning.memory.episodic.events()), 1)
        self.assertEqual(len(restarted.learning.governed_learning.events), 1)
        with self.assertRaises(ValueError): restarted.learning.record(
            replace(experience(domain='bitcoin-mining'), outcome={'mining_success': True}))

    def test_store_corruption_fails_closed(self):
        rt = self.compose()
        rt.learning.record(experience())
        path = rt.learning.store.snapshot_path
        snap = json.loads(path.read_text()); snap['learning']['sleep_cycle'] += 1
        path.write_text(json.dumps(snap))
        with self.assertRaises(ValueError): runtime(self.root)

    def test_real_cross_process_restart_retains_lineage(self):
        rt = self.compose()
        rt.learning.record(experience())
        rt.close()
        code = '''import json,sys
from pathlib import Path
from hyba_substrate.euclid_experience_superlearner import ExperienceSuperlearner
from hyba_substrate.euclid_learning_system import EuclidLearningSystem
from Intelligence.pythia_learning import PythiaLearning
from Intelligence.pythia_memory import PythiaMemorySystem
from Intelligence.pythia_store import PythiaStore
p=Path(sys.argv[1]); learner=ExperienceSuperlearner(p/'learner.json')
g=EuclidLearningSystem(p/'governed_learning.json')
m=PythiaMemorySystem(); py=PythiaLearning(); st=PythiaStore(m,py,p/'pythia'); st.load()
print(json.dumps({'transitions':len(learner.transitions),'events':len(g.events),
                  'episodes':len(m.episodic.events()),'totals':py._totals}))'''
        env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
        result = subprocess.run([sys.executable, '-c', code, str(self.root)], env=env,
                                text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout), {'transitions':1,'events':1,'episodes':1,'totals':[0,0]})

    def test_training_checkpoint_manifest_matches_runtime_learner(self):
        rt = self.compose()
        pipeline = rt.training_pipeline(mission_id='mission', provenance='synthetic-control-v1')
        self.assertIs(pipeline.learner, rt.learning.experience_learner)
        cases = lambda prefix: [TrainingCase(prefix+str(i), {'x': i%2}) for i in range(6)]
        report = pipeline.run(task_id='routing', actions=('a','b'), train_cases=cases('t'),
                              validation_cases=cases('v'), final_test_cases=cases('f'),
                              reward=lambda case, action: float(action == ('a' if case.state['x']==0 else 'b')),
                              epochs=8, report_path=self.root/'report.json',
                              manifest_path=self.root/'manifest.json', source_revision='test-revision')
        self.assertTrue(verify_manifest(load_manifest(self.root/'manifest.json'),
                                        evidence_path=self.root/'report.json')['valid'])
        self.assertEqual(len(rt.learning.governed_learning.events), 48)
        self.assertTrue(all(t.done for t in pipeline.learner.transitions))
        self.assertFalse(report.boundaries['external_validation'])

    def test_repeated_training_runs_have_distinct_replay_namespaces(self):
        rt = self.compose(); pipeline = rt.training_pipeline(mission_id='m', provenance='test')
        args = dict(task_id='task', actions=('a','b'), train_cases=[TrainingCase('t', {'x':1})],
                    validation_cases=[TrainingCase('v', {'x':2})], epochs=1,
                    reward=lambda c,a: 0.5)
        pipeline.run(**args); pipeline.run(**args)
        self.assertEqual(len(pipeline.learner.transitions), 2)

    def test_evaluation_does_not_mutate_or_explore(self):
        learner = ExperienceSuperlearner(planning_steps=0)
        learner.register_task('t', ('a','b'), persist=False)
        before = copy.deepcopy(learner._payload())
        learner.select_action('t', {'unseen':True}, explore=False)
        self.assertEqual(learner._payload(), before)

    def test_rng_and_task_contract_survive_checkpoint(self):
        path = self.root/'rng.json'
        learner = ExperienceSuperlearner(path, epsilon=1.0, seed=7)
        learner.register_task('task', ('a','b'))
        for _ in range(17): learner.select_action('task', {'x':1})
        learner._checkpoint()
        restored = ExperienceSuperlearner(path)
        self.assertEqual(restored.tasks['task'].actions, ('a','b'))
        restored.register_task('task', ('a','b'))
        self.assertEqual([learner.select_action('task', {'x':1}) for _ in range(20)],
                         [restored.select_action('task', {'x':1}) for _ in range(20)])

    def test_reward_range_rejected_without_transition(self):
        learner = ExperienceSuperlearner(planning_steps=0)
        learner.register_task('t', ('a','b'), reward_range=(0,1), persist=False)
        with self.assertRaises(ValueError): learner.observe('t', {}, 'a', 2.0, {})
        self.assertFalse(learner.q_values)

    def test_external_claim_cannot_self_award_or_skip_ladder(self):
        rt = self.compose(); g = rt.learning.governed_learning
        claim = g.propose_claim(domain='routing', statement='x', derivation='test')
        with self.assertRaises(ValueError):
            g.add_claim_evidence(claim.claim_id, kind=EvidenceKind.EXTERNAL_COMPARISON,
                                 passed=True, issuer='self')
        g.add_claim_evidence(claim.claim_id, kind=EvidenceKind.EXTERNAL_COMPARISON,
                             passed=True, issuer='reviewer', reference_id='review-1', operator_approved=True)
        self.assertEqual(claim.stage, ClaimStage.HYPOTHESIZED.value)

    def test_refuted_claim_remains_refuted(self):
        g = EuclidLearningSystem(); c = g.propose_claim(domain='d', statement='x', derivation='test')
        g.add_claim_evidence(c.claim_id, kind=EvidenceKind.INTERNAL_REPRODUCTION, passed=False, issuer='test')
        g.add_claim_evidence(c.claim_id, kind=EvidenceKind.INTERNAL_REPRODUCTION, passed=True, issuer='test')
        self.assertEqual(c.stage, ClaimStage.REFUTED.value)
        self.assertEqual(c.confidence, 0.0)

    def test_pythia_statistics_tamper_rejected(self):
        pythia = PythiaLearning(); snap = pythia.to_snapshot()
        snap['evidence_totals'] = [100, 100]
        with self.assertRaises(ValueError): pythia.load_snapshot(snap)

    def test_closed_runtime_rejects_new_training_and_consolidation(self):
        rt = self.compose(); rt.close()
        with self.assertRaises(RuntimeError): rt.training_pipeline(mission_id='m', provenance='test')
        with self.assertRaises(RuntimeError): rt.consolidate_learning()


if __name__ == '__main__': unittest.main()
