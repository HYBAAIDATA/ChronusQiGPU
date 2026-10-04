from __future__ import annotations
import json,tempfile,unittest
from dataclasses import replace
from pathlib import Path
from euclid.creative_substrate import *
class IntentGeometryTests(unittest.TestCase):
 def setUp(self):self.layer=IntentLayer()
 def directives(self):return (CreatorDirective('andre','A hopeful city learns to sing',2,{'tone':['hopeful'],'themes':['renewal'],'aesthetics':['oxford blue'],'symbols':['phoenix'],'emotional_trajectory':[.2,.8],'constraints':{'characters':{'Ada':{'goal':'restore the city'}},'world_rules':{'forbidden_lore':['impossible claim']}}}),CreatorDirective('collaborator','Keep the journey intimate',1,{'tone':['intimate'],'themes':['trust'],'emotional_trajectory':[.4,.6]}))
 def test_multi_creator_intent_is_normalized_and_hashed(self):
  intent=self.layer.interpret(self.directives());self.assertAlmostEqual(sum(intent.creator_weights.values()),1);self.assertEqual(intent.creator_weights['andre'],2/3);self.assertEqual(len(intent.content_hash),71);self.assertAlmostEqual(intent.emotional_trajectory[0],.26666666666666666);self.assertAlmostEqual(intent.emotional_trajectory[1],.7333333333333334)
 def test_duplicate_creator_and_invalid_trajectory_fail(self):
  with self.assertRaises(ValueError):self.layer.interpret((CreatorDirective('x','one'),CreatorDirective('x','two')))
  with self.assertRaises(ValueError):self.layer.interpret((CreatorDirective('x','one',structured={'emotional_trajectory':[2]}),))
 def test_constraint_conflict_is_explicit(self):
  items=(CreatorDirective('a','one',structured={'constraints':{'pacing':'slow'}}),CreatorDirective('b','two',structured={'constraints':{'pacing':'fast'}}));intent=self.layer.interpret(items);self.assertTrue(intent.constraints['pacing']['requires_resolution'])
 def test_creative_manifold_is_valid_and_intent_linked(self):
  intent=self.layer.interpret(self.directives());manifold=SemanticGeometryLayer().construct(intent);self.assertEqual(manifold.intent_hash,intent.content_hash);self.assertTrue(manifold.nodes);self.assertTrue(all(len(x.vector)==6 for x in manifold.nodes));self.assertEqual(manifold.characters['Ada']['goal'],'restore the city')
class GenerationWorldTests(unittest.TestCase):
 def cycle(self,path=None):return EuclidCreativeKernel(world_checkpoint=path).run((CreatorDirective('andre','A hopeful city learns to sing',structured={'tone':['hopeful'],'themes':['renewal'],'aesthetics':['blue'],'symbols':['phoenix'],'constraints':{'characters':{'Ada':{'goal':'restore'}},'world_rules':{'immutable_character_fields':['origin'],'forbidden_lore':['false axiom']}}}),))
 def test_all_modalities_share_canonical_lineage(self):
  cycle=self.cycle();self.assertEqual({a.modality for a in cycle.artifacts},set(MODALITIES));self.assertTrue(all(a.intent_hash==cycle.intent.content_hash and a.manifold_hash==cycle.manifold.content_hash for a in cycle.artifacts));self.assertTrue(all(not a.rendered for a in cycle.artifacts))
 def test_world_character_lore_rules_and_conflict_resolution(self):
  kernel=EuclidCreativeKernel();cycle=kernel.run((CreatorDirective('a','world',structured={'themes':['life'],'constraints':{'characters':{'Ada':{'origin':'earth'}},'world_rules':{'immutable_character_fields':['origin'],'forbidden_lore':['forbidden']}}}),));updated=kernel.adapt_world(cycle,'character_update',{'entity_id':'Ada','state':{'mood':'curious'}});self.assertEqual(updated.world.entities['Ada'].state['mood'],'curious')
  with self.assertRaises(ValueError):kernel.adapt_world(updated,'character_update',{'entity_id':'Ada','state':{'origin':'mars'}})
  with self.assertRaises(ValueError):kernel.adapt_world(updated,'lore_add',{'statement':'a forbidden history'})
  resolved=kernel.adapt_world(updated,'conflict_resolution',{'entity_id':'Ada','field':'path','candidates':['north','south','north'],'policy':'consensus'});self.assertEqual(resolved.world.entities['Ada'].state['path'],'north');self.assertTrue(kernel.world_engine.verify_chain())
 def test_persistent_world_restores_exactly(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'world.json';cycle=self.cycle(path);restored=WorldStateEngine(path).restore();self.assertEqual(restored.content_hash,cycle.world.content_hash);self.assertTrue(json.loads(path.read_text())['world_hash'].startswith('sha256:'))
 def test_coherence_detects_lineage_tamper(self):
  cycle=self.cycle();bad=replace(cycle.artifacts[0],intent_hash='sha256:bad');report=CoherenceEngine().evaluate(cycle.intent,cycle.manifold,(bad,)+cycle.artifacts[1:],cycle.world);self.assertFalse(report.passed);self.assertIn('artifact lineage mismatch',report.violations)
 def test_emergence_respects_forbidden_motif(self):
  intent=IntentLayer().interpret((CreatorDirective('a','test',structured={'themes':['hope','loss'],'constraints':{'forbidden_motifs':['hope-loss']}}),));manifold=SemanticGeometryLayer().construct(intent);world=WorldStateEngine().initialize(intent,manifold);proposals=EmergenceEngine().propose(intent,manifold,world);self.assertTrue(any(not p.allowed for p in proposals))
class KernelInterfaceTests(unittest.TestCase):
 def directive(self,refs=()):return CreatorDirective('andre','An intimate hopeful voyage',structured={'tone':['intimate'],'themes':['discovery'],'aesthetics':['luminous'],'symbols':['compass'],'emotional_trajectory':[.3,.6,.9]},references=refs)
 def test_end_to_end_closed_loop(self):
  kernel=EuclidCreativeKernel();cycle=kernel.run((self.directive(),),mode='hybrid');self.assertTrue(cycle.coherence.passed);self.assertEqual(cycle.expression.mode,ExpressionMode.HYBRID);self.assertTrue(cycle.expression.creator_controls['intent_edit']);self.assertTrue(cycle.expression.audience_controls['interact']);self.assertIn('not asserted',cycle.telemetry.claims['identity'])
  refined=kernel.refine(cycle,{'tone':['solemn'],'direction':'The voyage returns transformed'});self.assertEqual(refined.intent.revision,2);self.assertEqual(refined.intent.creators,cycle.intent.creators);self.assertEqual(refined.intent.tone,('solemn',));self.assertNotEqual(refined.intent.content_hash,cycle.intent.content_hash)
 def test_real_time_world_adaptation_updates_versions(self):
  kernel=EuclidCreativeKernel();cycle=kernel.run((self.directive(),));adapted=kernel.adapt_world(cycle,'lore_add',{'statement':'The compass remembers every voyage'});self.assertGreater(adapted.world.version,cycle.world.version);self.assertTrue(all(a.world_version==adapted.world.version for a in adapted.artifacts))
 def test_creator_api_governance_and_modes(self):
  api=EuclidCreatorAPI();ref={'reference_id':'archive-1','media_type':'image','source':'creator archive','rights':'owned','content_hash':'sha256:'+'0'*64,'owner_id':'andre'};cycle=api.create((self.directive((ref,)),),'creator');self.assertIn(cycle.world.world_id,api.cycles)
  with self.assertRaises(PermissionError):api.create((self.directive(({'source':'unknown'},)),))
  with self.assertRaises(KeyError):api.interact('missing','lore_add',{'statement':'x'})
 def test_telemetry_is_broader_than_mining_and_truthful(self):
  cycle=EuclidCreativeKernel().run((self.directive(),));data=cycle.telemetry.__dict__;self.assertNotIn('share_acceptance',data);self.assertGreaterEqual(data['intent_fidelity'],0);self.assertLessEqual(data['intent_fidelity'],1);self.assertIn('AGI/ASI',data['claims']['identity']);self.assertIn('not rendered media',data['claims']['media'])
 def test_architecture_audit_boundaries(self):
  report=architecture_audit();self.assertFalse(report['identity']['agi']);self.assertFalse(report['identity']['asi']);self.assertEqual(report['architecture']['intent_layer'],'implemented_with_deterministic_semantic_identity');self.assertIn('contract implemented',report['production_boundaries']['distributed_world_cluster']);self.assertEqual(report['production_boundaries']['share_acceptance_metrics'],'excluded_as_midas_mining_specific')
 def test_world_cluster_sharding_and_concurrency(self):
  kernel=EuclidCreativeKernel(world_cluster=WorldEngineCluster(4));cycle=kernel.run((self.directive(),));self.assertEqual(kernel.world_cluster.get(cycle.world.world_id).content_hash,cycle.world.content_hash);self.assertEqual(kernel.world_cluster.health()['worlds'],1)
  with self.assertRaises(RuntimeError):kernel.world_cluster.put(cycle.world,expected_version=99)
if __name__=='__main__':unittest.main()
