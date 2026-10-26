"""Automated production-honest verification for Project EUCLID."""
from __future__ import annotations
import json,tempfile
from pathlib import Path
from .creative_substrate import CreatorDirective,EuclidCreativeKernel,ProvenanceChain,architecture_audit
from .creative_benchmarks import CreativeBenchmarkCase,CreativeBenchmarkSuite
from .organism_cns import EuclidOrganismCNS
from .kairos_runtime import FoldEvent,KairosRuntime
from .kairos_execution import KairosExecutionLayer,OperatorAction
from .kairos_mining_lab_service import KairosMiningLabService,MiningExperimentRequest
from .millennium_math_world import MillenniumMathematicsWorld,MathematicalExperiment,MillenniumProblem
from .kairos_mining_reasoning import StabilityReasoningModule,StabilityObservation

def run_verification()->dict:
 checks=[]
 def check(name,fn):
  try:details=fn();checks.append({'name':name,'passed':True,'details':details})
  except Exception as exc:checks.append({'name':name,'passed':False,'error':f'{type(exc).__name__}: {exc}'})
 with tempfile.TemporaryDirectory() as d:
  root=Path(d);kernel=EuclidCreativeKernel(world_checkpoint=root/'world.json',provenance_checkpoint=root/'provenance.json');cns=EuclidOrganismCNS(kernel)
  directive=CreatorDirective('verification','A coherent world learns through curiosity',structured={'tone':['hopeful'],'themes':['learning'],'aesthetics':['luminous'],'symbols':['compass'],'constraints':{'characters':{'Euclid':{'goal':'discover coherently'}}}})
  cycle=cns.create((directive,),'hybrid')
  check('closed_loop',lambda:{'coherence':cycle.coherence.aggregate,'world':cycle.world.content_hash})
  check('world_restoration',lambda:{'hash':kernel.world_engine.restore().content_hash})
  check('provenance_restoration',lambda:{'head':ProvenanceChain(root/'provenance.json').head,'verified':cycle.provenance_verified})
  check('semantic_determinism',lambda:{'equal':cycle.world.content_hash==EuclidCreativeKernel().run((directive,),mode='hybrid').world.content_hash})
  check('phase_ii_stress',cns.run_phase_ii_stress)
  check('dashboard',lambda:{'schema':cns.dashboard()['schema']})
  check('organism_health',cns.health_report)
  check('benchmark_protocol',lambda:{'lane':CreativeBenchmarkSuite().run((CreativeBenchmarkCase('verification-case',(directive,),('narrative',)),)).claim_lane})
  check('architecture_identity',lambda:architecture_audit()['identity'])
  check('architecture_gap_closure',lambda:architecture_audit()['closed_gaps'])
  def kairos_control_plane():
   runtime=KairosRuntime();world=runtime.create_world('harness-kairos','sha256:'+'a'*64);runtime.bootstrap_world(world.world_id);session=runtime.activate_session(runtime.open_session('harness').session_id)
   result=runtime.dispatch_fold(world.world_id,session.session_id,FoldEvent('frontier_city','symbolic_orchard','build',{'structure':'bridge'},{},{'source':'production_harness'}));checkpoint=runtime.checkpoint_world(world.world_id);replay=runtime.replay_world(world.world_id)
   if result.outcome.value!='ACCEPTED' or not replay['event_hashes']:raise RuntimeError('Kairos control plane verification failed')
   return {'world_hash':result.world_hash,'checkpoint':checkpoint,'replay_events':len(replay['event_hashes'])}
  check('kairos_control_plane',kairos_control_plane)
  def kairos_execution_layer():
   layer=KairosExecutionLayer();world=layer.runtime.create_world('harness-execution','sha256:'+'b'*64);layer.runtime.bootstrap_world(world.world_id);session=layer.runtime.activate_session(layer.runtime.open_session('harness-execution').session_id)
   result=layer.execute(world.world_id,session.session_id,OperatorAction('frontier_city','symbolic_orchard','build',{'structure':'bridge'},{},{'source':'production_harness'}));state=layer.world_state(world.world_id)
   if result.outcome.value!='ACCEPTED' or not result.cns_event_hash or state['state']['domains']['frontier_city']['local_revision']!=1:raise RuntimeError('Kairos execution layer verification failed')
   return {'world_hash':state['world_hash'],'chronicle_head':state['chronicle_head'],'resonance':result.resonance_triggered}
  check('kairos_execution_layer',kairos_execution_layer)
  def kairos_mining_lab_service():
   service=KairosMiningLabService();created=service.create_world('andre','harness-mining-lab','sha256:'+'c'*64)
   request=MiningExperimentRequest('harness-risk-cycle','andre','harness-mining-lab','frontier_city','symbolic_orchard','build',.2,.1,('risk-sentinel',),{'scenario':'forbidden-state rehearsal'},{'source':'production_harness'})
   result=service.execute_experiment(created['session_id'],request)
   if result.outcome!='ACCEPTED' or not result.evidence_gate.passed or 'no live mining' not in result.claim_boundary.lower():raise RuntimeError('Kairos Mining Lab Service verification failed')
   return {'world_hash':result.world_hash,'evidence_class':result.evidence_gate.evidence_class,'routes':len(service.routes())}
  check('kairos_mining_lab_service',kairos_mining_lab_service)
  def millennium_mathematics_world():
   world=MillenniumMathematicsWorld();world.create();result=world.run(MathematicalExperiment('harness-riemann',MillenniumProblem.RIEMANN,'A stated invariant remains explicit under a bounded transformation.',('explicit_premises','counterexample_retention'),{}))
   if result['outcome']!='ACCEPTED' or 'No proof' not in result['claim_boundary']:raise RuntimeError('Millennium Mathematics World verification failed')
   return {'world_hash':result['world_hash'],'problem':result['problem']}
  check('millennium_mathematics_world',millennium_mathematics_world)
  def mining_stability_reasoning():
   service=KairosMiningLabService();created=service.create_world('andre','harness-stability','sha256:'+'s'*64);result=StabilityReasoningModule(service.layer).assess(created['world_id'],StabilityObservation('harness-stable',.15,.10,False,.05,('risk-sentinel',)))
   if not result.accepted or result.policy_proposal!='OBSERVE' or 'not a prediction' not in result.claim_boundary:raise RuntimeError('Mining stability reasoning verification failed')
   return {'posture':result.posture,'policy':result.policy_proposal,'event_hash':result.chronicle_event_hash}
  check('mining_stability_reasoning',mining_stability_reasoning)
 return {'schema':'EUCLID_PRODUCTION_HARNESS_V2','passed':all(x['passed'] for x in checks),'total':len(checks),'passed_count':sum(x['passed'] for x in checks),'checks':checks,'boundaries':{'rendered_media_providers':'deployment_required','network_transports':'deployment_required','distributed_storage':'deployment_required','external_evaluation':'independent_evidence_required','agi':False,'asi':False}}

def main()->int:
 report=run_verification();print(json.dumps(report,sort_keys=True,indent=2,default=str));return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
