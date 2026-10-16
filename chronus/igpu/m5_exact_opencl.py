"""Actual exact integer OpenCL executor; hardware absence never becomes evidence.

GPU domain is the exact dyadic subset of Q(sqrt(2),i), with common denominator
exponent <=60 throughout. Arbitrary rationals remain exact host capabilities;
GPU rejection allows only explicitly authorised reference fallback.
"""
from collections import OrderedDict
from fractions import Fraction
import hashlib
from pathlib import Path
import sys
import threading
from ..adapters.base import BackendAbsent
from .resident import canonical

CODES={'H':0,'X':1,'Z':2,'S':3,'SDG':4,'T':5,'TDG':6,'CX':7,'CZ':8,'SWAP':9}
KERNEL_PATH=Path(__file__).parent/'kernels/m5_exact_dyadic.cl'


def source_identity():
    return {'adapter_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'kernel_sha256':hashlib.sha256(KERNEL_PATH.read_bytes()).hexdigest()}


def pack_exact(chain,initial):
    from .m5_ultra_contract import norm,ONE
    if len(initial)!=1<<chain.pads or norm(initial)!=ONE:raise ValueError('normalised exact GPU input required')
    exponent=0
    for amplitude in initial:
        if len(amplitude)!=4:raise ValueError('exact field input shape')
        for x in amplitude:
            if not isinstance(x,Fraction):raise ValueError('exact Fraction transport required')
            d=x.denominator
            if d&(d-1):raise BackendAbsent('exact GPU domain: dyadic rational coefficients required; no approximation')
            exponent=max(exponent,d.bit_length()-1)
    increments=sum(g[0]in('H','T','TDG')for g in chain.gates)
    if exponent+increments>60:raise BackendAbsent('exact GPU common-denominator exponent quota; no integer overflow fallback')
    numerators=tuple(x.numerator*((1<<exponent)//x.denominator)for a in initial for x in a)
    if any(abs(x)>1<<60 for x in numerators):raise BackendAbsent('exact GPU signed coefficient transport bound')
    plan=tuple((CODES[g[0]],chain.pad_map[g[1]],chain.pad_map[g[2]]if len(g)==3 else 0)for g in chain.gates)
    return numerators,exponent,plan


def unpack_exact(numerators,exponent):
    if type(exponent)is not int or not 0<=exponent<=60 or len(numerators)%4:raise ValueError('bounded exact GPU result shape')
    if any(type(x)is not int or abs(x)>1<<60 for x in numerators):raise ValueError('exact GPU result coefficient bound')
    return tuple(tuple(Fraction(x,1<<exponent)for x in numerators[j:j+4])for j in range(0,len(numerators),4))


def validate_device_contract(contract):
    expected={'backend','executor','substrate','physical_entanglement','implementation_digest','canonical_form','adapter_source_sha256','kernel_sha256','device_fingerprint','device_name','platform_name','driver_version','arithmetic_domain'}
    if not isinstance(contract,dict)or set(contract)!=expected:raise ValueError('exact GPU device contract fields')
    from .m5_ultra_contract import implementation_identity
    fixed={'backend':'GPU','executor':'opencl_exact_dyadic_field','substrate':'detected_gpu_integer_arithmetic','physical_entanglement':False,'implementation_digest':implementation_identity(),'canonical_form':'q_sqrt2_i_four_reduced_rationals/1','arithmetic_domain':'dyadic_q_sqrt2_i_i64_common_exp_le60',**source_identity()}
    if any(contract[k]!=v for k,v in fixed.items())or any(not isinstance(contract[k],str)or not contract[k]for k in('device_name','platform_name','driver_version','device_fingerprint')):raise ValueError('exact GPU implementation/device identity mismatch')
    import re
    if not re.fullmatch('[0-9a-f]{64}',contract['device_fingerprint']):raise ValueError('exact GPU fingerprint')
    return True


class ExactOpenCLExecutor:
    def __init__(self,selector=None):
        try:
            import numpy as np
            import pyopencl as cl
            candidates=[(p,d)for p in cl.get_platforms()for d in p.get_devices(device_type=cl.device_type.GPU)]
            if selector is not None:
                if not isinstance(selector,str)or not selector:raise ValueError('explicit device selector')
                candidates=[(p,d)for p,d in candidates if selector.lower()in(p.name+' '+d.name).lower()]
            if len(candidates)!=1:raise BackendAbsent('select one real exact GPU; none or ambiguous GPU inventory')
            self.platform,self.device=candidates[0]
            if bool(self.device.endian_little)!=(sys.byteorder=='little'):raise BackendAbsent('exact GPU transport requires matching byte order')
            self.cl=cl;self.np=np;self.context=cl.Context([self.device]);self.queue=cl.CommandQueue(self.context)
            self.sources=source_identity();self.program=cl.Program(self.context,KERNEL_PATH.read_text()).build(options=['-cl-std=CL1.2'])
            self.kernel=cl.Kernel(self.program,'m5_gate_step');self.lock=threading.RLock();self.plans=OrderedDict();self.buffers=None
            self.closed=False;self._contract=self._make_contract()
        except BackendAbsent:raise
        except Exception as exc:raise BackendAbsent('exact OpenCL executor unavailable: '+str(exc))from exc
    def _make_contract(self):
        from .m5_ultra_contract import implementation_identity
        descriptor={'vendor':self.device.vendor,'name':self.device.name,'driver':self.device.driver_version,'platform':self.platform.name,'version':self.device.version}
        return {'backend':'GPU','executor':'opencl_exact_dyadic_field','substrate':'detected_gpu_integer_arithmetic','physical_entanglement':False,'implementation_digest':implementation_identity(),'canonical_form':'q_sqrt2_i_four_reduced_rationals/1',**self.sources,'device_fingerprint':hashlib.sha256(canonical(descriptor)).hexdigest(),'device_name':self.device.name,'platform_name':self.platform.name,'driver_version':self.device.driver_version,'arithmetic_domain':'dyadic_q_sqrt2_i_i64_common_exp_le60'}
    def contract(self):
        if self.closed or source_identity()!=self.sources or self._make_contract()!=self._contract:raise BackendAbsent('exact GPU immutable executor identity changed')
        validate_device_contract(self._contract);return dict(self._contract)
    def execute(self,chain,initial):
        values,exponent,rows=pack_exact(chain,initial)
        with self.lock:
            self.contract();cl=self.cl;np=self.np;flags=cl.mem_flags;n=1<<chain.pads;size=n*4*8
            plan_bytes=max(12,len(rows)*12)
            if max(size,plan_bytes)>self.device.max_mem_alloc_size or size*2+plan_bytes+4>self.device.global_mem_size:raise BackendAbsent('exact GPU memory admission quota')
            if self.buffers is None or self.buffers[0]!=size:
                self.buffers=(size,cl.Buffer(self.context,flags.READ_WRITE,size),cl.Buffer(self.context,flags.READ_WRITE,size),cl.Buffer(self.context,flags.READ_WRITE,4))
            _,src,dst,error=self.buffers
            cl.enqueue_copy(self.queue,src,np.asarray(values,dtype=np.int64));cl.enqueue_copy(self.queue,error,np.zeros(1,dtype=np.int32))
            key=hashlib.sha256(canonical({'chain':chain.to_dict(),'plan':rows})).hexdigest()
            if rows:
                if key not in self.plans:
                    if len(self.plans)>=8:self.plans.popitem(last=False)
                    self.plans[key]=cl.Buffer(self.context,flags.READ_ONLY|flags.COPY_HOST_PTR,hostbuf=np.asarray(rows,dtype=np.int32))
                self.plans.move_to_end(key);plan=self.plans[key]
                for stage,gate in enumerate(chain.gates):
                    self.kernel.set_args(src,dst,plan,np.int32(stage),np.int32(n),error)
                    cl.enqueue_nd_range_kernel(self.queue,self.kernel,(n,),None)
                    src,dst=dst,src;exponent+=gate[0]in('H','T','TDG')
            output=np.empty(n*4,dtype=np.int64);status=np.zeros(1,dtype=np.int32)
            cl.enqueue_copy(self.queue,output,src);cl.enqueue_copy(self.queue,status,error).wait();self.queue.finish();self.contract()
            if int(status[0]):raise ArithmeticError('exact GPU overflow/invalid gate; output rejected')
            return unpack_exact([int(x)for x in output],exponent)
    def close(self):
        with self.lock:
            if not self.closed:self.queue.finish();self.closed=True;self.plans.clear();self.buffers=None


def integer_kernel_counts(chain):
    """Exact source-level helper calls/writes, not cycles or throughput."""
    n=1<<chain.pads;counts={'checked_add_calls':0,'checked_negation_calls':0,'checked_doubling_calls':0,'coefficient_writes':4*n*len(chain.gates),'kernel_dispatches':len(chain.gates),'coefficient_buffer_shape':[2,n,4],'count_scope':'integer kernel helper calls and coefficient writes, not ISA instructions'}
    for gate in chain.gates:
        kind=gate[0]
        if kind=='H':counts['checked_add_calls']+=4*n;counts['checked_negation_calls']+=2*n;counts['checked_doubling_calls']+=2*n
        elif kind in('T','TDG'):counts['checked_add_calls']+=2*n;counts['checked_negation_calls']+=(1 if kind=='T'else 3)*n;counts['checked_doubling_calls']+=3*n
        elif kind in('S','SDG','CZ'):counts['checked_negation_calls']+=n
        elif kind=='Z':counts['checked_negation_calls']+=2*n
    return counts
