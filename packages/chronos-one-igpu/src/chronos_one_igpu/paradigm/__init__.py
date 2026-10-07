"""Standalone paradigm spine from the user-supplied Chronus systems thesis."""
from enum import Enum
from dataclasses import dataclass,asdict
import math,json,hashlib,time
from ..lucas_engine import fibonacci_pair
THESIS='Chronus provides a versioned, fail-closed virtual accelerator ABI whose receipts bind workload, backend, digest, and trust class; algebraic schedules may reorder classical work but never substitute for SHA256d or pool acknowledgement.'
THESIS_ID=hashlib.sha256(THESIS.encode()).hexdigest()
class ScheduleName(str,Enum):
    SEQUENTIAL='sequential'
    GOLDEN_STRIDE='golden_stride'
    LUCAS='lucas_residue'
def golden_stride(size,rung=15):
    if type(size)is not int or size<1:raise ValueError('positive integer schedule size required')
    if type(rung)is not int or not 2<=rung<=110:raise ValueError('bounded schedule rung required')
    f,f1=fibonacci_pair(rung);stride=max(1,(size*f*f)//(f1*f1))
    while math.gcd(stride,size)!=1:stride+=1
    return stride

def nonce_walk(size,schedule=ScheduleName.GOLDEN_STRIDE,start=0,rung=15):
    if type(size)is not int or size<0 or type(start)is not int or start<0:raise ValueError('invalid nonce domain')
    schedule=ScheduleName(schedule)
    if schedule==ScheduleName.SEQUENTIAL:yield from range(start,start+size);return
    if not size:return
    if schedule==ScheduleName.GOLDEN_STRIDE:
        stride=golden_stride(size,rung)
        for k in range(size):yield start+(k*stride)%size
    else:
        if size>65536:raise ValueError('Lucas recurrence materialisation quota')
        seen=set();a,b=2%size,1%size
        for _ in range(2*size):
            if a not in seen:seen.add(a);yield start+a
            a,b=b,(a+b)%size
            if len(seen)==size:return
        for n in nonce_walk(size,ScheduleName.GOLDEN_STRIDE,start,rung):
            if n-start not in seen:seen.add(n-start);yield n

def assert_thesis_bounds():
    assert 'never substitute for SHA256d or pool acknowledgement'in THESIS
    return {'thesis_id':THESIS_ID,'theorem_proven':False,'logical_device':'chronos_igpu'}
def run_conformance():
    from .. import OneIGPU
    from ..igpu.virtual_abi import Workload,VirtualRuntime
    with OneIGPU(working_width=32,prime_rom_limit=1000)as gpu:
        w=Workload('spine-conformance','local','lucas',{'rungs':[0,1,15]},quota=3)
        receipt=VirtualRuntime(gpu).execute(w);VirtualRuntime.verify_receipt(receipt,w)
        assert receipt['output']['values']==[2,1,1364]
        return {'passed':True,'abi':receipt['schema'],'backend':receipt['backend'],'receipt_digest':receipt['receipt_digest']}
def run_honesty_chaos():
    from .. import OneIGPU
    from ..igpu.virtual_abi import Workload,VirtualRuntime
    with OneIGPU(working_width=32,prime_rom_limit=1000)as gpu:
        runtime=VirtualRuntime(gpu);w=Workload('chaos','local','lucas',{'rungs':[15]},quota=1);receipt=runtime.execute(w)
        cases={}
        altered=dict(receipt);altered['backend']='fictional-hardware-root'
        for name,action in [('tamper',lambda:runtime.verify_receipt(altered,w)),('quota',lambda:runtime.execute(Workload('quota','local','lucas',{'rungs':[1,2]},quota=1))),('liar_hardware_root',lambda:runtime.execute(Workload('liar','local','lucas',{'rungs':[15]},trust_class='hardware_root')))]:
            try:action();cases[name]=False
            except (ValueError,RuntimeError):cases[name]=True
        return {'passed':all(cases.values()),'cases':cases}
def run_bakeoff(header_prefix=None,target=0,size=128,runs=3):
    from ..golden_quantum import GoldenRatioMining,NonceLease
    if type(size)is not int or not 1<=size<=65536 or type(runs)is not int or not 1<=runs<=30:raise ValueError('bounded bakeoff required')
    header_prefix=bytes(76)if header_prefix is None else header_prefix
    rows=[]
    for name in ScheduleName:
        samples=[]
        for _ in range(runs):
            order=tuple(nonce_walk(size,name));result=GoldenRatioMining().scan(header_prefix,target,NonceLease(0,size),order,size)
            samples.append({'completed_hashes':result.sha256d_evaluations,'elapsed_seconds':result.elapsed_seconds,'hashrate':result.hashrate,'verified':result.verified})
        rows.append({'schedule':name.value,'samples':samples,'mean_hashrate':sum(s['hashrate']for s in samples)/runs})
    baseline=rows[0]['mean_hashrate']
    return {'passed':all(s['completed_hashes']<=size for row in rows for s in row['samples']),
            'rows':rows,'baseline':'sequential','negative_results':[row['schedule']for row in rows[1:]if row['mean_hashrate']<=baseline],
            'measurement':'executed_sha256d_only','represented_state_multiplier_used':False,'hardware_qualification':False}
@dataclass(frozen=True)
class TriadReport:
    lemma:dict
    systems:dict
    measurement:dict
    honesty:dict
    passed:bool
    def to_dict(self):return asdict(self)
def run_triad():
    assert_thesis_bounds();cases=[]
    for size in(1,2,3,17,64,127,256,600,1000):
        stride=golden_stride(size);values=list(nonce_walk(size));cases.append(math.gcd(stride,size)==1 and sorted(values)==list(range(size)))
    lemma={'passed':all(cases),'identity':'golden_stride_bijection','theorem_proven':False,'cases':len(cases)}
    systems=run_conformance();measurement=run_bakeoff();honesty=run_honesty_chaos()
    return TriadReport(lemma,systems,measurement,honesty,all(c['passed']for c in(lemma,systems,measurement,honesty)))
