"""Versioned standalone accelerator ABI; canonical request/result custody."""
from dataclasses import dataclass
import hashlib,json,re,time,threading
from ..golden_quantum import NonceLease

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
@dataclass(frozen=True)
class Workload:
    workload_id:str
    tenant:str
    operation:str
    payload:dict
    quota:int=4096
    trust_class:str='host_verified'
    deadline:object=None
    schema:str='virtual_igpu_v1'
    def validate(self):
        if self.schema!='virtual_igpu_v1':raise ValueError('unsupported ABI version')
        if not all(isinstance(v,str)and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',v)for v in(self.workload_id,self.tenant)):raise ValueError('invalid ABI identity')
        if type(self.quota)is not int or not 0<=self.quota<=1000000:raise ValueError('ABI quota violation')
        if self.trust_class not in('host_verified','unsigned_local'):raise ValueError('requested trust class is not provided by the standalone execution root')
        if self.operation not in('lucas','fold','sha256d','asic_sha256d','tensor','evolve','qx','structured_ground','pythi_native','intrinsic','resident','exact_features'):raise ValueError('unsupported ABI operation')
        if not isinstance(self.payload,dict)or len(canonical(self.payload))>4*1024*1024:raise ValueError('invalid payload/quota')
        if self.deadline is not None and(not isinstance(self.deadline,(int,float))or not __import__('math').isfinite(self.deadline)or time.perf_counter()>=self.deadline):raise ValueError('ABI deadline expired')
        return True
    def body(self):return {'schema':self.schema,'workload_id':self.workload_id,'tenant':self.tenant,'operation':self.operation,'payload':self.payload,'quota':self.quota,'trust_class':self.trust_class,'deadline':self.deadline}
    def digest(self):self.validate();return hashlib.sha256(canonical(self.body())).hexdigest()
class VirtualRuntime:
    def __init__(self,gpu,max_active=16,max_tenant_active=4):self.gpu=gpu;self.max_active=max_active;self.max_tenant_active=max_tenant_active;self.active={};self.lock=threading.Lock()
    def execute(self,workload):
        workload.validate();digest=workload.digest();tenant=workload.tenant
        with self.lock:
            if sum(self.active.values())>=self.max_active or self.active.get(tenant,0)>=self.max_tenant_active:raise RuntimeError('ABI backpressure admission rejected')
            self.active[tenant]=self.active.get(tenant,0)+1
        start=time.perf_counter()
        try:
            p=workload.payload;op=workload.operation
            if op=='lucas':
                if len(p['rungs'])>workload.quota:raise ValueError('Lucas workload quota')
                result=self.gpu.dispatch(p['rungs']);result.verify();output={'values':[r.value for r in result.records],'certificates':[r.certificate for r in result.records]};backend=result.backend
            elif op=='fold':
                if len(p['values'])>workload.quota:raise ValueError('fold workload quota')
                f=self.gpu.fold_exact(p['values']);output=f.to_dict();backend='cpu_reference'
            elif op=='sha256d':
                from dataclasses import asdict
                output=asdict(self.gpu.mine(bytes.fromhex(p['header_prefix']),int(p['target']),NonceLease(**p['lease']),max_evaluations=workload.quota,deadline=workload.deadline,scale_index=p.get('scale_index',15)));backend=output['backend']
            elif op=='asic_sha256d':
                from .asic_mining import MiningJob
                job=MiningJob.from_manifest(p['job'])
                output=self.gpu.mine_asic(job,NonceLease(**p['lease']),max_evaluations=workload.quota,lanes=p.get('lanes',1),batch_size=p.get('batch_size',1024),max_inflight=p.get('max_inflight',2),deadline=workload.deadline);backend=output['backend']
            elif op=='structured_ground':
                import numpy as np
                if len(p['real'])!=len(p.get('imag',[0]*len(p['real'])))or len(p['real'])>workload.quota:raise ValueError('structured workload quota')
                result=self.gpu.structured_ground(np.asarray(p['real'])+1j*np.asarray(p.get('imag',[0]*len(p['real']))),p.get('phi'),p.get('backend','auto'))
                output={'real':result.vector.real.tolist(),'imag':result.vector.imag.tolist(),'evidence':result.evidence};backend=result.evidence['backend']
            elif op=='pythi_native':
                from ..pythi_native import NativePolicy,MAX_HEADER_BYTES
                if workload.quota<1 or not isinstance(p['header_hex'],str)or not 2<=len(p['header_hex'])<=2*MAX_HEADER_BYTES:raise ValueError('native header workload quota')
                output=self.gpu.compute_pythi(bytes.fromhex(p['header_hex']),NativePolicy.from_dict(p.get('policy',{})));backend='cpu_exact_native_protocol'
            elif op=='intrinsic':
                if workload.quota<1:raise ValueError('intrinsic quota')
                output=self.gpu.intrinsic(p['node']);backend='cpu_exact'
            elif op=='resident':
                from .resident import ResidentConfig
                config=ResidentConfig(**p.get('config',{}));config.validate()
                if config.max_items>workload.quota:raise ValueError('resident quota exceeds admitted ABI quota')
                output=self.gpu.resident(config).execute(p['kind'],p['data'],deadline=workload.deadline,require_host_gpu=p.get('require_host_gpu',False));backend='resident_composed'
            elif op=='exact_features':
                from .feature_profile import FeatureProfile
                from .feature_runtime import FeatureConfig
                if workload.quota<1 or set(p)!={'profile','task'}:raise ValueError('sealed exact feature ABI payload/quota')
                profile=FeatureProfile.from_dict(p['profile'])
                with self.gpu.feature_runtime(profile,FeatureConfig(max_scalar_ops=workload.quota))as runtime:
                    output=runtime.execute(p['task'])
                backend='cpu_exact_features'
            elif op=='tensor':
                import numpy as np
                if np.size(p['left'])+np.size(p.get('right',[]))>workload.quota:raise ValueError('tensor workload quota')
                output=self.gpu.tensor(p['operator'],p['left'],p.get('right')).tolist();backend=self.gpu.fabric.route('tensor').executor
            elif op=='evolve':
                if len(p['amplitudes'])>workload.quota:raise ValueError('state workload quota')
                from .exact_quantum import encode_expression,decode_evolution_payload
                amplitudes,hamiltonian,t=decode_evolution_payload(p)
                evolved=self.gpu.evolve(amplitudes,hamiltonian,t);a=evolved.amplitudes
                output={'real':[encode_expression(x)for x in a.real],
                        'imag':[encode_expression(x)for x in a.imag],
                        'encoding':'exact_expression_tree_v1','execution_receipt':evolved.evidence};backend='cpu_exact_symbolic'
            else:
                from .qx import QXBuffer
                if len(p['commands'])>workload.quota:raise ValueError('QX workload quota')
                output=self.gpu.execute_qx(QXBuffer.seal(p['commands']),p.get('seed',0));backend='cpu_reference'
            if workload.deadline is not None and time.perf_counter()>workload.deadline:raise TimeoutError('ABI deadline exceeded during execution')
            result_digest=hashlib.sha256(canonical(output)).hexdigest()
            receipt={'schema':'virtual_igpu_v1','workload_id':workload.workload_id,'tenant':tenant,'logical_device':'chronos_igpu','backend':backend,
                     'workload_digest':digest,'result_digest':result_digest,'trust_class':workload.trust_class,'elapsed_seconds':time.perf_counter()-start,
                     'hardware_root_claimed':False,'output':output}
            receipt['receipt_digest']=hashlib.sha256(canonical(receipt)).hexdigest()
            if op in('evolve','exact_features'): self.verify_receipt(receipt,workload)
            self.gpu.golden.attest('virtual_abi',start,details={'workload_digest':digest,'receipt_digest':receipt['receipt_digest'],'tenant':tenant})
            return receipt
        finally:
            with self.lock:self.active[tenant]-=1
    def execute_once(self,workload,max_records=128,max_cache_bytes=32*1024*1024):
        """Session-bounded idempotency; no automatic replay after a partial failure."""
        from concurrent.futures import Future
        workload.validate()
        sealed=Workload(**json.loads(canonical(workload.body())))
        digest=sealed.digest();identity=(sealed.tenant,sealed.workload_id)
        # Initialisation is serialized with the existing runtime admission lock.
        with self.lock:
            if not hasattr(self,'once_records'):self.once_records={};self.once_bytes=0
            if identity in self.once_records:
                record=self.once_records[identity]
                if record['digest']!=digest:raise ValueError('idempotency identity reused with different work')
                future=record['future'];owner=False
            else:
                reserve=4*1024*1024
                if len(self.once_records)>=max_records or self.once_bytes+reserve>max_cache_bytes:raise RuntimeError('idempotency cache admission quota')
                future=Future();self.once_records[identity]={'digest':digest,'future':future};self.once_bytes+=reserve;owner=True
        if not owner:
            timeout=None if sealed.deadline is None else max(0,sealed.deadline-time.perf_counter())
            return json.loads(future.result(timeout=timeout))
        try:
            result=self.execute(sealed);encoded=canonical(result)
            if len(encoded)>reserve:raise ValueError('idempotent result exceeds cache record quota')
            with self.lock:self.once_bytes+=len(encoded)-reserve
            future.set_result(encoded);return json.loads(encoded)
        except Exception as exc:
            with self.lock:self.once_bytes-=reserve
            future.set_exception(RuntimeError('recorded execution failure; use a new workload ID after reconciliation: '+type(exc).__name__))
            raise

    @staticmethod
    def verify_receipt(receipt,workload):
        body=dict(receipt);digest=body.pop('receipt_digest')
        if hashlib.sha256(canonical(body)).hexdigest()!=digest or body['workload_digest']!=workload.digest()or body['result_digest']!=hashlib.sha256(canonical(body['output'])).hexdigest():raise ValueError('ABI receipt custody mismatch')
        if body['tenant']!=workload.tenant or body['workload_id']!=workload.workload_id or body['hardware_root_claimed'] or body['trust_class']!=workload.trust_class or body['schema']!=workload.schema or body['logical_device']!='chronos_igpu':raise ValueError('ABI identity/trust mismatch')
        if workload.operation=='exact_features':
            from .feature_profile import FeatureProfile
            from .feature_runtime import FeatureConfig
            from .facade import OneIGPU
            if body['backend']!='cpu_exact_features':raise ValueError('exact feature ABI substrate mismatch')
            profile=FeatureProfile.from_dict(workload.payload['profile'])
            with OneIGPU()as verifier:
                with verifier.feature_runtime(profile,FeatureConfig(max_scalar_ops=workload.quota))as runtime:
                    runtime.verify(body['output'])
            if body['output']['task']!=workload.payload['task']:raise ValueError('exact feature ABI request substitution')
        if workload.operation=='evolve':
            from .exact_quantum import exact_hamiltonian_evolution,encode_expression,decode_evolution_payload
            if body['backend']!='cpu_exact_symbolic':raise ValueError('exact evolution substrate mismatch')
            amplitudes,hamiltonian,t=decode_evolution_payload(workload.payload)
            replayed=exact_hamiltonian_evolution(amplitudes,hamiltonian,t,legacy_encoding=True)
            expected={'real':[encode_expression(x)for x in replayed.amplitudes.real],
                      'imag':[encode_expression(x)for x in replayed.amplitudes.imag],
                      'encoding':'exact_expression_tree_v1','execution_receipt':replayed.evidence}
            if body['output']!=expected:raise ValueError('exact evolution implementation replay failed')
        return True
