"""Resident logical accelerator with bounded, lane-striped host execution.

Virtual units are scheduling addresses, never fabricated silicon execution units.
All operations stay under ONE iGPU's exact authority and executor bindings.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass,asdict
import hashlib,json,math,threading,time
import numpy as np
from ..adapters.base import BackendAbsent
from ..lucas_engine import lucas
from .scaled_plan import LADDER
from .intrinsics import execute_intrinsic

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
@dataclass(frozen=True)
class ResidentConfig:
    host_binding:str="auto"
    base_units:int=8
    scale_index:int=15
    virtual_units:int|None=None
    max_workers:int=2
    max_inflight:int=4
    tile_items:int=128
    max_items:int=65536
    max_bytes:int=4*1024*1024
    def validate(self):
        bounds={'base_units':(1,1000000),'max_workers':(1,8),'max_inflight':(1,32),'tile_items':(1,4096),'max_items':(1,1000000),'max_bytes':(1024,32*1024*1024)}
        for key,(lo,hi)in bounds.items():
            if type(getattr(self,key))is not int or not lo<=getattr(self,key)<=hi:raise ValueError('resident resource quota: '+key)
        if self.host_binding not in ('auto','native','opencl','metal'):raise ValueError('resident binding policy')
        if type(self.scale_index)is not int or self.scale_index not in LADDER:raise ValueError('undeclared resident rung')
        if self.virtual_units is not None and(type(self.virtual_units)is not int or not 1<=self.virtual_units<=1000000):raise ValueError('virtual unit quota')
        return True
    @property
    def units(self):return self.virtual_units if self.virtual_units is not None else min(1000000,self.base_units*lucas(self.scale_index))
    def manifest(self):
        self.validate();return {**asdict(self),'virtual_units':self.units,'lucas_factor':lucas(self.scale_index),'allocation_class':'logical_lanes_not_silicon','physical_throughput_multiplier':None}

class ResidentRuntime:
    def __init__(self,gpu,config=None):
        self.gpu=gpu;self.config=config or ResidentConfig();self.config.validate();self.lock=threading.Lock();self.active=False
    def manifest(self):
        c=self.gpu.compose();overlay=self.gpu.fabric.overlay
        device=None if overlay is None else overlay.capability()
        return {'schema':'chronos_resident_v1','logical_device':'chronos_igpu','resident':True,
                'mode':'independent'if overlay is None else'host_gpu_composed','overlay_unavailable_reason':self.gpu.fabric.reason,
                'host_executor':device or c['executors'][0],'physical_compute_units':None if device is None else device.get('physical_compute_units'),
                'working_width':self.gpu.plan_config.working_width,'native_operations_always_available':True,'scaling':self.config.manifest()}
    def execute(self,kind,payload,deadline=None,cancel=None,require_host_gpu=False):
        if kind not in ('intrinsics','lucas','tensor'):raise ValueError('unsupported resident workload kind')
        if not isinstance(payload,dict)or len(canonical(payload))>self.config.max_bytes:raise ValueError('resident payload quota')
        p=json.loads(canonical(payload)) # immutable admitted snapshot
        if deadline is not None and(type(deadline)not in(int,float)or not math.isfinite(deadline)or time.perf_counter()>=deadline):raise ValueError('resident deadline expired')
        if cancel is not None and not isinstance(cancel,threading.Event):raise ValueError('cancellation event required')
        route=self.gpu.fabric.route('tensor'if kind=='tensor'else'intrinsic'if kind=='intrinsics'else'lucas')
        if type(require_host_gpu)is not bool:raise ValueError('explicit physical execution policy required')
        bound=self.gpu.fabric.overlay
        if require_host_gpu and(kind=='intrinsics'or route.executor=='cpu_reference'or bound is None or bound.capability().get('physical')is not True):raise BackendAbsent('requested operation has no physical GPU executor')
        if kind=='tensor':
            if set(p)!={'operator','left','right'}or p['operator'] not in ('matmul','add','hadamard','scale'):raise ValueError('resident tensor row-wise operation required')
            a=np.asarray(p['left']);b=np.asarray(p['right']);op=p['operator']
            if a.ndim!=2 or not np.isfinite(a).all()or not np.isfinite(b).all()or a.size+b.size>self.config.max_items:raise ValueError('bounded resident matrices required')
            if op=='matmul'and(b.ndim!=2 or a.shape[1]!=b.shape[0]or a.shape[0]*b.shape[1]>self.config.max_items):raise ValueError('resident matmul shape/output quota')
            if op in ('add','hadamard')and a.shape!=b.shape:raise ValueError('matching tensor shapes required')
            if op=='scale'and b.ndim!=0:raise ValueError('resident scalar required')
            total=len(a)
        else:
            key='nodes'if kind=='intrinsics'else'rungs'
            if set(p)!={key}or not isinstance(p[key],list)or len(p[key])>self.config.max_items:raise ValueError('resident exact item quota')
            values=p[key];total=len(values)
        with self.lock:
            if self.active:raise RuntimeError('resident session backpressure')
            self.active=True
        started=time.perf_counter();records=[];output_bytes=0;peak=0;stopped=False
        # One stream for a physical adapter; no concurrent command queues or false
        # promotion of virtual lane count into actual host threads.
        workers=1 if route.executor!='cpu_reference'else self.config.max_workers
        effective_units=min(total,self.config.units)
        width=min(self.config.tile_items,max(1,(total+max(1,effective_units)-1)//max(1,effective_units)))
        def interrupted():return (cancel is not None and cancel.is_set())or(deadline is not None and time.perf_counter()>=deadline)
        def task(start,stop):
            if kind=='intrinsics':
                result=[execute_intrinsic(n)for n in values[start:stop]];backend='cpu_exact'
            elif kind=='lucas':
                res=self.gpu.dispatch(values[start:stop]);res.verify();result=[n.value for n in res.records];backend=res.backend
            else:
                right=b[start:stop]if op in ('add','hadamard')else b
                result=self.gpu.tensor(op,a[start:stop],right).tolist();backend=route.executor
            return {'start':start,'stop':stop,'logical_lane':(start//width)%self.config.units,'backend':backend,'output':result}
        try:
            with ThreadPoolExecutor(max_workers=workers,thread_name_prefix='chronos-resident')as pool:
                pending=[];cursor=0
                while cursor<total or pending:
                    if interrupted():stopped=True
                    while not stopped and cursor<total and len(pending)<self.config.max_inflight:
                        stop=min(total,cursor+width);pending.append(pool.submit(task,cursor,stop));cursor=stop;peak=max(peak,len(pending))
                    if not pending:break
                    # Settle already dispatched work before cancellation receipt.
                    record=pending.pop(0).result();output_bytes+=len(canonical(record))
                    if output_bytes>self.config.max_bytes:raise MemoryError('resident output byte quota exceeded')
                    records.append(record)
            completed=sum(v['stop']-v['start']for v in records)
            result={'schema':'chronos_resident_result_v1','logical_device':'chronos_igpu','manifest':self.manifest(),'kind':kind,
                    'input_digest':hashlib.sha256(canonical(p)).hexdigest(),'completed_items':completed,'admitted_items':total,
                    'status':'complete'if completed==total else'cancelled','deadline_exceeded':deadline is not None and time.perf_counter()>=deadline,'cancellation_observed':cancel is not None and cancel.is_set(),'actual_worker_limit':workers,'peak_inflight':peak,
                    'completed_tiles':records,'elapsed_seconds':time.perf_counter()-started,'hardware_throughput_multiplier':None}
            result['receipt_digest']=hashlib.sha256(canonical(result)).hexdigest()
            self.verify(result,p)
            self.gpu.golden.attest('resident_'+kind,started,details={'receipt_digest':result['receipt_digest'],'completed_items':completed,'virtual_units':self.config.units,'executor_backends':sorted({v['backend']for v in records})})
            return result
        finally:
            with self.lock:self.active=False
    @staticmethod
    def verify(result,payload):
        body=dict(result);digest=body.pop('receipt_digest',None)
        if digest!=hashlib.sha256(canonical(body)).hexdigest()or result['input_digest']!=hashlib.sha256(canonical(payload)).hexdigest():raise ValueError('resident custody mismatch')
        pos=0
        for record in result['completed_tiles']:
            if type(record['start'])is not int or type(record['stop'])is not int or record['start']!=pos or record['stop']<=pos or len(record['output'])!=record['stop']-pos:raise ValueError('resident coverage violation')
            pos=record['stop']
        if pos!=result['completed_items']or pos>result['admitted_items']or (result['status']=='complete')!=(pos==result['admitted_items']):raise ValueError('resident settlement violation')
        if result['kind']=='intrinsics':
            from .intrinsics import verify_intrinsic
            for record in result['completed_tiles']:
                for index,receipt in enumerate(record['output'],record['start']):
                    if canonical(receipt['node'])!=canonical(payload['nodes'][index]):raise ValueError('resident intrinsic identity mismatch')
                    verify_intrinsic(receipt)
        elif result['kind']=='lucas':
            width=result['manifest']['working_width']
            if type(width)is not int or not 8<=width<=256:raise ValueError('resident exact width invalid')
            for record in result['completed_tiles']:
                expected=[lucas(n)%(1<<width)for n in payload['rungs'][record['start']:record['stop']]]
                if canonical(record['output'])!=canonical(expected):raise ValueError('resident Lucas host verification failed')
        else:
            from .tensor_runtime import tensor_deviation_ok
            from fractions import Fraction
            a=np.asarray(payload['left']);b=np.asarray(payload['right']);op=payload['operator']
            for record in result['completed_tiles']:
                right=b[record['start']:record['stop']]if op in ('add','hadamard')else b
                actual=np.asarray(record['output'])
                # Certified envelope: FP64 executors at unit 2**-52, device
                # executors at unit 2**-23 -- no flat heuristic tolerance.
                unit=Fraction(1,2**23)if record['backend']not in ('cpu_reference','cpu_exact')else Fraction(1,2**52)
                try:
                    ok=tensor_deviation_ok(op,actual,a[record['start']:record['stop']],right,unit=unit)
                except ValueError as exc:
                    raise ValueError(f'resident tensor host verification failed: {exc}')from exc
                if not ok:raise ValueError('resident tensor failed certified host verification')
        return True
