"""Bounded M5 operator contract: depth/composition/evidence, never silicon claims.

Canonical amplitudes are four rational coefficients in Q(sqrt(2), i).
Production applies local exact gate operations; independent reference uses
symbolic basis-column contributions. Parity is canonical JSON byte equality.
"""
from dataclasses import dataclass
from fractions import Fraction as F
import hashlib
import itertools
import json
from pathlib import Path
import re
import sympy as sp
from ..adapters.base import BackendAbsent
from .resident import canonical
from .m5_quantum import topology, digest

PAD_MAX=10
# Existing maximum bounded preparation: 10 H + 45 CZ (ten-pad full mesh).
DEPTH_MAX=55
GATES={'H':1,'X':1,'Z':1,'S':1,'SDG':1,'T':1,'TDG':1,'CX':2,'CZ':2,'SWAP':2}
ZERO=(F(0),)*4
ONE=(F(1),F(0),F(0),F(0))
H=(F(0),F(1,2),F(0),F(0))
I=(F(0),F(0),F(1),F(0))
T=(F(0),F(1,2),F(0),F(1,2))


def add(a,b):return tuple(x+y for x,y in zip(a,b))
def neg(a):return tuple(-x for x in a)
def conjugate(a):return a[:2]+tuple(-x for x in a[2:])
def mul(a,b):
    out=[F(0)]*4
    for j in range(4):
        for k in range(4):
            r=(j%2)+(k%2);i=(j//2)+(k//2)
            out[(r%2)+2*(i%2)]+=a[j]*b[k]*(2 if r==2 else 1)*(-1 if i==2 else 1)
    return tuple(out)
def encode(a):return [[x.numerator,x.denominator]for x in a]
def decode(a):
    if not isinstance(a,list)or len(a)!=4:raise ValueError('canonical Q(sqrt2,i) amplitude required')
    out=[]
    for p in a:
        if not isinstance(p,list)or len(p)!=2 or any(type(x)is not int or x.bit_length()>4096 for x in p)or p[1]<=0:raise ValueError('bounded canonical rational pair required')
        x=F(*p)
        if [x.numerator,x.denominator]!=p:raise ValueError('noncanonical rational representation')
        out.append(x)
    return tuple(out)
def expression(a):return sum(sp.Rational(x.numerator,x.denominator)*b for x,b in zip(a,(1,sp.sqrt(2),sp.I,sp.I*sp.sqrt(2))))
def symbolic_coefficients(x):
    x=sp.expand(sp.simplify(x));real=sp.expand(sp.re(x));imag=sp.expand(sp.im(x));out=[]
    for part in(real,imag):
        radical=part.coeff(sp.sqrt(2));rational=sp.simplify(part-radical*sp.sqrt(2))
        if not rational.is_Rational or not radical.is_Rational:raise ValueError('reference left exact declared field')
        out.extend((F(int(rational.p),int(rational.q)),F(int(radical.p),int(radical.q))))
    return tuple(out)


@dataclass(frozen=True)
class OperatorChain:
    pads:int
    gates:tuple
    pad_map:tuple
    def __post_init__(self):
        if type(self.pads)is not int or not 1<=self.pads<=PAD_MAX:raise ValueError('pad bound')
        if not isinstance(self.gates,tuple)or len(self.gates)>DEPTH_MAX:raise ValueError('depth bound')
        if not isinstance(self.pad_map,tuple)or any(type(x)is not int for x in self.pad_map)or sorted(self.pad_map)!=list(range(self.pads)):raise ValueError('exact pad permutation required')
        for gate in self.gates:
            if not isinstance(gate,tuple)or not gate or gate[0]not in GATES or len(gate)!=GATES[gate[0]]+1 or any(type(x)is not int or not 0<=x<self.pads for x in gate[1:])or len(set(gate[1:]))!=len(gate[1:]):raise ValueError('exact bounded gate contract')
    def to_dict(self):return {'pads':self.pads,'gates':[list(g)for g in self.gates],'pad_map':list(self.pad_map),'depth_max':DEPTH_MAX,'pad_max':PAD_MAX}
    @classmethod
    def from_dict(cls,d):
        if not isinstance(d,dict)or set(d)!={'pads','gates','pad_map','depth_max','pad_max'}or d['depth_max']!=DEPTH_MAX or d['pad_max']!=PAD_MAX:raise ValueError('operator bounds/contract mismatch')
        if not isinstance(d['gates'],list)or not isinstance(d['pad_map'],list):raise ValueError('serialised exact chain required')
        return cls(d['pads'],tuple(tuple(g)for g in d['gates']),tuple(d['pad_map']))
    def adjoint(self):
        inv={'S':'SDG','SDG':'S','T':'TDG','TDG':'T'}
        return OperatorChain(self.pads,tuple((inv.get(g[0],g[0]),*g[1:])for g in reversed(self.gates)),self.pad_map)
    def inverse(self):return self.adjoint()
    def then(self,other):
        if self.pads!=other.pads or self.pad_map!=other.pad_map:raise ValueError('composition domain mismatch')
        return OperatorChain(self.pads,self.gates+other.gates,self.pad_map)


def preparation(model,algorithm):
    n,edges=topology(model)
    if algorithm=='exact_m5_ghz':gates=(('H',0),)+tuple(('CX',0,i)for i in range(1,n))
    elif algorithm=='exact_m5_cluster':gates=tuple(('H',i)for i in range(n))+tuple(('CZ',i,j)for i,j in edges)
    else:raise ValueError('no algorithm substitution')
    return OperatorChain(n,gates,tuple(range(n)))


def norm(state):
    total=ZERO
    for a in state:total=add(total,mul(conjugate(a),a))
    return total


def fast_apply(chain,initial):
    state=tuple(initial);dimension=1<<chain.pads
    if len(state)!=dimension or norm(state)!=ONE:raise ValueError('exact normalised input required')
    counts={'gate_applications':len(chain.gates),'amplitude_add_calls':0,'amplitude_multiply_calls':0,'amplitude_negations':0,'permutation_writes':0,'normalisation_checks':1+len(chain.gates),'norm_amplitude_products':dimension*(1+len(chain.gates)),'state_dimension':dimension,'depth':len(chain.gates),'pad_occupancy':chain.pads,'state_buffer_shape':[2,dimension,4],'coefficient_encoding':'unbounded_rational_with_input_bit_quota4096'}
    for gate in chain.gates:
        kind=gate[0];bits=[chain.pad_map[b]for b in gate[1:]];out=list(state)
        if kind=='H':
            bit=1<<bits[0]
            for j in range(dimension):
                if not j&bit:
                    k=j|bit;out[j]=mul(add(state[j],state[k]),H);out[k]=mul(add(state[j],neg(state[k])),H)
            counts['amplitude_add_calls']+=dimension;counts['amplitude_multiply_calls']+=dimension;counts['amplitude_negations']+=dimension//2
        elif kind in('S','SDG','T','TDG'):
            phase={'S':I,'SDG':conjugate(I),'T':T,'TDG':conjugate(T)}[kind]
            for j in range(dimension):
                if j&(1<<bits[0]):out[j]=mul(state[j],phase)
            counts['amplitude_multiply_calls']+=dimension//2
        elif kind in('Z','CZ'):
            for j in range(dimension):
                if all(j&(1<<b)for b in bits):out[j]=neg(state[j])
            counts['amplitude_negations']+=dimension//(1<<len(bits))
        else:
            for j in range(dimension):
                if kind=='X':k=j^(1<<bits[0])
                elif kind=='CX':k=j^(1<<bits[1])if j&(1<<bits[0])else j
                else:k=j^((1<<bits[0])|(1<<bits[1]))if bool(j&(1<<bits[0]))!=bool(j&(1<<bits[1]))else j
                out[k]=state[j]
            counts['permutation_writes']+=dimension
        state=tuple(out)
        if norm(state)!=ONE:raise ArithmeticError('operator normalisation violation')
    counts['field_rational_products']=16*(counts['amplitude_multiply_calls']+counts['norm_amplitude_products'])
    counts['stored_output_rational_pairs']=dimension*4
    counts['initial_canonical_bytes']=len(canonical([encode(a)for a in initial]))
    counts['result_canonical_bytes']=len(canonical([encode(a)for a in state]))
    counts['result_max_coefficient_bits']=max(max(x.numerator.bit_length(),x.denominator.bit_length())for a in state for x in a)
    counts['op_count']=sum(counts[k]for k in('amplitude_add_calls','amplitude_multiply_calls','amplitude_negations','permutation_writes','norm_amplitude_products'))
    return state,counts


def reference_apply(chain,initial,with_counts=False):
    """Independent symbolic matrix-column action, never using fast field gates."""
    state={j:expression(a)for j,a in enumerate(initial)if a!=ZERO}
    contributions=0
    for gate in chain.gates:
        next_state={};kind=gate[0];bits=[chain.pad_map[b]for b in gate[1:]]
        for j,a in state.items():
            if kind=='H':
                b=1<<bits[0];columns=((j&~b,1/sp.sqrt(2)),(j|b,(-1 if j&b else 1)/sp.sqrt(2)))
            elif kind in('S','SDG','T','TDG'):
                phase={'S':sp.I,'SDG':-sp.I,'T':(1+sp.I)/sp.sqrt(2),'TDG':(1-sp.I)/sp.sqrt(2)}[kind]
                columns=((j,phase if j&(1<<bits[0])else 1),)
            elif kind in('Z','CZ'):columns=((j,-1 if all(j&(1<<b)for b in bits)else 1),)
            else:
                if kind=='X':k=j^(1<<bits[0])
                elif kind=='CX':k=j^(1<<bits[1])if j&(1<<bits[0])else j
                else:k=j^((1<<bits[0])|(1<<bits[1]))if bool(j&(1<<bits[0]))!=bool(j&(1<<bits[1]))else j
                columns=((k,1),)
            contributions+=len(columns)
            for k,coefficient in columns:next_state[k]=next_state.get(k,0)+coefficient*a
        state={j:sp.simplify(a)for j,a in next_state.items()if a!=0}
    result=tuple(symbolic_coefficients(state.get(j,sp.Integer(0)))for j in range(1<<chain.pads))
    if sp.simplify(sum(sp.conjugate(expression(a))*expression(a)for a in result)-1)!=0:raise ArithmeticError('reference normalisation')
    return (result,{"basis_column_contributions":contributions,"output_coefficients_canonicalised":len(result)*4,"normalisation_amplitudes_checked":len(result)})if with_counts else result


def born_fast(state):return [encode(mul(conjugate(a),a))for a in state]

def born_reference(state):return [encode(symbolic_coefficients(sp.simplify(sp.conjugate(expression(a))*expression(a))))for a in state]


def initial_state(n,values=None):
    if values is None:return (ONE,)+(ZERO,)*((1<<n)-1)
    if not isinstance(values,list)or len(values)!=1<<n:raise ValueError('bounded exact input shape')
    state=tuple(decode(x)for x in values)
    if norm(state)!=ONE:raise ValueError('zero/non-unit norm input rejected')
    return state


def implementation_identity():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def device_contract(backend):
    if backend not in('CPU_REFERENCE','IGPU'):raise BackendAbsent('exact M5_ULTRA GPU executor unavailable; explicit reference fallback required')
    return {'backend':backend,'executor':'symbolic_basis_columns'if backend=='CPU_REFERENCE'else'chronos_resident_exact_field','substrate':'host_cpu_exact_math','physical_entanglement':False,'implementation_digest':implementation_identity(),'canonical_form':'q_sqrt2_i_four_reduced_rationals/1'}


class M5UltraContract:
    def __init__(self,gpu,model,rc_sha,gpu_selector=None):
        if not isinstance(rc_sha,str)or not re.fullmatch('[0-9a-f]{40}',rc_sha):raise ValueError('full sealed revision identity required')
        if getattr(gpu,"_m5_ultra_closed",False):raise RuntimeError("M5 contract owner closed")
        if gpu_selector is not None and(not isinstance(gpu_selector,str)or not gpu_selector):raise ValueError("explicit GPU selector")
        self.gpu_selector=gpu_selector
        topology(model);self.gpu=gpu;self.model=model;self.rc_sha=rc_sha;self.model_digest=digest(model.as_dict())
    def _gpu_binding(self):
        from .m5_exact_opencl import ExactOpenCLExecutor
        with self.gpu._hendrix_lock:
            if getattr(self.gpu,"_m5_ultra_closed",False):raise RuntimeError("M5 contract owner closed")
            existing=getattr(self.gpu,'_m5_exact_opencl',None)
            if existing is None:
                existing=ExactOpenCLExecutor(self.gpu_selector);self.gpu._m5_exact_opencl=existing
                self.gpu._m5_exact_selector=self.gpu_selector
            elif getattr(self.gpu,'_m5_exact_selector',None)!=self.gpu_selector:raise BackendAbsent('different exact GPU selector requires a new owner binding')
            existing.contract();return existing
    def device_contract(self,backend):
        return self._gpu_binding().contract()if backend=='GPU'else device_contract(backend)
    def execute(self,chain,initial=None,backend='IGPU',authorised_fallback=None):
        if not isinstance(chain,OperatorChain)or chain.pads!=self.model.n_pads:raise ValueError('bound operator domain')
        if authorised_fallback not in(None,'CPU_REFERENCE'):raise ValueError('named fallback contract')
        if getattr(self.gpu,'_m5_ultra_closed',False):raise RuntimeError('M5 contract owner closed')
        inputs=initial_state(chain.pads,initial)
        if len(canonical([encode(a)for a in inputs]))>512*1024:raise ValueError('exact initial transport admission quota')
        requested=backend;reason=None;accelerator_state=None
        try:
            if backend=='GPU':
                from .m5_exact_opencl import pack_exact
                pack_exact(chain,inputs)
                executor=self._gpu_binding();contract=executor.contract();accelerator_state=executor.execute(chain,inputs)
            else:contract=device_contract(backend)
        except BackendAbsent:
            if backend not in('GPU','IGPU')or authorised_fallback!='CPU_REFERENCE':raise
            backend='CPU_REFERENCE';contract=device_contract(backend);reason='exact_requested_executor_unavailable'
        if backend=='GPU'and accelerator_state is None:raise ArithmeticError('GPU executor returned no exact result')
        return self._verified_receipt(chain,inputs,backend,requested,authorised_fallback,reason,contract,accelerator_state)
    def _verified_receipt(self,chain,inputs,backend,requested,authorised_fallback,reason,contract,accelerator_state=None):
        # Pure exact reconstruction. No executor discovery/dispatch/lifecycle work.
        fast,counts=fast_apply(chain,inputs);reference,ref_counts=reference_apply(chain,inputs,with_counts=True)
        if canonical([encode(a)for a in fast])!=canonical([encode(a)for a in reference]):raise ArithmeticError('differential disagreement: no winner selected')
        if accelerator_state is not None and accelerator_state!=reference:raise ArithmeticError('exact GPU differential disagreement')
        state=accelerator_state if accelerator_state is not None else reference if backend=='CPU_REFERENCE'else fast
        output=[encode(a)for a in state];probabilities=born_fast(state)
        if canonical(probabilities)!=canonical(born_reference(reference)):raise ArithmeticError("independent exact Born disagreement")
        counts={**counts,"production_born_field_products":len(state),"independent_reference_counts":ref_counts,"count_scope":"named mathematical operations, not CPU instructions or elapsed rates"}
        receipt={'schema':'chronos.m5_ultra_contract/1','scope':'INCREMENTAL_EVIDENCE_ONLY','rc_sha':self.rc_sha,'algorithm':'exact_m5_operator_chain','requested_algorithm':'exact_m5_operator_chain','planned_algorithm':'exact_m5_operator_chain','executed_algorithm':'exact_m5_operator_chain','implementation_id':implementation_identity(),'topology_id':digest({'model_digest':self.model_digest,'topology':topology(self.model)}),'model_digest':self.model_digest,'chain':chain.to_dict(),'operator_chain_digest':digest(chain.to_dict()),'depth':len(chain.gates),'pad_map':list(chain.pad_map),'initial':[encode(a)for a in inputs],'initial_digest':digest([encode(a)for a in inputs]),'device_contract_identity':contract,'requested_backend':requested,'executed_backend':backend,'authorised_fallback':authorised_fallback,'fallback_used':requested!=backend,'fallback_reason':reason,'result':output,'born':probabilities,'result_digest':digest({'amplitudes':output,'born':probabilities}),'cost_model_counts':counts,'reference_verification':'INDEPENDENT_SYMBOLIC_CANONICAL_BYTE_EQUAL','normalisation':'1','sha256d_evaluations':0,'physical_claims':False,'certified':False}
        receipt['execution_work']={'executed_backend':backend,'host_differential_gate_counts':counts,'device_integer_kernel_counts':None}
        if backend=='GPU':
            from .m5_exact_opencl import integer_kernel_counts
            receipt['execution_work']['device_integer_kernel_counts']=integer_kernel_counts(chain)
        receipt['replay_binding']=digest(receipt)
        if len(canonical(receipt))>4*1024*1024:raise ValueError('exact receipt transport quota')
        return receipt
    def replay(self,receipt,expected_device_contract):
        try:return self._replay(receipt,expected_device_contract)
        except (KeyError,TypeError,IndexError,AttributeError)as exc:raise ValueError("malformed exact replay contract")from exc
    def _replay(self,receipt,expected_device_contract):
        if not isinstance(receipt,dict)or len(canonical(receipt))>4*1024*1024:raise ValueError('bounded replay receipt')
        if receipt.get('device_contract_identity')!=expected_device_contract:raise ValueError('device contract swap')
        chain=OperatorChain.from_dict(receipt['chain'])
        # Independent historical replay must not redispatch a physical GPU.
        # Source/kernel identity and caller-pinned device contract remain mandatory.
        backend=receipt['executed_backend'];requested=receipt['requested_backend'];fallback=receipt['authorised_fallback']
        if fallback not in(None,'CPU_REFERENCE')or backend not in('CPU_REFERENCE','IGPU','GPU')or requested not in('CPU_REFERENCE','IGPU','GPU'):raise ValueError('closed replay backend policy')
        if backend=='GPU':
            from .m5_exact_opencl import validate_device_contract,pack_exact
            validate_device_contract(expected_device_contract);pack_exact(chain,initial_state(chain.pads,receipt['initial']))
            if requested!='GPU'or receipt['fallback_used']or receipt['fallback_reason']is not None:raise ValueError('GPU replay fallback identity')
        elif expected_device_contract!=device_contract(backend):raise ValueError('host replay device contract mismatch')
        used=requested!=backend
        if used and(backend!='CPU_REFERENCE'or fallback!='CPU_REFERENCE'or requested not in('GPU','IGPU')):raise ValueError('unauthorised historical fallback')
        if chain.pads!=self.model.n_pads:raise ValueError('bound replay operator domain')
        inputs=initial_state(chain.pads,receipt['initial'])
        if len(canonical([encode(a)for a in inputs]))>512*1024:raise ValueError('exact replay input quota')
        expected=self._verified_receipt(chain,inputs,backend,requested,fallback,'exact_requested_executor_unavailable'if used else None,expected_device_contract)
        if canonical(receipt)!=canonical(expected):raise ValueError('strict replay/identity/result/cost rejection')
        return True
    def checkpoint(self,receipt):
        self.replay(receipt,receipt['device_contract_identity'])
        if self.gpu.db is None:raise RuntimeError('durable custody requires configured PRIME-DB')
        return self.gpu.db.put(receipt,1,family='m5_ultra_contract:'+self.rc_sha).object_id
    def restore(self,object_id,expected_device_contract):
        if self.gpu.db is None:raise RuntimeError('durable custody requires configured PRIME-DB')
        receipt=self.gpu.db.get(object_id).payload;self.replay(receipt,expected_device_contract);return receipt


def audit_operator_laws(chain):
    """Exhaustive finite basis proof of U†U=I (hence all basis inner products)."""
    dimension=1<<chain.pads
    if chain.pads>3:raise ValueError('exhaustive symbolic proof admission bound; gatewise exact identities apply above three pads')
    columns=[]
    for j in range(dimension):
        basis=tuple(ONE if i==j else ZERO for i in range(dimension));fast,_=fast_apply(chain,basis);ref=reference_apply(chain,basis)
        if fast!=ref:raise ArithmeticError('basis differential mismatch')
        restored,_=fast_apply(chain.adjoint(),fast)
        if restored!=basis:raise ArithmeticError('adjoint basis identity')
        columns.append([expression(a)for a in fast])
    matrix=sp.Matrix.hstack(*(sp.Matrix(x)for x in columns))
    if any(sp.simplify(v)!=0 for v in matrix.H*matrix-sp.eye(dimension)):raise ArithmeticError('all basis pair unitarity')
    return {'basis_pairs_checked':dimension**2,'normalisation_exact':True,'unitarity_exact':True,'proof_digest':digest({'chain':chain.to_dict(),'matrix':[[str(x)for x in row]for row in matrix.tolist()]})}


def symbolic_gate_laws():
    """Local exact gate theorem; tensor embedding preserves unitarity for all n."""
    root=sp.sqrt(2)
    matrices={'H':sp.Matrix([[1,1],[1,-1]])/root,'X':sp.Matrix([[0,1],[1,0]]),'Z':sp.diag(1,-1),'S':sp.diag(1,sp.I),'SDG':sp.diag(1,-sp.I),'T':sp.diag(1,(1+sp.I)/root),'TDG':sp.diag(1,(1-sp.I)/root),'CX':sp.Matrix([[1,0,0,0],[0,0,0,1],[0,0,1,0],[0,1,0,0]]),'CZ':sp.diag(1,1,1,-1),'SWAP':sp.Matrix([[1,0,0,0],[0,0,1,0],[0,1,0,0],[0,0,0,1]])}
    for name,m in matrices.items():
        if any(sp.simplify(x)!=0 for x in m.H*m-sp.eye(m.rows)):raise ArithmeticError('gate theorem '+name)
    u=sp.MatrixSymbol('U',2,2);v=sp.MatrixSymbol('V',2,2)
    if sp.Adjoint(u*v).doit()!=sp.Adjoint(v)*sp.Adjoint(u):raise ArithmeticError('symbolic composition-adjoint law')
    return {'gates':list(matrices),'exact_unitarity':True,'tensor_embedding_preserves_inner_product':True,'composition_adjoint_rule':'(UV).H=V.H*U.H','proof_digest':digest({k:[[str(v)for v in row]for row in m.tolist()]for k,m in matrices.items()})}
