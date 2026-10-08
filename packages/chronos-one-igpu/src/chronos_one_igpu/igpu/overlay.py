"""Physical OpenCL host overlay beneath the independent Chronos contract device."""
from importlib.resources import files
import hashlib,time
import numpy as np
from ..adapters.base import BackendAbsent,DispatchError
class OpenCLOverlay:
    def __init__(self,device_selector=None):
        try:
            import pyopencl as cl
            devices=[d for p in cl.get_platforms()for d in p.get_devices(device_type=cl.device_type.GPU)]
            if device_selector:devices=[d for d in devices if device_selector.lower()in(f'{d.vendor} {d.name}').lower()]
            if not devices:raise BackendAbsent('no matching physical OpenCL GPU')
            # Prefer integrated Intel devices only with unified memory evidence.
            devices.sort(key=lambda d:(not('intel'in d.vendor.lower()and d.host_unified_memory and any(t in d.name.lower()for t in('uhd','iris'))),d.vendor,d.name))
            self.device=devices[0];self.cl=cl;self.context=cl.Context([self.device]);self.queue=cl.CommandQueue(self.context,properties=cl.command_queue_properties.PROFILING_ENABLE)
            self.source=files('chronos_one_igpu').joinpath('igpu/kernels/lucas256.cl').read_text()
            self.program=cl.Program(self.context,self.source).build();self.kernel=cl.Kernel(self.program,'chronos_lucas256')
            kernel_max=self.kernel.get_work_group_info(cl.kernel_work_group_info.WORK_GROUP_SIZE,self.device)
            self.workgroup=max(1,min(64,self.device.max_work_group_size,kernel_max,self.device.max_work_item_sizes[0]))
            self.sha_source=files('chronos_one_igpu').joinpath('igpu/kernels/sha256d.cl').read_text()
            self.sha_program=cl.Program(self.context,self.sha_source).build();self.sha_kernel=cl.Kernel(self.sha_program,'chronos_sha256d')
            self.last_receipt=None
        except BackendAbsent:raise
        except Exception as exc:raise BackendAbsent(f'OpenCL overlay unavailable: {exc}')from exc
    def capability(self):
        return {'device_id':self.device.name,'vendor':self.device.vendor,'driver':self.device.driver_version,
                'backend':'opencl','physical':True,'physical_compute_units':int(self.device.max_compute_units),'physical_compute_units_kind':'OpenCL max_compute_units','operations':['lucas_mod256','sha256d']+(['structured_matvec']if 'cl_khr_fp64'in self.device.extensions.split()else[]),
                'host_unified_memory':bool(self.device.host_unified_memory),'workgroup_limit':self.workgroup,
                'kernel_sha256':hashlib.sha256(self.source.encode()).hexdigest()}
    def execute_lucas(self,rungs,width=256):
        values=list(rungs)
        if type(width)is not int or not 8<=width<=256:raise ValueError('overlay width must be 8..256')
        if any(type(n)is not int or not 0<=n<2**64 for n in values):raise ValueError('OpenCL rung transport requires u64')
        if not values:return ()
        a=np.array(values,dtype=np.uint64);out=np.empty((len(a),8),dtype=np.uint32)
        if max(a.nbytes,out.nbytes)>self.device.max_mem_alloc_size or a.nbytes+out.nbytes>self.device.global_mem_size:raise DispatchError('device memory admission failed')
        cl=self.cl;start=time.perf_counter();flags=cl.mem_flags
        inp=cl.Buffer(self.context,flags.READ_ONLY|flags.COPY_HOST_PTR,hostbuf=a);buf=cl.Buffer(self.context,flags.WRITE_ONLY,out.nbytes)
        self.kernel.set_args(inp,buf,np.uint32(len(a)))
        global_size=((len(a)+self.workgroup-1)//self.workgroup)*self.workgroup
        event=cl.enqueue_nd_range_kernel(self.queue,self.kernel,(global_size,),(self.workgroup,))
        cl.enqueue_copy(self.queue,out,buf,wait_for=[event]).wait()
        result=tuple(sum(int(word)<<(32*i)for i,word in enumerate(row))&((1<<width)-1)for row in out)
        # Every device result is compared with independent exact host arithmetic.
        from ..lucas_engine import lucas
        if result!=tuple(lucas(n)% (1<<width)for n in values):raise DispatchError('OpenCL/host Lucas mismatch')
        self.last_receipt={**self.capability(),'items_executed':len(a),'host_verified':True,
                           'kernel_seconds':(event.profile.end-event.profile.start)*1e-9,
                           'wall_seconds':time.perf_counter()-start,'executor':'opencl',
                           'physical_throughput_multiplier':None}
        return result
    def execute_sha256d(self,prefix,nonces):
        values=list(nonces)
        if not isinstance(prefix,bytes)or len(prefix)!=76 or any(type(n)is not int or not 0<=n<2**32 for n in values):raise ValueError('SHA256d header/nonce contract violation')
        if not values:return ()
        cl=self.cl
        if not hasattr(self,'sha_program'):
            self.sha_source=files('chronos_one_igpu').joinpath('igpu/kernels/sha256d.cl').read_text()
            self.sha_program=cl.Program(self.context,self.sha_source).build();self.sha_kernel=cl.Kernel(self.sha_program,'chronos_sha256d')
        limit=self.sha_kernel.get_work_group_info(cl.kernel_work_group_info.WORK_GROUP_SIZE,self.device)
        local=max(1,min(64,limit,self.device.max_work_group_size,self.device.max_work_item_sizes[0]))
        a=np.array(values,dtype=np.uint32);p=np.frombuffer(prefix,dtype=np.uint8);out=np.empty((len(a),8),dtype=np.uint32)
        if max(a.nbytes,out.nbytes)>self.device.max_mem_alloc_size or a.nbytes+out.nbytes+p.nbytes>self.device.global_mem_size:raise DispatchError('SHA256d device allocation quota')
        flags=cl.mem_flags;start=time.perf_counter()
        bp=cl.Buffer(self.context,flags.READ_ONLY|flags.COPY_HOST_PTR,hostbuf=p);bn=cl.Buffer(self.context,flags.READ_ONLY|flags.COPY_HOST_PTR,hostbuf=a);bo=cl.Buffer(self.context,flags.WRITE_ONLY,out.nbytes)
        self.sha_kernel.set_args(bp,bn,bo,np.uint32(len(a)))
        event=cl.enqueue_nd_range_kernel(self.queue,self.sha_kernel,(((len(a)+local-1)//local)*local,),(local,))
        cl.enqueue_copy(self.queue,out,bo,wait_for=[event]).wait()
        result=tuple(b''.join(int(word).to_bytes(4,'big')for word in row)for row in out)
        self.last_receipt={**self.capability(),'items_executed':len(a),'operation':'sha256d','executor':'opencl','kernel_sha256':hashlib.sha256(self.sha_source.encode()).hexdigest(),
                           'kernel_seconds':(event.profile.end-event.profile.start)*1e-9,'wall_seconds':time.perf_counter()-start,'physical_throughput_multiplier':None}
        return result

def _execute_structured_matvec(self,operator,vector):
    """Physical fp64 OpenCL matrix-vector application, not a GPU eigensolve."""
    from .structured_solver import StructuredHamiltonian
    if not isinstance(operator,StructuredHamiltonian):raise ValueError('structured operator required')
    raw=np.asarray(vector)
    if raw.shape!=(operator.n,)or np.iscomplexobj(raw)and np.any(raw.imag!=0)or not np.isfinite(raw).all():raise ValueError('finite real structured vector required')
    if 'cl_khr_fp64'not in self.device.extensions.split():raise BackendAbsent('fp64 structured OpenCL capability absent')
    cl=self.cl;started=time.perf_counter()
    source=files('chronos_one_igpu').joinpath('igpu/kernels/structured_matvec.cl').read_text()
    if not hasattr(self,'structured_program'):
        self.structured_program=cl.Program(self.context,source).build();self.structured_partial=cl.Kernel(self.structured_program,'chronos_rank2_partials');self.structured_apply=cl.Kernel(self.structured_program,'chronos_structured_apply')
    bounds=[self.device.max_work_group_size,self.device.max_work_item_sizes[0],64,self.device.local_mem_size//16]
    for kernel in(self.structured_partial,self.structured_apply):bounds.append(kernel.get_work_group_info(cl.kernel_work_group_info.WORK_GROUP_SIZE,self.device))
    limit=min(bounds)
    if limit<1:raise DispatchError('structured launch/local-memory quota')
    width=1<<(int(limit).bit_length()-1);n=operator.n;groups=(n+width-1)//width;x=np.ascontiguousarray(raw.real,dtype=np.float64);partials=np.empty((groups,2),dtype=np.float64);out=np.empty(n,dtype=np.float64)
    arrays=[operator.diagonal,operator.real,operator.imag,x,partials,out]
    if max(a.nbytes for a in arrays)>self.device.max_mem_alloc_size or sum(a.nbytes for a in arrays)>self.device.global_mem_size:raise DispatchError('structured device memory quota')
    flags=cl.mem_flags;bd,br,bi,bx=[cl.Buffer(self.context,flags.READ_ONLY|flags.COPY_HOST_PTR,hostbuf=a)for a in arrays[:4]];bp=cl.Buffer(self.context,flags.WRITE_ONLY,partials.nbytes);bo=cl.Buffer(self.context,flags.WRITE_ONLY,out.nbytes)
    self.structured_partial.set_args(br,bi,bx,bp,np.uint32(n),cl.LocalMemory(width*8),cl.LocalMemory(width*8));first=cl.enqueue_nd_range_kernel(self.queue,self.structured_partial,(groups*width,),(width,));cl.enqueue_copy(self.queue,partials,bp,wait_for=[first]).wait();dots=partials.sum(axis=0)
    self.structured_apply.set_args(bd,br,bi,bx,bo,np.uint32(n),np.float64(operator.off),np.float64(dots[0]),np.float64(dots[1]));second=cl.enqueue_nd_range_kernel(self.queue,self.structured_apply,(groups*width,),(width,));cl.enqueue_copy(self.queue,out,bo,wait_for=[second]).wait()
    if not np.isfinite(out).all():raise DispatchError('structured OpenCL nonfinite output')
    # Exact host verification: recompute y = H x in exact rational
    # arithmetic and bound the device result by a sound FP64 forward-error
    # envelope (each kernel flop contributes at most ulp(=2^-52) of its
    # row's absolute term sum); the check is certified, not a tolerance.
    if not operator.matvec_deviation_ok(out,x):raise DispatchError('structured OpenCL output outside certified error envelope')
    self.last_receipt={**self.capability(),'operation':'structured_matvec','items_executed':n,'dtype':'float64','host_verified':True,'matrix_materialized':False,'kernel_sha256':hashlib.sha256(source.encode()).hexdigest(),'kernel_seconds':sum((e.profile.end-e.profile.start)*1e-9 for e in(first,second)),'wall_seconds':time.perf_counter()-started,'host_partial_reduction':True,'local_size':width,'groups':groups,'executor':'opencl','physical_throughput_multiplier':None}
    return out
OpenCLOverlay.execute_structured_matvec=_execute_structured_matvec

def _execute_hendrix_order(self, compiled, position, count):
    """Reusable real device program/state, with exact CPU ordering parity."""
    from collections import OrderedDict
    v = compiled.as_dict()
    expected, expected_binding = compiled.batch(position, count)
    if count == 0:
        return expected, expected_binding
    if not hasattr(self, '_hendrix_program'):
        self._hendrix_source = files('chronos_one_igpu').joinpath('igpu/kernels/hendrix600.cl').read_text()
        self._hendrix_program = self.cl.Program(self.context, self._hendrix_source).build()
        self._hendrix_kernel = self.cl.Kernel(self._hendrix_program, 'chronos_hendrix600')
        self._hendrix_buffers = OrderedDict()
    cl = self.cl; flags = cl.mem_flags
    state = self._hendrix_buffers.get(compiled.digest)
    if state is None:
        rows = np.asarray([r[:6] for r in v['shards'] if r[3]], dtype=np.uint64)
        shortest = int(rows[:,3].min())
        wide = np.flatnonzero(rows[:,3] > shortest).astype(np.uint32)
        if not len(wide):wide = np.zeros(1,dtype=np.uint32)
        # Retain the certified geometry transport and exact dual adjacency
        # on device alongside the executable position table. Their bound
        # identity is not reconstructed per candidate or per nonce batch.
        geometry = np.frombuffer(bytes.fromhex(v['geometry']['transport']['folded_hex']),dtype=np.uint8)
        adjacency = np.asarray(v['geometry']['adjacency'],dtype=np.uint32)
        arrays = (rows, wide, geometry, adjacency)
        if max(a.nbytes for a in arrays) > self.device.max_mem_alloc_size or sum(a.nbytes for a in arrays) > self.device.global_mem_size:
            raise DispatchError('resident Hendrix state exceeds device quota')
        buffers = tuple(cl.Buffer(self.context, flags.READ_ONLY|flags.COPY_HOST_PTR,hostbuf=a) for a in arrays)
        state = (buffers, len(rows), shortest)
        self._hendrix_buffers[compiled.digest] = state
        if len(self._hendrix_buffers)>4:self._hendrix_buffers.popitem(last=False)
    buffers, active, shortest = state
    out = np.empty(count,dtype=np.uint32);binding = np.empty((count,2),dtype=np.uint32)
    bo=cl.Buffer(self.context,flags.WRITE_ONLY,out.nbytes);bb=cl.Buffer(self.context,flags.WRITE_ONLY,binding.nbytes)
    self._hendrix_kernel.set_args(buffers[0],buffers[1],np.uint64(v['window']),np.uint64(v['hendrix_stride']),np.uint64(position),np.uint32(active),np.uint64(shortest),np.uint32(count),bo,bb)
    limit=self._hendrix_kernel.get_work_group_info(cl.kernel_work_group_info.WORK_GROUP_SIZE,self.device)
    local=max(1,min(64,limit,self.device.max_compute_units,self.device.max_work_item_sizes[0],self.device.max_work_group_size))
    global_size=((count+local-1)//local)*local
    event=cl.enqueue_nd_range_kernel(self.queue,self._hendrix_kernel,(global_size,),(local,))
    cl.enqueue_copy(self.queue,out,bo,wait_for=[event]).wait();cl.enqueue_copy(self.queue,binding,bb).wait()
    if not np.array_equal(out,expected) or not np.array_equal(binding,expected_binding):
        raise DispatchError('resident Hendrix device/CPU ordering mismatch')
    self._hendrix_order_receipt={'backend':'opencl','kernel_launch_count':1,'kernel_seconds':(event.profile.end-event.profile.start)*1e-9,'kernel_sha256':hashlib.sha256(self._hendrix_source.encode()).hexdigest(),'resident_execution_digest':compiled.digest,'host_order_verified':True,'geometry_operations_counted_as_hashes':False}
    return out,binding

OpenCLOverlay.execute_hendrix_order = _execute_hendrix_order
