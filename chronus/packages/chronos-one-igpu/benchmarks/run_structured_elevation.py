"""Cold/warm full-pipeline structured vs frozen v3.8.1 dense S6 comparison."""
import json,time,random,platform,hashlib,importlib.util,os
from pathlib import Path
from chronos import OneIGPU
from chronos.golden_quantum import NonceLease
from chronos.qualification import GENESIS
from chronos.pythi_native import verify_receipt

def run():
 source=Path(__file__).with_name('reference_v3_8_1_solver_cache.py');spec=importlib.util.spec_from_file_location('chronos.igpu._reference_solver_v381',source);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
 owners={'v381_dense':OneIGPU(),'v39_structured':OneIGPU()};owners['v381_dense'].golden.solver_cache=old.DeterministicSolverCache();owners['v39_structured'].configure_solver('structured')
 for g in owners.values():g.configure_asic_like(require_native=True)
 rows=[];coverage=[]
 for rung in (18,31):
  for job,prefix in enumerate((GENESIS[:76],GENESIS[:68]+(int.from_bytes(GENESIS[68:72],'little')+1).to_bytes(4,'little')+GENESIS[72:76])):
   lease=NonceLease(job*10000,job*10000+4096,f'rung-{rung}-job-{job}',1)
   orders=[]
   for g in owners.values():orders.append(g.golden.plan(lease,scale_index=rung)['order'])
   assert orders[0]==orders[1]
   coverage.append({'rung':rung,'job':job,'plan':owners['v39_structured'].scaled_plan(1,rung).manifest(),'budget':4096,'order_digest':hashlib.sha256(json.dumps(orders[0]).encode()).hexdigest(),'equal_candidate_order':True})
   for phase in ('cold_solver','warm_solver'):
    for g in owners.values():g.golden.solver_cache.enabled=phase=='warm_solver';g.golden.solver_cache.clear();g.golden.plan(lease,scale_index=rung)
    for repeat in range(30):
     cases=list(owners);random.Random(8000+rung+job*100+repeat).shuffle(cases)
     for case in cases:
      g=owners[case];out=g.mine(prefix,0,lease,max_evaluations=4096,current_epoch=1,scale_index=rung);details=g.golden.events[-2]['details'];meta=details['solver']
      assert out.sha256d_evaluations==4096 and not out.verified and details['reason']is None and 'S6_chronos_solver'in out.path
      if case=='v39_structured':assert meta['backend']=='native_structured_cpu'and not meta['matrix_materialized']and meta['dense_fallback_reason']is None
      assert g.golden.events[-1]['lucas_rung']==rung
      rows.append({'rung':rung,'job':job,'phase':phase,'repeat':repeat,'case':case,'completed_sha256d':out.sha256d_evaluations,'elapsed_seconds':out.elapsed_seconds,'hash_backend':out.backend,'solver_backend':meta.get('backend',meta['solver']),'cache_hit':meta['cache_hit'],'residual':meta['residual'],'advisory_dimension':meta['dimension']})
 for g in owners.values():g.close()
 summaries=[]
 for phase in ('cold_solver','warm_solver'):
  for case in owners:
   r=[x for x in rows if x['phase']==phase and x['case']==case];total=sum(x['completed_sha256d']for x in r);duration=sum(x['elapsed_seconds']for x in r);summaries.append({'phase':phase,'case':case,'completed_sha256d':total,'elapsed_seconds':duration,'aggregate_hashrate':total/duration,'samples':len(r)})
 # Native computation is a different workload/unit, never a SHA256d-equivalent.
 native=[]
 with OneIGPU()as g:
  for i in range(32):
   header=GENESIS+(i).to_bytes(4,'little');t=time.perf_counter();r=g.compute_pythi(header);elapsed=time.perf_counter()-t;assert verify_receipt(r,header);native.append({'index':i,'header_digest':r['header_digest'],'rung':r['rung'],'certificate_id':r['certificate_id'],'elapsed_seconds':elapsed,'verified':True})
 return {'schema':'chronos_structured_elevation_v1','environment':{'python':platform.python_version(),'platform':platform.platform(),'numpy':__import__('numpy').__version__,'cpu':next((s.split(':',1)[1].strip()for s in Path('/proc/cpuinfo').read_text().splitlines()if s.startswith('model name')),None),'openblas_threads':os.getenv('OPENBLAS_NUM_THREADS'),'omp_threads':os.getenv('OMP_NUM_THREADS')},'scope':{'full_pipeline':True,'rungs':[18,31],'prefixes':['genesis','genesis timestamp+1 derived control'],'samples_per_path_phase':120,'nonces_per_sample':4096,'advisory_dimension':64,'cold_definition':'S6 result not reused; native hash midstate and process remain warm','warm_definition':'S6 identical-input cache populated before samples','matrix_free':True,'physical_gpu':False,'physical_asic':False,'pooled_hashratios_not_multiplied':True},'reference_solver_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'coverage':coverage,'observations':rows,'summary':summaries,'native_compute_observations':native,'native_protocol_scope':'32 local computation receipts; no chain/consensus/pool/competitor comparison'}
if __name__=='__main__':
 x=run();Path('benchmarks/structured-elevation-results.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps({'summary':x['summary'],'native_receipts':len(x['native_compute_observations'])}))
