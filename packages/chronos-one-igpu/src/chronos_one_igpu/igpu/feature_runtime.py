"""Generic executable feature plane over ONE iGPU; no vendor or mining authority.

Exact neural/tensor, compact Clifford registers, supplied Hamiltonian evolution,
real shared memory and bounded local-pad transport are independent capabilities.
They never silently substitute for one another or claim physical M5 hardware.
"""
from collections import OrderedDict
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import threading
import time
import sympy as sp
from ..adapters.base import BackendAbsent
from .feature_profile import FeatureProfile
from .unified_fabric import UnifiedArena, LocalPadTransport
from . import exact_neural as neural
from . import exact_stabilizer as stabilizer
from .exact_quantum import decode_expression, encode_expression, scalar
from .resident import canonical


@dataclass(frozen=True)
class FeatureConfig:
    memory_bytes:int=16*1024*1024
    memory_blocks:int=128
    cache_bytes:int=2*1024*1024
    cache_entries:int=8
    max_scalar_ops:int=1000000
    max_active:int=4
    max_inflight:int=4
    transport_records:int=128

    def validate(self):
        bounds={'memory_bytes':(1024,1024**3),'memory_blocks':(1,4096),'cache_bytes':(1024,16*1024*1024),
                'cache_entries':(1,128),'max_scalar_ops':(1,10000000),'max_active':(1,16),
                'max_inflight':(1,32),'transport_records':(1,4096)}
        for key,(lo,hi)in bounds.items():
            if type(getattr(self,key))is not int or not lo<=getattr(self,key)<=hi:raise ValueError('feature quota: '+key)
        return True


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def implementation():
    return {name:hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
            for name,module in [('feature_runtime',__import__(__name__,fromlist=['x'])),('exact_neural',neural),('exact_stabilizer',stabilizer)]}


def decode(v):
    if type(v)is int:return scalar(v)
    if isinstance(v,dict)and v.get('encoding')=='q_phi_v1':return scalar(neural.value(v))
    if isinstance(v,dict):return decode_expression(v)
    raise ValueError('strict exact quantum input required')


def exact_matrix(rows):
    if not isinstance(rows,list)or not 1<=len(rows)<=128 or any(not isinstance(row,list)or len(row)!=len(rows)for row in rows):raise ValueError('bounded exact square operator required')
    result=sp.ImmutableMatrix([[decode(v)for v in row]for row in rows])
    if any(sp.simplify(v)!=0 for v in result-result.H):raise ValueError('exact Hermitian operator required')
    return result


def hamiltonian(task):
    if task['kind']=='unitary':return [[decode(x)for x in row]for row in task['hamiltonian']]
    terms=task['hamiltonian_terms']
    if not isinstance(terms,list)or not 1<=len(terms)<=64:raise ValueError('bounded exact Hamiltonian sum required')
    matrices=[exact_matrix(rows)for rows in terms]
    if any(m.shape!=matrices[0].shape for m in matrices):raise ValueError('Hamiltonian term dimensions')
    total=sp.zeros(matrices[0].rows)
    for matrix in matrices:total+=matrix
    return total.tolist()


def operator_contract(task):
    if task['kind']=='projector':
        p=exact_matrix(task['projector']);h=exact_matrix(task['hamiltonian'])
        if p.shape!=h.shape or any(sp.simplify(v)!=0 for v in p*p-p):raise ValueError('exact orthogonal projector required')
        residual=p*h-h*p if task['condition']=='commutes'else p*h*p
    else:
        left=exact_matrix(task['left_operator']);right=exact_matrix(task['right_operator'])
        if left.shape!=right.shape:raise ValueError('commutator dimensions')
        residual=left*right-right*left
    if any(sp.simplify(v)!=0 for v in residual):raise ValueError('requested exact operator condition does not hold')
    return {'verified':True,'residual':[[encode_expression(v)for v in row]for row in residual.tolist()]}, {'matrix_dimension':residual.rows,'operator_products':2 if task['kind']=='commutator'or task['condition']=='commutes'else 2}


class GenericFeatureRuntime:
    def __init__(self,gpu,profile,config=None):
        if not isinstance(profile,FeatureProfile):raise TypeError('generic FeatureProfile required')
        self.gpu=gpu;self.profile=profile;self.config=config or FeatureConfig();self.config.validate()
        self.arena=UnifiedArena(self.config.memory_bytes,self.config.memory_blocks)
        self._transport=None;self._resources_closed=False
        self.cache=OrderedDict();self.cache_bytes=0;self.active=0;self.closed=False;self.lock=threading.RLock();self.idle=threading.Condition(self.lock)
        self.cache_hits=0;self.cache_misses=0

    @property
    def transport(self):
        with self.lock:
            if self.closed:raise RuntimeError('feature runtime closed')
            if self._transport is None:
                self._transport=LocalPadTransport(self.profile,self.arena,self.config.max_inflight,self.config.transport_records)
            return self._transport

    def manifest(self):
        with self.lock:
            return {'schema':'chronos.generic_features/1','profile':self.profile.to_dict(),'profile_digest':self.profile.digest,
                    'vendor_dependency':None,'executor':'host_exact','physical_hardware_qualification':None,
                    'memory':self.arena.inventory(),'prepared_cache':{'entries':len(self.cache),'encoded_program_bytes':self.cache_bytes,'hits':self.cache_hits,'misses':self.cache_misses},
                    'transport':'host_shared_memory_fifo','active_transport_workers':0 if self._transport is None else len(self._transport.threads),'mining_authority':'PYTHIA','executor_authority':'CHRONUS',
                    'operations':['exact_qphi_matmul','exact_qphi_add','exact_qphi_hadamard','exact_qphi_neural',
                                  'exact_stabilizer_ghz','exact_stabilizer_cluster','exact_hamiltonian_evolution','exact_hamiltonian_sum_evolution','exact_projector_commutation','exact_projector_annihilation','exact_operator_commutation'],
                    'unavailable_physical_features':['Apple ANE dispatch','UltraFusion hardware','hardware RDMA','photonic compute','HBM4 silicon','physical topological QEC']}

    def _network(self,layers):
        # Admit and canonicalise the weights before the content-addressed cache.
        encoded=canonical(layers)
        if len(encoded)>self.config.cache_bytes:raise MemoryError('prepared network cache admission quota')
        key=hashlib.sha256(encoded).hexdigest()
        with self.lock:
            if key in self.cache:
                self.cache_hits+=1;self.cache.move_to_end(key);return self.cache[key][0],True
            network=neural.PreparedNetwork(layers)
            while self.cache and(self.cache_bytes+len(encoded)>self.config.cache_bytes or len(self.cache)>=self.config.cache_entries):
                _,(_,size)=self.cache.popitem(last=False);self.cache_bytes-=size
            self.cache[key]=(network,len(encoded));self.cache_bytes+=len(encoded);self.cache_misses+=1
            return network,False

    def _admit(self,task):
        if not isinstance(task,dict)or len(canonical(task))>4*1024*1024:raise ValueError('bounded exact feature task required')
        kind=task.get('kind')
        required={'tensor':{'kind','operation','left','right'},'neural':{'kind','layers','input'},
                  'stabilizer':{'kind','algorithm','layout','assignments'},'unitary':{'kind','amplitudes','hamiltonian','time'},
                  'unitary_sum':{'kind','amplitudes','hamiltonian_terms','time'},'projector':{'kind','projector','hamiltonian','condition'},
                  'commutator':{'kind','left_operator','right_operator'}}
        if kind not in required or set(task)-{'require_host_gpu'}!=required[kind]:raise ValueError('explicit sealed feature task fields required')
        if type(task.get('require_host_gpu',False))is not bool:raise ValueError('explicit hardware policy required')
        if task.get('require_host_gpu'):raise BackendAbsent('requested exact feature has no qualified physical executor')
        if kind=='tensor':
            if task['operation']not in('matmul','add','hadamard'):raise ValueError('requested exact tensor operation unavailable')
            algorithm='exact_qphi_'+task['operation']
            a=neural.matrix(task['left']);b=neural.matrix(task['right'])
            cost=len(a)*len(a[0])*len(b[0])if task['operation']=='matmul'else len(a)*len(a[0])
            if cost>self.config.max_scalar_ops:raise ValueError('exact tensor work quota')
        elif kind=='neural':
            algorithm='exact_qphi_neural';x=neural.matrix(task['input'])
            layers=task['layers']
            if not isinstance(layers,list)or not 1<=len(layers)<=16:raise ValueError('bounded network layers')
            width=len(x[0]);cost=0
            for layer in layers:
                if not isinstance(layer,dict)or set(layer)!={'weights','bias','activation'} or layer['activation']not in('identity','relu'):raise ValueError('sealed network layer contract')
                w=layer['weights'];bias=layer['bias']
                if not isinstance(w,list)or not 1<=len(w)<=128 or not isinstance(w[0],list)or not 1<=len(w[0])<=128 or any(not isinstance(row,list)or len(row)!=len(w[0])for row in w)or len(w)!=width or not isinstance(bias,list)or len(bias)!=len(w[0]):raise ValueError('network dimensions')
                cost+=len(x)*width*len(bias);width=len(bias)
            if cost>self.config.max_scalar_ops:raise ValueError('complete network work quota')
        elif kind=='stabilizer':
            algorithm=task['algorithm']
            if algorithm not in('exact_stabilizer_ghz','exact_stabilizer_cluster'):raise ValueError('no Clifford substitution for another requested quantum algorithm')
            n,edges,_=self.profile.register_layout(task['layout'])
            cost=n*(n if algorithm=='exact_stabilizer_ghz'else n+3*len(edges))
            if cost>self.config.max_scalar_ops:raise ValueError('register gate-update work quota')
            pairs=task['assignments']
            if not isinstance(pairs,list)or any(not isinstance(p,list)or len(p)!=2 or type(p[0])is not int or not 0<=p[0]<n or type(p[1])is not int or p[1]not in(0,1)for p in pairs)or len({p[0]for p in pairs})!=len(pairs):raise ValueError('exact unique basis assignments required')
        elif kind in('projector','commutator'):
            if kind=='projector':
                if task['condition']not in('commutes','annihilates'):raise ValueError('distinct exact projector contract required')
                algorithm='exact_projector_commutation'if task['condition']=='commutes'else'exact_projector_annihilation'
                n=len(task['projector'])
            else:algorithm='exact_operator_commutation';n=len(task['left_operator'])
            if n*n*n>self.config.max_scalar_ops:raise ValueError('operator-product work quota')
        else:
            algorithm='exact_hamiltonian_evolution'if kind=='unitary'else'exact_hamiltonian_sum_evolution';n=len(task['amplitudes'])
            terms=1 if kind=='unitary'else len(task['hamiltonian_terms'])
            if n*n*terms>self.config.max_scalar_ops:raise ValueError('exact Hamiltonian work quota')
            [decode(x)for x in task['amplitudes']];hamiltonian(task);decode(task['time'])
        return algorithm

    def execute(self,task):
        task=json.loads(canonical(task));algorithm=self._admit(task)
        with self.idle:
            if self.closed:raise RuntimeError('feature runtime closed')
            if self.active>=self.config.max_active:raise RuntimeError('feature admission backpressure')
            self.active+=1
        started=time.perf_counter();cache_hit=False
        try:
            kind=task['kind']
            if kind=='tensor':output,work=neural.tensor(task['operation'],task['left'],task['right'],self.config.max_scalar_ops)
            elif kind=='neural':
                network,cache_hit=self._network(task['layers']);result,work=network.execute(task['input'],self.config.max_scalar_ops)
                output=neural.encode(result);network.verify(task['input'],output)
            elif kind=='stabilizer':
                prepared=stabilizer.prepare(self.profile,algorithm,task['layout'])
                state=stabilizer.StabilizerState.from_dict(prepared['state']);probability=state.born(dict(task['assignments']))
                output={'state_receipt':prepared,'born_probability':[probability.numerator,probability.denominator]}
                work={**prepared['iterations_work_performed'],'born_constraints_queried':len(task['assignments'])}
            elif kind in('projector','commutator'):output,work=operator_contract(task)
            else:
                state=self.gpu.evolve([decode(x)for x in task['amplitudes']],hamiltonian(task),decode(task['time']))
                output={'amplitudes':[encode_expression(x)for x in state.amplitudes],'execution_receipt':state.evidence}
                work=dict(state.evidence['iterations_work_performed'])
                if kind=='unitary_sum':work['hamiltonian_terms_added']=len(task['hamiltonian_terms'])
            receipt={'schema':'chronos.generic_feature_execution/1','profile':self.profile.to_dict(),'profile_digest':self.profile.digest,
                     'task':task,'plan_digest':digest(task),'requested_algorithm':algorithm,'planned_algorithm':algorithm,'executed_algorithm':algorithm,
                     'implementation_module':__name__,'implementation_digests':implementation(),'execution_mode':'exact_host_execution',
                     'substrate':{'kind':'cpu','physical_quantum_execution':False},'output':output,'output_digest':digest(output),
                     'iterations_work_performed':work,'prepared_program_cache_hit':cache_hit,'elapsed_seconds':time.perf_counter()-started,
                     'sha256d_evaluations':0,'fallback_used':False,'fallback_reason':None}
            receipt['receipt_digest']=digest(receipt);self.verify(receipt)
            return receipt
        finally:
            with self.idle:self.active-=1;self.idle.notify_all()

    def verify(self,receipt):
        if not isinstance(receipt,dict):raise ValueError('feature receipt required')
        task=receipt.get('task');algorithm=self._admit(task)
        identity={'schema':'chronos.generic_feature_execution/1','profile':self.profile.to_dict(),'profile_digest':self.profile.digest,
                  'plan_digest':digest(task),'requested_algorithm':algorithm,'planned_algorithm':algorithm,'executed_algorithm':algorithm,
                  'implementation_module':__name__,'implementation_digests':implementation(),'execution_mode':'exact_host_execution',
                  'substrate':{'kind':'cpu','physical_quantum_execution':False},'sha256d_evaluations':0,'fallback_used':False,'fallback_reason':None}
        if set(receipt)!=set(identity)|{'task','output','output_digest','iterations_work_performed','prepared_program_cache_hit','elapsed_seconds','receipt_digest'}:raise ValueError('feature receipt contract fields')
        body=dict(receipt);seal=body.pop('receipt_digest')
        if seal!=digest(body)or any(receipt[k]!=v for k,v in identity.items())or receipt['output_digest']!=digest(receipt['output']):raise ValueError('feature algorithm/implementation/custody mismatch')
        if type(receipt['prepared_program_cache_hit'])is not bool or type(receipt['elapsed_seconds'])not in(int,float)or receipt['elapsed_seconds']<0:raise ValueError('feature execution metadata mismatch')
        kind=task['kind']
        if kind=='tensor':
            output,work=neural.tensor(task['operation'],task['left'],task['right'],self.config.max_scalar_ops)
            if receipt['output']!=output:raise ValueError('independent tensor replay mismatch')
        elif kind=='neural':
            network=neural.PreparedNetwork(task['layers']);network.verify(task['input'],receipt['output']);_,work=network.execute(task['input'],self.config.max_scalar_ops)
        elif kind=='stabilizer':
            out=receipt['output'];stabilizer.verify_receipt(out['state_receipt'],self.profile,algorithm,task['layout'])
            state=stabilizer.StabilizerState.from_dict(out['state_receipt']['state']);p=state.born(dict(task['assignments']))
            if out['born_probability']!=[p.numerator,p.denominator]:raise ValueError('independent Born probability mismatch')
            work={**out['state_receipt']['iterations_work_performed'],'born_constraints_queried':len(task['assignments'])}
        elif kind in('projector','commutator'):
            expected,work=operator_contract(task)
            if receipt['output']!=expected:raise ValueError('independent exact operator contract replay mismatch')
        else:
            from .exact_quantum import exact_hamiltonian_evolution
            state=exact_hamiltonian_evolution([decode(x)for x in task['amplitudes']],hamiltonian(task),decode(task['time']),legacy_encoding=True)
            expected={'amplitudes':[encode_expression(x)for x in state.amplitudes],'execution_receipt':state.evidence}
            if receipt['output']!=expected:raise ValueError('independent exact unitary replay mismatch')
            work=dict(state.evidence['iterations_work_performed'])
            if kind=='unitary_sum':work['hamiltonian_terms_added']=len(task['hamiltonian_terms'])
        if receipt['iterations_work_performed']!=work:raise ValueError('feature work counter mismatch')
        if kind!='neural'and receipt['prepared_program_cache_hit']:raise ValueError('unexecuted cache claim')
        return True

    def checkpoint(self,receipt):
        self.verify(receipt)
        if self.gpu.db is None:raise RuntimeError('durable feature custody requires configured PRIME-DB')
        return self.gpu.db.put(receipt,1,family='generic_feature_receipt').object_id

    def restore(self,object_id):
        if self.gpu.db is None:raise RuntimeError('durable feature custody requires configured PRIME-DB')
        receipt=self.gpu.db.get(object_id).payload;self.verify(receipt);return receipt

    def close(self):
        with self.idle:
            if self.closed and self._resources_closed:return
            self.closed=True
            while self.active:self.idle.wait()
        if self._transport is not None:self._transport.close()
        self.arena.close();self._resources_closed=True
        with self.lock:self.cache.clear();self.cache_bytes=0

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
