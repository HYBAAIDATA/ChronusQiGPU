"""Equal-work comparison of fresh and reused identical S6 ground-state ranking."""
import json,time,random,platform,hashlib,statistics,os
from pathlib import Path
from chronos import OneIGPU
from chronos.golden_quantum import NonceLease
from run_asic_adjacency import GENESIS

def run():
 owners={'fresh_dense':OneIGPU(),'reused_dense':OneIGPU()}
 import importlib.util
 source=Path(__file__).with_name('reference_v3_8_golden_runtime.py')
 spec=importlib.util.spec_from_file_location('chronos.igpu._reference_v38',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 baseline=owners['fresh_dense'];baseline.golden=module.GoldenRuntime();baseline.golden.fabric=baseline.fabric;baseline.golden.inventory=baseline.fabric
 for name,g in owners.items():g.configure_asic_like(require_native=True)
 rows=[];cold=[];coverage=[]
 for rung in (18,31):
  plan=owners['reused_dense'].scaled_plan(1,rung,address_limit=2**32);size=min(plan.effective_items,4096)
  for jobindex,prefix in enumerate((GENESIS[:76],GENESIS[:68]+(int.from_bytes(GENESIS[68:72],'little')+1).to_bytes(4,'little')+GENESIS[72:76])):
   lease=NonceLease(jobindex*10000,jobindex*10000+size,f'rung-{rung}-job-{jobindex}',rung)
   owners['reused_dense'].golden.solver_cache.clear()
   for name,g in owners.items():
    t=time.perf_counter();p=g.golden.plan(lease);cold.append({'rung':rung,'job':jobindex,'case':name,'elapsed_seconds':time.perf_counter()-t,'order_digest':hashlib.sha256(json.dumps(p['order']).encode()).hexdigest()})
   assert cold[-1]['order_digest']==cold[-2]['order_digest']
   for repeat in range(30):
    order=list(owners);random.Random(4000+rung*100+jobindex*30+repeat).shuffle(order)
    for name in order:
     g=owners[name];out=g.mine(prefix,0,lease,max_evaluations=size,current_epoch=rung)
     assert out.sha256d_evaluations==size and not out.verified and 'S6_chronos_solver'in out.path
     details=g.golden.events[-2]['details'] # plan then scan; negative result has no winner event
     assert details['reason']is None
     rows.append({'rung':rung,'job':jobindex,'repeat':repeat,'case':name,'sha256d_evaluations':out.sha256d_evaluations,'elapsed_seconds':out.elapsed_seconds,'backend':out.backend,'solver_cache_hit':details.get('solver',{}).get('cache_hit',False),'solver_residual':details.get('solver',{}).get('residual'),'order_digest':cold[-1]['order_digest']})
   coverage.append({'rung':rung,'job':jobindex,'plan':plan.manifest(),'executed_per_sample':size,'candidate_count':len(p['order']),'prefix_sha256':hashlib.sha256(prefix).hexdigest()})
 summaries=[]
 for name,g in owners.items():
  subset=[r for r in rows if r['case']==name];hashes=sum(r['sha256d_evaluations']for r in subset);seconds=sum(r['elapsed_seconds']for r in subset)
  summaries.append({'case':name,'completed_sha256d':hashes,'elapsed_seconds':seconds,'aggregate_hashrate':hashes/seconds,'samples':len(subset),'median_seconds':statistics.median(r['elapsed_seconds']for r in subset),'cache_stats':g.golden.solver_cache.stats()if hasattr(g.golden,'solver_cache')else{'enabled':False,'source':'unchanged_v3.8_GoldenRuntime'}});g.close()
 return {'schema':'chronos_deterministic_reuse_benchmark_v1','environment':{'python':platform.python_version(),'platform':platform.platform(),'numpy':__import__('numpy').__version__,'openblas_threads':os.getenv('OPENBLAS_NUM_THREADS'),'omp_threads':os.getenv('OMP_NUM_THREADS'),'cpu':next((line.split(':',1)[1].strip()for line in Path('/proc/cpuinfo').read_text().splitlines()if line.startswith('model name')),None)},'protocol':{'runs_per_job_rung':30,'rungs':[18,31],'jobs':['Bitcoin genesis prefix','genesis-derived timestamp+1 prefix (derived control)'],'zero_target':True,'shuffled_path_order':True,'warm_comparison':True,'full_pipeline':True,'reference_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'sparse_solver':False,'hardware':'CPU','real_pool':False},'coverage':coverage,'cold_plan_observations':cold,'observations':rows,'summary':summaries,'ratio':summaries[1]['aggregate_hashrate']/summaries[0]['aggregate_hashrate']}
if __name__=='__main__':
 data=run();Path('benchmarks/deterministic-reuse-results.json').write_text(json.dumps(data,indent=2)+'\n');print(json.dumps({'ratio':data['ratio'],'summary':data['summary']}))
