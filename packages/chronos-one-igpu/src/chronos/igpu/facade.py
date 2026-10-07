"""Unified Chronos-owned facade; requested topology is not execution evidence."""
from __future__ import annotations
from dataclasses import dataclass
import time
from ..lucas_datapath import DatapathConfig, DatapathRecord, SpatialLucasPipeline
from ..adapters.base import BackendAbsent
from .host import HostGPUPlan
from .store import PrimeDB
from .golden_runtime import GoldenRuntime
@dataclass(frozen=True)
class OneIGPUResult:
    mode: str
    backend: str
    plan: dict
    records: tuple[DatapathRecord, ...]
    config: DatapathConfig | None = None
    evidence: dict | None = None
    def verify(self):
        if self.config is None: raise ValueError('missing verification configuration')
        pipeline = SpatialLucasPipeline(self.config)
        for record in self.records: pipeline.verify(record)
        return True
class OneIGPU:
    """One iGPU API: exact core, PRIME-DB, solve-first search and CPU evidence.

    Legacy integrated/overlay modes describe requested logical layouts only.
    Hardware-required dispatch fails closed until an execution adapter is bound.
    """
    def __init__(self, mode='standalone', lanes=8, working_width=256,
                 prime_rom_limit=100_000, db_path=None, golden_quantum_enabled=True,
                 max_candidates=64, require_accelerator=False, host_adapter=None, device_selector=None, evidence_key=None):
        from threading import RLock
        self._hendrix_lock = RLock()
        HostGPUPlan(0, lanes, mode, 'cpu_reference').validate()
        from .fabric import ComputeFabric
        self.fabric=ComputeFabric(mode,require_accelerator,host_adapter,device_selector)
        self.mode = mode; self.backend = 'cpu_reference'; self.lanes = lanes
        self.plan_config = DatapathConfig(working_width, 6, prime_rom_limit, self.backend)
        self.pipeline = SpatialLucasPipeline(self.plan_config)
        self.db = PrimeDB(db_path) if db_path else None
        self.golden = GoldenRuntime(self.db, golden_quantum_enabled, max_candidates,evidence_key)
        self.golden.fabric=self.fabric;self.golden.inventory=self.fabric
    def dispatch(self, rungs):
        values = list(rungs); plan = HostGPUPlan(len(values), self.lanes, self.mode, self.backend)
        start = time.perf_counter(); records = tuple(self.pipeline.process_batch(values))
        values_computed,route,receipt=self.fabric.execute_lucas(values,self.plan_config.working_width)
        if values_computed!=tuple(r.value for r in records): raise ValueError('fabric/exact datapath mismatch')
        self.backend=route.executor
        manifest=plan.manifest();manifest['logical_device']='chronos_igpu';manifest['executor']=route.executor
        event = self.golden.attest('lucas', start, manifest, {'records': len(records), 'hardware_accelerated': bool(receipt and receipt.get('physical')), 'route':route.__dict__,'overlay_receipt':receipt}, execution={'backend':route.executor,'device':route.bound_device,'capability':route.capability})
        return OneIGPUResult(self.mode, self.backend, manifest, records, self.plan_config, event)
    def put(self, payload, sequence_index, scale=15, family='fibonacci'):
        if self.db is None: raise RuntimeError('OneIGPU was created without a PrimeDB path')
        return self.db.put(payload, sequence_index, scale, family)
    def search(self, candidates, predicate, max_evaluations=4096):
        return self.golden.search(candidates, predicate, max_evaluations)
    def evolve(self, amplitudes, hamiltonian, time_value=1.0):
        return self.golden.evolve(amplitudes, hamiltonian, time_value)
    def mine(self, header_prefix, target, lease, **kwargs):
        return self.golden.mine(header_prefix, target, lease, **kwargs)
    def checkpoint(self, data, index=0): return self.golden.checkpoint(data, index)
    def restore(self, object_id): return self.golden.restore(object_id)
    def tensor(self, operation, left, right=None):
        from .tensor_runtime import tensor_operation
        start = time.perf_counter();route=self.fabric.route('tensor')
        result = self.fabric.overlay.execute_tensor(operation,left,right)if route.executor!='cpu_reference'else tensor_operation(operation, left, right)
        self.golden.attest('tensor_'+operation, start, details={'shape': list(result.shape), 'dtype': str(result.dtype)},execution={'backend':route.executor,'device':route.bound_device,'capability':'tensor'})
        return result
    def mps(self, n_qubits, bond_dim=16, max_bytes=64*1024*1024, allow_lossy=False):
        from .tensor_runtime import SafeMatrixProductState
        start = time.perf_counter(); result = SafeMatrixProductState(n_qubits, bond_dim, max_bytes, allow_lossy)
        self.golden.attest('mps_allocate', start, details={'qubits': n_qubits, 'physical_bytes': result.memory_bytes(), 'allow_lossy': allow_lossy})
        return result
    def render(self, scene='default', n_faces=32, layers=4):
        from ..engine import ChronosEngine
        if not 1 <= n_faces <= 512 or not 1 <= layers <= 64: raise ValueError('render dimensions exceed facade quota')
        start = time.perf_counter(); result = ChronosEngine(n_faces, layers).render(scene)
        self.golden.attest('render', start, details={'frame_shape': list(result.frame_shape), 'faces': n_faces})
        return result
    def capabilities(self): return self.fabric.compose()
    def compose(self): return self.fabric.compose()
    def route(self,operation,scale_index=15): return self.fabric.route(operation,scale_index)
    def scaled_plan(self,base_items,scale_index=15,start=0,address_limit=2**32):
        return self.fabric.scaled_plan(base_items,scale_index,start,self.lanes,address_limit)
    def scaled_search(self,base_items,predicate,scale_index=15,start=0,max_evaluations=4096):
        plan=self.scaled_plan(base_items,scale_index,start)
        result=self.golden.search(range(plan.start,plan.start+plan.effective_items),predicate,max_evaluations,scale_index)
        return {'plan':plan.manifest(),'result':result}
    def fold_exact(self,values):
        from .exact_fold import ExactFoldState
        started=time.perf_counter();result=ExactFoldState.fold(values);result.verify()
        self.golden.attest('exact_fold',started,details={'items':result.count,'digest':result.digest})
        return result
    def witness_cache(self,path,total_budget_bytes=100_000_000_000,image_bytes=4_000_000_000):
        from .witness_cache import WitnessCache
        return WitnessCache(path,total_budget_bytes,image_bytes)
    def mine_swarm(self,prefix,target,lease,workers=1,max_evaluations=65536,**kwargs):
        from .control import SwarmCoordinator
        started=time.perf_counter();result=SwarmCoordinator(workers).scan(prefix,target,lease,max_evaluations,**kwargs)
        self.golden.attest('swarm_sha256d',started,details=result);return result
    def execute_qx(self,buffer,seed=0):
        from .qx import QXExecutor
        started=time.perf_counter();result=QXExecutor().execute(buffer,seed)
        self.golden.attest('qx',started,details=result);return result
    def uci_parameters(self,**overrides): return self.golden.uci.parameterize(**overrides)
    def execute_workload(self,workload):
        from .virtual_abi import VirtualRuntime
        if not hasattr(self,"virtual_runtime"):self.virtual_runtime=VirtualRuntime(self)
        return self.virtual_runtime.execute_once(workload)
    def ingest_certified(self,values,sequence_index=15,scale_index=15,family='exact_state_vector',lineage=()):
        from .contracts import CertifiedMLAObject
        if self.db is None:raise RuntimeError('certified persistence requires PrimeDB')
        obj=CertifiedMLAObject.create(values,sequence_index,scale_index,family,lineage)
        return self.db.put(obj.to_dict(),sequence_index,scale_index,'certified_mla_v2')
    def retrieve_certified(self,stored_id,mode='GET EXACT'):
        from .contracts import CertifiedMLAObject
        if self.db is None:raise RuntimeError('certified retrieval requires PrimeDB')
        return CertifiedMLAObject.from_dict(self.db.get(stored_id).payload).retrieve(mode)
    def close(self):
        if self.db is not None: self.db.close()
    def __enter__(self): return self
    def __exit__(self, *args): self.close()

    def family_certificate(self,indices):
        from ..family_algebra import FamilyCertificate
        started=time.perf_counter();result=FamilyCertificate.create(indices);FamilyCertificate.verify(result)
        self.golden.attest('family_compose',started,details={'indices':result['indices'],'combined_index':result['combined_index'],'digest':result['digest']})
        return result
    def neural_rank(self,candidates,features,ranker):
        values=tuple(candidates)
        if len(values)>self.golden.max_candidates:raise ValueError('neural candidate quota exceeded')
        started=time.perf_counter();ranked=tuple(ranker.rank(values,features))
        if len(ranked)!=len(values)or len(set(values))!=len(values)or set(ranked)!=set(values):raise ValueError('neural ordering changed candidate ownership')
        receipt=ranker.last_receipt or {}
        self.golden.attest('neural_rank',started,details={'candidates':len(values),'model_receipt':receipt},execution={'backend':receipt.get('backend','unknown'),'device':receipt.get('backend','unknown'),'capability':'neural_rank'})
        return ranked

    def configure_asic_like(self,require_native=False):
        from .asic_mining import PreparedSHA256d
        adapter=PreparedSHA256d(require_native=require_native)
        self.fabric.bind_mining_executor(adapter);return adapter
    def bind_asic_driver(self,driver):
        from .asic_mining import ASICDriverBridge
        adapter=ASICDriverBridge(driver);self.fabric.bind_mining_executor(adapter);return adapter
    def mine_asic(self,job,lease,**kwargs):
        from .asic_mining import MiningFarm
        started=time.perf_counter();lanes=kwargs.pop('lanes',1);batch_size=kwargs.pop('batch_size',1024);max_inflight=kwargs.pop('max_inflight',2)
        farm=kwargs.pop('farm',None)or MiningFarm(lanes=lanes,batch_size=batch_size,max_inflight=max_inflight)
        if not farm.ledger.is_current(job):farm.ledger.activate(job)
        result=farm.scan(job,lease,**kwargs);MiningFarm.verify_receipt(result)
        self.golden.attest('asic_like_mining',started,details={'receipt_digest':result['receipt_digest'],'job_commitment':job.commitment,'scan_sha256d_evaluations':result['scan_sha256d_evaluations'],'lanes':lanes},execution={'backend':result['backend'],'device':'host_prepared_mining','capability':'sha256d_midstate'})
        return result

    def checkpoint_mining(self,result):
        from .asic_mining import MiningFarm
        if self.db is None:raise RuntimeError('mining checkpoint requires persistent PrimeDB')
        MiningFarm.verify_receipt(result);started=time.perf_counter()
        obj=self.db.put(result,1,family='asic_mining_checkpoint')
        self.golden.attest('asic_checkpoint',started,details={'object_id':obj.object_id,'receipt_digest':result['receipt_digest']})
        return obj
    def restore_mining(self,object_id):
        from .asic_mining import MiningFarm
        if self.db is None:raise RuntimeError('mining restore requires persistent PrimeDB')
        obj=self.db.get(object_id);result=obj.payload;MiningFarm.verify_receipt(result);return result

    def configure_solver(self,mode="auto",cache_enabled=True):
        self.golden.solver_cache.set_mode(mode);self.golden.solver_cache.enabled=bool(cache_enabled)
        return self.golden.solver_cache.stats()
    def structured_ground(self,amplitudes,phi=None,backend="auto"):
        from .structured_solver import StructuredHamiltonian
        started=time.perf_counter();result=StructuredHamiltonian(amplitudes,self.golden.constants.phi if phi is None else phi).ground(backend)
        self.golden.attest("structured_ground",started,details=result.evidence)
        return result

    def compute_pythi(self,header,policy=None):
        from ..pythi_native import compute_receipt,verify_receipt,NativePolicy
        policy=policy or NativePolicy();started=time.perf_counter();receipt=compute_receipt(header,policy)
        exact=self.dispatch([receipt["rung"]]);exact.verify()
        if exact.records[0].value!=receipt["lucas_value"]:raise ValueError("native/exact core value mismatch")
        verify_receipt(receipt,header,policy)
        self.golden.attest("pythi_native_compute",started,details={"certificate_id":receipt["certificate_id"],"rung":receipt["rung"],"admissible":receipt["admissible"],"bitcoin_compatible":False,"consensus_security_proven":False,"network_submitted":False})
        return receipt

    def scaled_mine(self,header_prefix,target,base_items,scale_index=15,start=0,max_evaluations=4096,job_id="scaled",epoch=0,**kwargs):
        from ..golden_quantum import NonceLease
        from dataclasses import asdict
        plan=self.scaled_plan(base_items,scale_index,start)
        lease=NonceLease(plan.start,plan.start+plan.effective_items,job_id,epoch)
        result=self.mine(header_prefix,target,lease,max_evaluations=max_evaluations,scale_index=scale_index,**kwargs)
        return {"plan":plan.manifest(),"result":asdict(result)}

    def structured_matvec(self,amplitudes,vector,phi=None,backend="cpu"):
        from .structured_solver import StructuredHamiltonian
        from ..adapters.base import BackendAbsent
        operator=StructuredHamiltonian(amplitudes,self.golden.constants.phi if phi is None else phi);started=time.perf_counter()
        if backend=="cpu":result=operator.matvec(vector);execution={"backend":"cpu_structured","device":"host_cpu","capability":"structured_matvec"}
        elif backend=="host_gpu":
            adapter=self.fabric.overlay
            if adapter is None or not adapter.capability().get("physical")or not hasattr(adapter,"execute_structured_matvec"):raise BackendAbsent("physical structured GPU executor required")
            result=adapter.execute_structured_matvec(operator,vector);execution={"backend":adapter.capability()["backend"],"device":adapter.capability()["device_id"],"capability":"structured_matvec"}
        else:raise ValueError("unknown structured matvec backend")
        self.golden.attest("structured_matvec",started,details={"dimension":operator.n,"matrix_materialized":False},execution=execution)
        return result

    def resident(self,config=None):
        from .resident import ResidentRuntime,ResidentConfig
        from ..adapters.base import BackendAbsent
        import platform
        config=config or ResidentConfig();config.validate()
        if self.fabric.overlay is None and config.host_binding!='native':
            if config.host_binding=='auto':
                if self.fabric.reason is None:
                    try:self.bind_host_gpu('metal'if platform.system()=='Darwin'else'opencl')
                    except BackendAbsent as exc:self.fabric.reason=str(exc)
            else:self.bind_host_gpu(config.host_binding)
        return ResidentRuntime(self,config)

    def bind_host_gpu(self,backend="opencl",device_selector=None):
        from .overlay import OpenCLOverlay
        from .apple import MLXOverlay
        if backend=="opencl":adapter=OpenCLOverlay(device_selector)
        elif backend=="metal":
            if device_selector is not None:raise ValueError("Metal binding uses the system MLX GPU; selector unsupported")
            adapter=MLXOverlay()
        else:raise ValueError("supported physical overlays: opencl, metal")
        capability=adapter.capability()
        if not capability.get("physical"):raise RuntimeError("physical host GPU required")
        self.fabric.overlay=adapter;self.fabric.reason=None
        return capability

    def projection_analysis(self,rung_bits=8):
        from ..projection_analysis import projection_contract
        return projection_contract(rung_bits)

    def intrinsic(self,node):
        from .intrinsics import execute_intrinsic,verify_intrinsic
        started=time.perf_counter();receipt=execute_intrinsic(node);verify_intrinsic(receipt)
        self.golden.attest("exact_intrinsic",started,details={"digest":receipt["digest"],"intrinsic":node["op"]},execution={"backend":"cpu_exact","device":"host_cpu","capability":"exact_intrinsic"})
        return receipt

    def execute_hendrix(self, artifact, header, target_be, **kwargs):
        from .hendrix_execution import execute_hendrix
        with self._hendrix_lock:
            return execute_hendrix(self, artifact, header, target_be, **kwargs)

    def execute_nonce_batch(self, header, target_be, nonces):
        from .hendrix_execution import execute_nonce_batch
        with self._hendrix_lock:
            return execute_nonce_batch(self, header, target_be, nonces)
