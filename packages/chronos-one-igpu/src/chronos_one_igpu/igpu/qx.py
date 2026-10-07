"""Sealed computational QX command stream with actual evolution and readout."""
from dataclasses import dataclass
import hashlib,json
import numpy as np
from ..golden_quantum import MathematicalQuantumState,HamiltonianEngine,Operator

def encoded_matrix(values):
    a=np.asarray(values,dtype=np.complex128)
    if not np.isfinite(a).all():raise ValueError('nonfinite QX values')
    return {'real':a.real.tolist(),'imag':a.imag.tolist()}
def decoded_matrix(values):return np.array(values['real'])+1j*np.array(values['imag'])
@dataclass(frozen=True)
class QXBuffer:
    commands_json:str
    digest:str
    @classmethod
    def seal(cls,commands):
        text=json.dumps(list(commands),sort_keys=True,separators=(',',':'),allow_nan=False)
        if len(text)>4*1024*1024:raise ValueError('QX command quota')
        return cls(text,hashlib.sha256(text.encode()).hexdigest())
    def verify(self):
        if hashlib.sha256(self.commands_json.encode()).hexdigest()!=self.digest:raise ValueError('QX seal mismatch')
        return json.loads(self.commands_json)
class QXExecutor:
    def execute(self,buffer,seed=0):
        commands=buffer.verify();states={};hamiltonians={};readouts={};events=[];rng=np.random.default_rng(seed);descriptors={}
        for index,c in enumerate(commands):
            op=c['op'];name=c.get('name','state')
            if op=='allocate':
                if name in states:raise ValueError('duplicate QX allocation')
                amplitudes=decoded_matrix(c['amplitudes']);state=MathematicalQuantumState(amplitudes)
                if not np.isclose(np.vdot(amplitudes,amplitudes).real,1,atol=1e-10):raise ValueError('QX input norm must already be one')
                states[name]=state
            elif op=='bind_hamiltonian':
                if name not in states:raise ValueError('QX state not allocated')
                h=Operator(decoded_matrix(c['matrix'])).matrix
                if h.shape[0]!=len(states[name].amplitudes)or not np.allclose(h,h.conj().T,atol=1e-12,rtol=1e-12):raise ValueError('invalid QX Hamiltonian')
                hamiltonians[name]=h
            elif op=='evolve':states[name]=HamiltonianEngine().evolve(states[name],hamiltonians[name],c.get('time',1))
            elif op=='correct':
                u=Operator(decoded_matrix(c['matrix'])).matrix
                if not np.allclose(u.conj().T@u,np.eye(len(u)),atol=1e-12,rtol=1e-12):raise ValueError('QX correction must be unitary')
                states[name]=Operator(u).apply(states[name])
            elif op=='weak_measure':
                strength=c['strength']
                if not 0<=strength<=1 or len(states[name].amplitudes)!=2:raise ValueError('weak readout requires a bounded 1-qubit state')
                effects=[np.diag(np.sqrt([(1+strength)/2,(1-strength)/2])),np.diag(np.sqrt([(1-strength)/2,(1+strength)/2]))]
                vectors=[effect@states[name].amplitudes for effect in effects];probs=[float(np.vdot(v,v).real)for v in vectors]
                outcome=int(rng.choice(2,p=np.array(probs)/sum(probs)));states[name]=MathematicalQuantumState(vectors[outcome]);readouts[c.get('output','weak')]={'outcome':outcome,'probabilities':probs}
            elif op=='expectation':
                observable=Operator(decoded_matrix(c['matrix'])).matrix
                if observable.shape[0]!=len(states[name].amplitudes)or not np.allclose(observable,observable.conj().T,atol=1e-12,rtol=1e-12):raise ValueError('QX observable must be compatible Hermitian')
                readouts[c.get('output',name)]=float(np.vdot(states[name].amplitudes,observable@states[name].amplitudes).real)
            elif op=='descriptor_set':
                refs=c['states']
                if any(ref not in states for ref in refs):raise ValueError('descriptor refers to absent state')
                descriptors[c['descriptor']]=tuple(refs)
            elif op in('barrier','synchronize'):events.append({'command':index,'event':op})
            else:raise ValueError('unsupported QX operation')
        state_hashes={n:hashlib.sha256(s.amplitudes.tobytes()).hexdigest()for n,s in states.items()}
        return {'logical_device':'chronos_igpu','executor':'cpu_reference','precision':'complex128','command_digest':buffer.digest,
                'readouts':readouts,'events':events,'descriptor_sets':descriptors,'state_hashes':state_hashes,
                'norm_errors':{n:abs(float(np.vdot(s.amplitudes,s.amplitudes).real)-1)for n,s in states.items()}}
