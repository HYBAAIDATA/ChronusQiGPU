"""Integer kernel body conformance on CPU; NOT OpenCL/GPU execution evidence."""
import ctypes
from fractions import Fraction
import pathlib
import random
import shutil
import subprocess
import pytest
from chronos_one_igpu import OneIGPU
from chronos_one_igpu.m5_ultra import elevate_pads
from chronos_one_igpu.adapters.base import BackendAbsent
from chronos_one_igpu.igpu.m5_exact_opencl import KERNEL_PATH,pack_exact,unpack_exact,ExactOpenCLExecutor
from chronos_one_igpu.igpu.m5_ultra_contract import OperatorChain,initial_state,fast_apply,reference_apply,encode,ONE,ZERO,device_contract

@pytest.fixture(scope='module')
def kernel_body(tmp_path_factory):
    gcc=shutil.which('gcc')
    if gcc is None:pytest.skip('CPU C-compiler conformance unavailable; not a GPU pass')
    assert ctypes.sizeof(ctypes.c_long)==8
    folder=tmp_path_factory.mktemp('kernel-cpu-body');c=folder/'body.c';lib=folder/'body.so'
    shim='''#include <stddef.h>
#define __global
#define __kernel
#define inline static inline
static size_t host_gid;
static size_t get_global_id(int dim){(void)dim;return host_gid;}
static int atomic_or(volatile int*p,int x){int old=*p;*p|=x;return old;}
'''
    c.write_text(shim+KERNEL_PATH.read_text()+'''\nvoid cpu_stage(const long*src,long*dst,const int*plan,int stage,int dimension,int*error){for(host_gid=0;host_gid<(size_t)dimension;host_gid++)m5_gate_step(src,dst,plan,stage,dimension,error);}\n''')
    result=subprocess.run([gcc,'-shared','-fPIC','-std=c99','-Wall','-Wextra','-Werror',str(c),'-o',str(lib)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    fn=ctypes.CDLL(str(lib)).cpu_stage;fn.argtypes=[ctypes.POINTER(ctypes.c_long),ctypes.POINTER(ctypes.c_long),ctypes.POINTER(ctypes.c_int),ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_int)]
    return fn


def execute_cpu_kernel_body(fn,chain,initial):
    values,exponent,rows=pack_exact(chain,initial);n=len(initial);src=(ctypes.c_long*(n*4))(*values);dst=(ctypes.c_long*(n*4))();plan=(ctypes.c_int*(3*len(rows)))(*(x for row in rows for x in row));error=ctypes.c_int()
    for stage,gate in enumerate(chain.gates):
        fn(src,dst,plan,stage,n,ctypes.byref(error));assert error.value==0;src,dst=dst,src;exponent+=gate[0]in('H','T','TDG')
    return unpack_exact(list(src),exponent)

@pytest.mark.parametrize('gate,arity',[('H',1),('X',1),('Z',1),('S',1),('SDG',1),('T',1),('TDG',1),('CX',2),('CZ',2),('SWAP',2)])
def test_cpu_kernel_body_every_gate_every_basis(kernel_body,gate,arity):
    chain=OperatorChain(arity,((gate,*range(arity)),),tuple(range(arity)))
    for j in range(1<<arity):
        initial=tuple(ONE if i==j else ZERO for i in range(1<<arity));output=execute_cpu_kernel_body(kernel_body,chain,initial)
        assert output==fast_apply(chain,initial)[0]==reference_apply(chain,initial)

@pytest.mark.parametrize('seed',range(12))
def test_cpu_kernel_body_random_exact_chains(kernel_body,seed):
    rng=random.Random(seed);n=3;choices=[('H',1),('T',1),('TDG',1),('S',1),('SDG',1),('CX',2),('CZ',2),('SWAP',2)]
    gates=[]
    for _ in range(8):
        name,arity=rng.choice(choices);gates.append((name,*rng.sample(range(n),arity)))
    chain=OperatorChain(n,tuple(gates),(2,0,1));initial=initial_state(n)
    output=execute_cpu_kernel_body(kernel_body,chain,initial);assert output==fast_apply(chain,initial)[0]==reference_apply(chain,initial)

@pytest.mark.parametrize('gate',['H','T','TDG'])
def test_cpu_kernel_body_max_depth_phase_exact(kernel_body,gate):
    chain=OperatorChain(1,((gate,0),)*55,(0,));initial=(ZERO,ONE)
    assert execute_cpu_kernel_body(kernel_body,chain,initial)==fast_apply(chain,initial)[0]


def test_gpu_transport_rejects_non_dyadic_without_approximation():
    chain=OperatorChain(1,(),(0,));initial=((Fraction(3,5),Fraction(0),Fraction(0),Fraction(0)),(Fraction(4,5),Fraction(0),Fraction(0),Fraction(0)))
    with pytest.raises(BackendAbsent):pack_exact(chain,initial)
    initial=((Fraction(1,1<<61),Fraction(0),Fraction(0),Fraction(0)),ZERO)
    with pytest.raises(ValueError):pack_exact(chain,initial)


def test_cpu_kernel_overflow_flag_rejects_not_overflow_to_zero(kernel_body):
    src=(ctypes.c_long*8)(0,2**62,0,0,0,0,0,0);dst=(ctypes.c_long*8)();plan=(ctypes.c_int*3)(0,0,0);error=ctypes.c_int()
    kernel_body(src,dst,plan,0,2,ctypes.byref(error));assert error.value==1


def test_reference_fallback_receipt_survives_hardware_recovery():
    with OneIGPU(working_width=32,prime_rom_limit=1000)as gpu:
        r=gpu.m5_resident(model=elevate_pads(1)).ultra_contract('a'*40)
        # Exact GPU-domain rejection independent of hardware availability.
        state=[encode((Fraction(3,5),Fraction(0),Fraction(0),Fraction(0))),encode((Fraction(4,5),Fraction(0),Fraction(0),Fraction(0)))]
        receipt=r.execute(OperatorChain(1,(),(0,)),state,'GPU','CPU_REFERENCE')
        assert receipt['executed_backend']=='CPU_REFERENCE'and r.replay(receipt,device_contract('CPU_REFERENCE'))


def test_owner_close_invalidates_contract():
    gpu=OneIGPU(working_width=32,prime_rom_limit=1000);r=gpu.m5_resident(model=elevate_pads(1)).ultra_contract('a'*40);gpu.close()
    with pytest.raises(RuntimeError):r.execute(OperatorChain(1,(),(0,)))


def test_actual_gpu_parity_when_device_exists():
    try:executor=ExactOpenCLExecutor()
    except BackendAbsent as exc:pytest.skip('actual GPU evidence UNAVAILABLE: '+str(exc))
    try:
        chain=OperatorChain(2,(('H',0),('T',0),('CX',0,1)),(0,1));initial=initial_state(2)
        assert executor.execute(chain,initial)==fast_apply(chain,initial)[0]==reference_apply(chain,initial)
        assert executor.contract()['substrate']=='detected_gpu_integer_arithmetic'
    finally:executor.close()


def test_cpu_kernel_complete_ten_pad_full_mesh(kernel_body):
    from chronos_one_igpu.igpu.m5_ultra_contract import preparation
    c=preparation(elevate_pads(10,topology='full_mesh'),'exact_m5_cluster');assert len(c.gates)==55
    initial=initial_state(10);actual=execute_cpu_kernel_body(kernel_body,c,initial)
    assert actual==fast_apply(c,initial)[0]
    # Independent closed form for this graph state, no same-kernel verifier.
    for j,a in enumerate(actual):
        phase=(-1)**sum(bool(j&(1<<x))and bool(j&(1<<y))for x in range(10)for y in range(x+1,10))
        assert a==(Fraction(phase,32),Fraction(0),Fraction(0),Fraction(0))


def test_distinct_exact_gpu_integer_work_counts():
    from chronos_one_igpu.igpu.m5_exact_opencl import integer_kernel_counts
    c=OperatorChain(2,(('H',0),('T',0),('TDG',1),('S',1),('CX',0,1)),(0,1));counts=integer_kernel_counts(c)
    assert counts['kernel_dispatches']==5 and counts['coefficient_writes']==80
    assert counts['checked_add_calls']==32 and counts['checked_negation_calls']==28 and counts['checked_doubling_calls']==32
