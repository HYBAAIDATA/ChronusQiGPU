"""Exact six-stage adapter with explicit hybrid placement, never fake dispatch.

The real existing OpenCL Lucas kernel executes the Lucas value; all six-stage
records are independently constructed/verified by the exact host datapath.
The five other stages are declared host stages, NOT silently called GPU work.
All-device placement remains UNAVAILABLE. No throughput figure is generated.
"""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
from itertools import islice
import json
from pathlib import Path
import threading
import time
from .base import BackendAbsent,CompileError,DispatchError,PipelineSpec,Capability,CompiledKernel,BatchResult,ExecutionReceipt,default_pipeline_spec
from ..lucas_datapath import DatapathConfig,SpatialLucasPipeline


class OpenCLAdapter:
    name='opencl';kind='opencl';fail_closed=True
    def __init__(self,device_selector=None,prime_rom_limit=100000,max_batch=4096,execution_profile='hybrid_exact'):
        if type(prime_rom_limit)is not int or not 1<=prime_rom_limit<=100000 or type(max_batch)is not int or not 1<=max_batch<=65536:raise ValueError('bounded adapter ROM/batch required')
        if execution_profile not in('hybrid_exact','all_device_exact'):raise ValueError('explicit exact execution placement required')
        self.device_selector=device_selector;self.prime_rom_limit=prime_rom_limit;self.max_batch=max_batch;self.execution_profile=execution_profile
        self._overlay=None;self._capability=None;self._last=None;self._details=None;self._compiled={};self._lock=threading.RLock();self._closed=False
    def _validate_spec(self,spec):
        if not isinstance(spec,PipelineSpec)or type(spec.working_width)is not int or not 8<=spec.working_width<=256:raise CompileError('exact OpenCL working width is 8..256')
        if spec!=default_pipeline_spec(spec.working_width):raise CompileError('canonical six-stage exact spec required; no stage substitution')
        if self.execution_profile!='hybrid_exact':raise BackendAbsent('all-six-stages physical GPU placement is unavailable; explicit hybrid profile required')
    def probe(self):
        with self._lock:
            if self._closed:raise BackendAbsent('OpenCL adapter closed')
            if self._overlay is None:
                from ..igpu.overlay import OpenCLOverlay
                self._overlay=OpenCLOverlay(self.device_selector)
            cap=self._overlay.capability()
            if cap.get('physical')is not True or 'lucas_mod256'not in cap.get('operations',[]):raise BackendAbsent('actual compiled exact Lucas device capability required')
            identity=hashlib.sha256(json.dumps({k:cap.get(k)for k in('device_id','vendor','driver','kernel_sha256')},sort_keys=True).encode()).hexdigest()
            current=Capability(cap['device_id'],'opencl',cap['driver'],identity,True,True)
            if self._capability is not None and current!=self._capability:raise BackendAbsent('OpenCL adapter device identity changed')
            self._capability=current;return current
    def _compile_identity(self,spec):
        from ..igpu import overlay
        from .. import lucas_datapath
        cap=self.probe()
        body={'spec':spec.digest(),'profile':self.execution_profile,'prime_rom_limit':self.prime_rom_limit,'max_batch':self.max_batch,'device_id':cap.device_id,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'overlay_sha256':hashlib.sha256(Path(overlay.__file__).read_bytes()).hexdigest(),'datapath_sha256':hashlib.sha256(Path(lucas_datapath.__file__).read_bytes()).hexdigest(),'stage_placement':{'lucas':'opencl_exact_integer_with_host_verification','cassini':'host_exact','zeckendorf':'host_exact','prime':'host_exact_rom','binet':'host_exact','pisot':'host_exact'}}
        return hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest(),body
    def compile(self,spec):
        self._validate_spec(spec)
        with self._lock:
            identity,body=self._compile_identity(spec)
            if identity not in self._compiled:
                if len(self._compiled)>=16:raise CompileError('compiled exact adapter profile quota')
                config=DatapathConfig(spec.working_width,6,self.prime_rom_limit,'opencl_exact_hybrid')
                self._compiled[identity]=(spec,SpatialLucasPipeline(config),body)
            return CompiledKernel(self.name,identity,spec)
    def dispatch(self,kernel,batch):
        if not isinstance(kernel,CompiledKernel)or kernel.backend!=self.name:raise DispatchError('compiled adapter identity required')
        self._validate_spec(kernel.pipeline_spec)
        values=list(islice(iter(batch),self.max_batch+1))
        if len(values)>self.max_batch or any(type(n)is not int or not 0<=n<min(self.prime_rom_limit,1<<kernel.pipeline_spec.working_width)for n in values):raise DispatchError('bounded exact rung/ROM domain required')
        with self._lock:
            identity,body=self._compile_identity(kernel.pipeline_spec)
            if identity!=kernel.kernel_digest or identity not in self._compiled:raise DispatchError('adapter implementation/profile substitution')
            _,pipeline,_=self._compiled[identity];started=time.perf_counter()
            records=tuple(pipeline.process_batch(values));device_values=self._overlay.execute_lucas(values,kernel.pipeline_spec.working_width)
            if device_values!=tuple(r.value for r in records):raise DispatchError('independent device/datapath Lucas mismatch')
            for record in records:pipeline.verify(record)
            self.probe();elapsed=time.perf_counter()-started
            # Performance remains unqualified. Exact execution and stage placement
            # are recorded separately; no modeled/measured rate is fabricated.
            self._last=ExecutionReceipt('opencl_exact_hybrid','hybrid_exact',self._capability.device_id,identity,kernel.pipeline_spec.digest(),None,None,None,False,datetime.now(timezone.utc).isoformat(),None)
            self._details={'schema':'chronos.exact_adapter_execution/1','requested_algorithm':'six_stage_lucas_exact_v1','planned_algorithm':'six_stage_lucas_exact_v1','executed_algorithm':'six_stage_lucas_exact_v1','implementation_module':__name__,'implementation_digest':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'requested_pipeline_digest':kernel.pipeline_spec.digest(),'compiled_identity':identity,'execution_profile':self.execution_profile,'stage_placement':body['stage_placement'],'records_executed':len(records),'device_lucas_evaluations':len(values),'all_six_stages_independently_verified':True,'sha256d_evaluations':0,'fallback_used':False,'all_device_pipeline_claimed':False,'throughput_rps':None,'performance_qualified':False}
            return BatchResult(records,'opencl_exact_hybrid',identity,elapsed,False)
    def receipt(self):
        if self._last is None:raise RuntimeError('no verified OpenCL adapter dispatch')
        return self._last
    def receipt_details(self):
        if self._details is None:raise RuntimeError('no exact adapter evidence')
        return json.loads(json.dumps(self._details))
    def close(self):
        with self._lock:
            if not self._closed:
                if self._overlay is not None:self._overlay.queue.finish()
                self._closed=True;self._compiled.clear()
