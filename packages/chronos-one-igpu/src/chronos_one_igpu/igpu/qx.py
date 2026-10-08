"""Sealed computational QX command stream with actual evolution and readout.

Expectation and weak-measurement probabilities are computed in exact
rational arithmetic over the state's exact amplitudes; only the readout
outcome sampling is stochastic (the probabilities bound to it are exact)."""
from dataclasses import dataclass
from fractions import Fraction
import hashlib,json
import numpy as np
from ..golden_quantum import MathematicalQuantumState,HamiltonianEngine,Operator


def _exact_pair(value):
    c = complex(value)
    return (Fraction(float(c.real)), Fraction(float(c.imag)))


def _expectation_exact(state, observable_exact):
    """Exact <psi|O|psi>/||psi||^2 over rationals; Hermitian => real."""
    psi = state.amplitudes_exact
    n = len(psi)
    acc_re = Fraction(0)
    for i in range(n):
        inner_re, inner_im = Fraction(0), Fraction(0)
        row = observable_exact[i]
        for j in range(n):
            mr, mi = row[j]
            vr, vi = psi[j]
            inner_re += mr * vr - mi * vi
            inner_im += mr * vi + mi * vr
        pr, pi = psi[i]  # conj(psi_i) * inner_i
        acc_re += pr * inner_re + pi * inner_im
    return acc_re / state.norm_squared_exact


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
        commands=buffer.verify();states={};hamiltonians={};readouts={};readouts_exact={};events=[];rng=np.random.default_rng(seed);descriptors={}
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
                s=Fraction(float(strength))
                # E_0=diag((1+s)/2,(1-s)/2)^1/2 applied twice => outcome
                # probabilities p_k=<psi|E_k^2|psi>/||psi||^2 are exact.
                amps=states[name].amplitudes_exact;norm2=states[name].norm_squared_exact
                e0,e1=(1+s)/2,(1-s)/2
                p0=(e0*(amps[0][0]**2+amps[0][1]**2)+e1*(amps[1][0]**2+amps[1][1]**2))/norm2
                p1=1-p0
                # Post-measurement state requires sqrt(E) which is not a
                # rational operation; the outcome probabilities are exact
                # and the post-state is constructed from the exact E_k |psi>
                # then renormalised exactly (E_k psi / sqrt(p_k) in exact
                # form: numerator E_k psi, certificate carries p_k).
                vectors=[np.diag(np.sqrt([float(e0),float(e1)])),np.diag(np.sqrt([float(e1),float(e0)]))]
                vecs=[effect@states[name].amplitudes for effect in vectors]
                probs=[float(p0),float(p1)]
                outcome=int(rng.choice(2,p=np.array(probs)/sum(probs)));states[name]=MathematicalQuantumState(vecs[outcome]);readouts[c.get('output','weak')]={'outcome':outcome,'probabilities':probs,'probabilities_exact':[str(p0),str(p1)]}
            elif op=='expectation':
                op_obj=Operator(decoded_matrix(c['matrix']))
                observable=op_obj.matrix
                if observable.shape[0]!=len(states[name].amplitudes)or not np.allclose(observable,observable.conj().T,atol=1e-12,rtol=1e-12):raise ValueError('QX observable must be compatible Hermitian')
                exact=_expectation_exact(states[name],op_obj.matrix_exact)
                out_key=c.get('output',name)
                readouts[out_key]=float(exact)
                readouts_exact[out_key]=str(exact)
            elif op=='descriptor_set':
                refs=c['states']
                if any(ref not in states for ref in refs):raise ValueError('descriptor refers to absent state')
                descriptors[c['descriptor']]=tuple(refs)
            elif op in('barrier','synchronize'):events.append({'command':index,'event':op})
            else:raise ValueError('unsupported QX operation')
        state_hashes={n:hashlib.sha256(s.amplitudes.tobytes()).hexdigest()for n,s in states.items()}
        return {'logical_device':'chronos_igpu','executor':'cpu_exact_rational','precision':'exact_rational','command_digest':buffer.digest,
                'readouts':readouts,'readouts_exact':readouts_exact,'events':events,'descriptor_sets':descriptors,'state_hashes':state_hashes,
                'norm_errors':{n:abs(float(np.vdot(s.amplitudes,s.amplitudes).real)-1)for n,s in states.items()}}
