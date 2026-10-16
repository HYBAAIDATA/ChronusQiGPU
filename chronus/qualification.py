"""Fail-closed target GPU mining qualification; never upgrades CPU to GPU."""
import hashlib,time,platform,json
from . import OneIGPU
from .golden_quantum import NonceLease,AdvancedMathematicalOracles as Oracle
GENESIS=bytes.fromhex('01000000'+'00'*32+'3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a'+'29ab5f49'+'ffff001d'+'1dac2b7c')
def qualify_target(selector=None,runs=3,nonce_budget=4096):
 if type(runs)is not int or not 1<=runs<=30 or type(nonce_budget)is not int or not 1<=nonce_budget<=4096:raise ValueError('bounded target qualification required')
 result={'schema':'chronos_target_qualification_v1','status':'UNAVAILABLE','selector':selector,'environment':{'python':platform.python_version(),'platform':platform.platform()},'hardware_measured':False,'samples':[],'pool_submitted':False}
 created=time.perf_counter()
 try:
  with OneIGPU(mode='host_gpu_overlay',require_accelerator=True,device_selector=selector)as g:
   result['context_creation_seconds']=time.perf_counter()-created;result['inventory']=g.compose();adapter=g.fabric.overlay;capability=adapter.capability()
   if not capability.get('physical')or capability.get('backend')!='opencl':raise ValueError('physical OpenCL executor required')
   probe=[0,1,2083236893,2**32-1];outputs=adapter.execute_sha256d(GENESIS[:76],probe)
   if tuple(outputs)!=tuple(Oracle.nonce_digest(GENESIS[:76],n)for n in probe):raise ValueError('GPU known-vector qualification failed')
   result['known_vector_probe']='PASS';result['probe_receipt']=adapter.last_receipt
   if 'structured_matvec'in capability.get('operations',[]):
    import numpy as np
    from .igpu.structured_solver import StructuredHamiltonian
    a=np.ones(64,dtype=np.complex128)/8;op=StructuredHamiltonian(a,g.golden.constants.phi);out=adapter.execute_structured_matvec(op,np.linspace(0,1,64));result['structured_matvec']={'status':'MEASURED_TARGET','receipt':adapter.last_receipt}
   else:result['structured_matvec']={'status':'UNAVAILABLE','reason':'fp64 capability absent'}
   for rung in(18,31):
    for temperature in('cold_host_solver','warm_host_solver'):
     for repeat in range(runs):
      if temperature=='cold_host_solver':g.golden.solver_cache.clear()
      out=g.scaled_mine(GENESIS[:76],0,1,rung,max_evaluations=nonce_budget,job_id='qualification',epoch=1)
      if out['result']['backend']!='opencl'or out['result']['sha256d_evaluations']!=nonce_budget or out['result']['verified']:raise ValueError('target mining execution mismatch')
      receipt=adapter.last_receipt
      if not receipt.get('physical')or receipt.get('kernel_seconds',-1)<0:raise ValueError('missing GPU profiling evidence')
      result['samples'].append({'rung':rung,'phase':temperature,'repeat':repeat,'result':out['result'],'device_receipt':receipt})
   result.update(status='MEASURED_TARGET',hardware_measured=True,cache_scope='Cold/warm applies to host solver cache; OpenCL context retained, vector probe warmed the device. Context startup recorded separately.')
 except Exception as exc:
  result.update(status='UNAVAILABLE_OR_FAILED',reason=f'{type(exc).__name__}: {exc}',hardware_measured=False)
 result['evidence_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest();return result
