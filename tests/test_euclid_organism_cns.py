from __future__ import annotations
import unittest
from euclid.organism_cns import *
from euclid.creative_substrate import CreatorDirective
class BehaviorSteeringTests(unittest.TestCase):
 def directive(self):return CreatorDirective('andre','A luminous world discovers itself',structured={'tone':['hopeful'],'themes':['discovery'],'aesthetics':['luminous'],'symbols':['compass'],'constraints':{'characters':{'Euclid':{'goal':'discover coherently'}}}})
 def test_phase_and_mood_are_operational(self):
  c=EuclidOrganismCNS();c.create((self.directive(),));report=c.behavior.report();self.assertIn(report['phase'],{x.value for x in CreativePhase});self.assertIn(report['mood'],{x.value for x in OrganismMood});self.assertIn('not consciousness',report['claim_boundary'])
 def test_long_horizon_predictive_curves_and_volatility(self):
  s=LongHorizonSteering()
  for i in range(6):s.record(.4+i*.05,.2+i*.01,.5-i*.03,.2)
  f=s.forecast(8);self.assertEqual(len(f.value_curve),8);self.assertGreater(f.value_trend,0);self.assertGreaterEqual(f.volatility,0);self.assertIn(f.recommended_posture,{'exploit','explore_bounded','hold','conserve'});self.assertIn('reduce_cost_20pct',f.counterfactuals)
 def test_steering_bounds(self):
  with self.assertRaises(ValueError):LongHorizonSteering().record(2,0,0,0)
  with self.assertRaises(ValueError):LongHorizonSteering().forecast()
class CNSIntegrationTests(unittest.TestCase):
 def directive(self,refs=()):return CreatorDirective('andre','A living world learns through curiosity',structured={'tone':['hopeful'],'themes':['learning'],'aesthetics':['blue'],'symbols':['seed'],'constraints':{'characters':{'Euclid':{'goal':'learn'}}}},references=refs)
 def test_closed_loop_cns_world_cluster_and_dashboard(self):
  c=EuclidOrganismCNS();cycle=c.create((self.directive(),),'hybrid');dash=c.dashboard();self.assertEqual(dash['schema'],'EUCLID_ORGANISM_DASHBOARD_V1');self.assertEqual(dash['world']['id'],cycle.world.world_id);self.assertEqual(dash['cluster']['worlds'],1);self.assertFalse(dash['truth']['claims']['identity'].startswith('AGI'))
 def test_feedback_and_interaction_are_integrated(self):
  c=EuclidOrganismCNS();first=c.create((self.directive(),));refined=c.refine({'direction':'The world becomes reflective','tone':['solemn']});self.assertEqual(refined.intent.revision,2);adapted=c.interact('lore_add',{'statement':'The seed remembers the first question'});self.assertGreater(adapted.world.version,refined.world.version);self.assertTrue(c.health_report()['healthy'])
 def test_phase_ii_stress_is_evidence_producing(self):
  c=EuclidOrganismCNS();c.create((self.directive(),));summary=c.run_phase_ii_stress();self.assertEqual(summary['failed'],0);self.assertEqual(summary['pass_rate'],1);self.assertEqual(c.dashboard()['stress']['passed'],summary['passed'])
 def test_publication_formatter_has_external_gate(self):
  c=EuclidOrganismCNS();cycle=c.create((self.directive(),));behavior=c.behavior.report();internal=c.publication.manuscript('EUCLID Study',cycle,behavior,['controlled protocol'],['coherent cycle'],[]);self.assertFalse(internal['external_ready']);external=c.publication.manuscript('EUCLID Study',cycle,behavior,['controlled protocol'],['coherent cycle'],['doi:example']);self.assertTrue(external['external_ready']);seminar=c.publication.seminar('EUCLID Seminar',external);self.assertEqual(seminar['source_evidence_hash'],external['evidence_hash'])
 def test_identity_is_neither_agi_nor_asi(self):
  c=EuclidOrganismCNS();self.assertFalse(c.health_report()['identity']['agi']);self.assertFalse(c.health_report()['identity']['asi'])
if __name__=='__main__':unittest.main()
