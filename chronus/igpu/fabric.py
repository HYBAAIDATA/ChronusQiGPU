"""The independent iGPU contract owns host executors, not the reverse."""
from dataclasses import dataclass,asdict
from ..adapters.base import BackendAbsent,DispatchError
from .scaled_plan import ScaledPlan,LADDER
from .overlay import OpenCLOverlay
CONTRACT={'schema':'chronos_standalone_igpu_v1','device_id':'chronos_igpu','name':'Chronos MLA1517 iGPU',
          'is_gpu':True,'physical':False,'independent_of_physical_gpu':True,'memory_model':'host_unified','device_count':1,'one_igpu':True,
          'lucas_ladder':list(LADDER),'operations':['lucas','search','fold','unfold','partial_unfold','tensor','evolve','witness','qx','sha256d','structured_ground','structured_matvec','pythi_native','intrinsic','resident']}
@dataclass(frozen=True)
class RouteDecision:
    logical_device:str
    executor:str
    operation:str
    capability:str
    bound_device:str
    scale_index:int
    fallback_reason:object=None
class ComputeFabric:
    def __init__(self,mode='standalone',require_accelerator=False,host_adapter=None,device_selector=None):
        self.mode=mode;self.overlay=host_adapter;self.reason=None;self.mining_adapter=None
        if self.overlay is None and(mode=='host_gpu_overlay'or require_accelerator):
            try:self.overlay=OpenCLOverlay(device_selector)
            except BackendAbsent as exc:
                self.reason=str(exc)
                if require_accelerator:raise
        if require_accelerator and not self.overlay.capability().get('physical'):raise BackendAbsent('physical executor required')
    def compose(self):
        executors=[{'device_id':'host_cpu','backend':'cpu_reference','physical':True,'operations':list(CONTRACT['operations'])}]
        if self.overlay is not None:executors.append(self.overlay.capability())
        if self.mining_adapter is not None:executors.append(self.mining_adapter.capability())
        return {'contract_device':dict(CONTRACT),'executors':executors,'overlay_available':self.overlay is not None,'overlay_unavailable_reason':self.reason,'device_count':1,'one_igpu':True,'logical_device':'chronos_igpu', 'unbound_adapters':[{'backend':b,'operations':[],'reason':'not configured in this standalone host'} for b in ('cuda','rocm','metal','asic_mmio','rtl','remote_gpu')]}
    def snapshot(self):return self.compose()
    def route(self,operation,scale_index=15):
        if scale_index not in LADDER:raise ValueError('undeclared Lucas rung')
        if operation not in CONTRACT['operations']:raise ValueError('unknown iGPU operation')
        if operation=='sha256d'and self.mining_adapter is not None:
            c=self.mining_adapter.capability();return RouteDecision('chronos_igpu',c['backend'],operation,'sha256d_midstate',c['device_id'],scale_index)
        if self.overlay is not None and ((operation=='lucas'and hasattr(self.overlay,'execute_lucas'))or(operation=='sha256d'and hasattr(self.overlay,'execute_sha256d'))or(operation=='tensor'and hasattr(self.overlay,'execute_tensor'))or(operation=='structured_matvec'and 'structured_matvec'in self.overlay.capability().get('operations',[])and hasattr(self.overlay,'execute_structured_matvec'))):
            c=self.overlay.capability();return RouteDecision('chronos_igpu',c['backend'],operation,'lucas_mod256' if operation=='lucas' else operation,c['device_id'],scale_index)
        return RouteDecision('chronos_igpu','cpu_reference',operation,operation,'host_cpu',scale_index,self.reason)
    def execute_lucas(self,rungs,width=256,scale_index=15):
        route=self.route('lucas',scale_index)
        if route.executor=='cpu_reference':
            from ..lucas_engine import lucas
            result=tuple(lucas(n)%(1<<width)for n in rungs);return result,route,None
        values=list(rungs);result=tuple(self.overlay.execute_lucas(values,width))
        from ..lucas_engine import lucas
        if result!=tuple(lucas(n)%(1<<width)for n in values):raise DispatchError('host overlay verification failed')
        return result,route,self.overlay.last_receipt
    def scaled_plan(self,base_items,scale_index=15,start=0,lanes=32,address_limit=2**32):return ScaledPlan(base_items,scale_index,start,lanes,address_limit)
    def scan_sha256d(self,prefix,target,lease,order=(),max_evaluations=65536,current_epoch=None,deadline=None):
        from ..golden_quantum import AdvancedMathematicalOracles as Oracle,MiningResult
        from .control import Guardian
        from itertools import chain,islice
        import time
        Guardian().admit(lease,max_evaluations,current_epoch,deadline);Oracle.accepts(bytes(32),target)
        if not isinstance(prefix,bytes)or len(prefix)!=76:raise ValueError('76-byte prefix required')
        priority=list(order)
        if len(priority)>max_evaluations or len(priority)!=len(set(priority))or any(type(n)is not int or not lease.start<=n<lease.stop for n in priority):raise ValueError('invalid ordered nonce ownership')
        seen=set(priority);nonces=chain(priority,(n for n in range(lease.start,lease.stop)if n not in seen));start=time.perf_counter();count=0;found=None;digest=None;verification_evaluations=0
        while count<max_evaluations:
            if deadline is not None and time.perf_counter()>=deadline:break
            batch=list(islice(nonces,min(4096,max_evaluations-count)))
            if not batch:break
            adapter=self.mining_adapter or self.overlay
            if adapter is None:raise BackendAbsent('no configured batch mining executor')
            if hasattr(adapter,'scan_nonce_batch'):
                result=adapter.scan_nonce_batch(prefix,batch,target);completed=result['completed'];nonce=result['nonce'];value=result['digest']
                if type(completed)is not int or not 0<=completed<=len(batch):raise DispatchError('fused executor work count violation')
                if nonce is None:
                    if completed!=len(batch)or value is not None:raise DispatchError('fused executor incomplete negative result')
                else:
                    if type(nonce)is not int or nonce not in batch[:completed]or not isinstance(value,bytes)or len(value)!=32 or not Oracle.accepts(value,target)or Oracle.nonce_digest(prefix,nonce)!=value:raise DispatchError('fused candidate failed host/ownership verification')
                    found=nonce;digest=value.hex()
                count+=completed
            else:
                outputs=adapter.execute_sha256d(prefix,batch)
                verification_evaluations+=(adapter.last_receipt or {}).get('verification_sha256d_evaluations',0)
                if len(outputs)!=len(batch):raise DispatchError('SHA256d result count mismatch')
                count+=len(batch)
                for nonce,value in zip(batch,outputs):
                    if Oracle.accepts(value,target):
                        if Oracle.nonce_digest(prefix,nonce)!=value:raise DispatchError('SHA256d candidate failed host verification')
                        found=nonce;digest=value.hex();break
            if found is not None:break
        elapsed=time.perf_counter()-start
        return MiningResult(found,digest,found is not None,count,elapsed,count/elapsed if elapsed else 0,self.route('sha256d').executor,('prepared_batch_executor',),verification_sha256d_evaluations=verification_evaluations+int(found is not None))

    def bind_mining_executor(self,adapter):
        c=adapter.capability()
        if 'sha256d'not in c.get('operations',[])or not hasattr(adapter,'execute_sha256d'):raise BackendAbsent('mining executor lacks executable SHA256d capability')
        self.mining_adapter=adapter;return c
    def has_sha256d_executor(self):
        return self.mining_adapter is not None or(self.overlay is not None and hasattr(self.overlay,'execute_sha256d'))
