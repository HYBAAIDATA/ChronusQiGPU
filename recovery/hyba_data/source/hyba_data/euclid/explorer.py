"""EUCLID internal mathematical discovery and frontier exploration.

This is an internal capability of EUCLID, not a separate product or instrument.
It evaluates candidate unknown structures without treating numerical thresholds as proofs. Quantum results are simulated diagnostics, complexity conclusions are
finite-instance evidence, and information integration is not labelled
consciousness or strong emergence.
"""
from __future__ import annotations
import hashlib,json,math,random,zlib
from dataclasses import dataclass
from typing import Any,Mapping,Sequence
import numpy as np
SCHEMA="EUCLID_MATHEMATICAL_FRONTIER_EXPLORER_V1"

@dataclass(frozen=True)
class MathematicalFrontier:
 name:str;research_question:str;evidence_limit:str;priority:int
@dataclass(frozen=True)
class QuantumPhaseReport:
 parameters:tuple[float,...];entanglement_entropies:tuple[float,...];adjacent_fidelities:tuple[float,...];entropy_gradients:tuple[float,...];candidate_indices:tuple[int,...];candidate_parameters:tuple[float,...]
 claim_boundary:str="Finite simulated-state indicators; not proof of a thermodynamic quantum phase transition."
@dataclass(frozen=True)
class ComplexityEvidence:
 sizes:tuple[float,...];solve_costs:tuple[float,...];verification_costs:tuple[float,...];polynomial_exponent:float;exponential_rate:float;polynomial_rmse:float;exponential_rmse:float;preferred_empirical_model:str;verification_asymmetry:float
 claim_boundary:str="Finite-instance scaling cannot establish P != NP, NP != coNP, BQP != P, or any class separation."
@dataclass(frozen=True)
class DiscoveryValidation:
 observed_effect:float;permutation_p_value:float;reproducibility_score:float;sign_consistency:float;finite:bool;passed_pre_registered_thresholds:bool;protocol_hash:str
 claim_boundary:str="Statistical validation is not formal proof or independent replication."

class TheoreticalSpaceExplorer:
 def __init__(self,seed:int=20260718):
  self.seed=int(seed);self.frontiers={
   "algorithmic_information":MathematicalFrontier("Algorithmic information","Which computable bounds are informative?","Kolmogorov complexity is uncomputable",10),
   "quantum_information":MathematicalFrontier("Quantum information","Which simulated indicators reproduce?","Simulation is not physical quantum evidence",9),
   "complexity_scaling":MathematicalFrontier("Complexity scaling","Which finite-size model fits best?","Finite scaling cannot separate classes",9),
   "emergence":MathematicalFrontier("Emergence","Does integration beat matched ablations?","Dependence alone is not strong emergence or consciousness",8)}
 @staticmethod
 def _vector(values:Sequence[float],name:str)->np.ndarray:
  a=np.asarray(values,float).reshape(-1)
  if not len(a) or not np.all(np.isfinite(a)):raise ValueError(f"{name} must be non-empty and finite")
  return a
 @staticmethod
 def _density(rho:np.ndarray)->np.ndarray:
  a=np.asarray(rho,complex)
  if a.ndim!=2 or a.shape[0]!=a.shape[1] or not a.size:raise ValueError("density matrix must be non-empty and square")
  if not np.all(np.isfinite(a)) or not np.allclose(a,a.conj().T,atol=1e-10):raise ValueError("density matrix must be finite Hermitian")
  tr=np.trace(a)
  if abs(tr.imag)>1e-10 or tr.real<=0:raise ValueError("density matrix must have positive real trace")
  a=a/tr.real;eig=np.linalg.eigvalsh(a)
  if eig.min() < -1e-9:raise ValueError("density matrix must be positive semidefinite")
  return a
 @staticmethod
 def mutual_information(x:Sequence[float],y:Sequence[float],bins:int=20)->float:
  a=TheoreticalSpaceExplorer._vector(x,"x");b=TheoreticalSpaceExplorer._vector(y,"y")
  if len(a)!=len(b) or bins<1:raise ValueError("equal sample counts and positive bins required")
  xb=max(1,min(int(bins),len(np.unique(a))));yb=max(1,min(int(bins),len(np.unique(b))))
  joint=np.histogram2d(a,b,bins=(xb,yb))[0];total=joint.sum()
  if total<=0:return 0.0
  p=joint/total;px=p.sum(1);py=p.sum(0);expected=px[:,None]*py[None,:];mask=p>0
  value=float(np.sum(p[mask]*np.log2(p[mask]/expected[mask])))
  return max(0.0,value)
 @staticmethod
 def von_neumann_entropy(rho:np.ndarray)->float:
  eig=np.clip(np.linalg.eigvalsh(TheoreticalSpaceExplorer._density(rho)),0,1);nz=eig[eig>1e-15]
  return float(-np.sum(nz*np.log2(nz)))
 @staticmethod
 def partial_trace(rho_ab:np.ndarray,dims:tuple[int,int],keep:str)->np.ndarray:
  rho=TheoreticalSpaceExplorer._density(rho_ab);da,db=map(int,dims)
  if da<=0 or db<=0 or da*db!=rho.shape[0] or keep not in {"A","B"}:raise ValueError("invalid subsystem dimensions or keep selector")
  tensor=rho.reshape(da,db,da,db)
  return np.trace(tensor,axis1=1,axis2=3) if keep=="A" else np.trace(tensor,axis1=0,axis2=2)
 @classmethod
 def quantum_mutual_information(cls,rho_ab:np.ndarray,dims:tuple[int,int])->float:
  rho=cls._density(rho_ab);value=cls.von_neumann_entropy(cls.partial_trace(rho,dims,"A"))+cls.von_neumann_entropy(cls.partial_trace(rho,dims,"B"))-cls.von_neumann_entropy(rho)
  return max(0.0,float(value))
 @classmethod
 def pure_state_entanglement_entropy(cls,state:np.ndarray,dims:tuple[int,int])->float:
  psi=np.asarray(state,complex).reshape(-1);da,db=map(int,dims)
  if da*db!=len(psi) or not np.all(np.isfinite(psi)) or np.linalg.norm(psi)<=0:raise ValueError("invalid bipartite state")
  psi=psi/np.linalg.norm(psi);return cls.von_neumann_entropy(psi.reshape(da,db)@psi.reshape(da,db).conj().T)
 @staticmethod
 def _fidelity(rho:np.ndarray,sigma:np.ndarray)->float:
  r=TheoreticalSpaceExplorer._density(rho);s=TheoreticalSpaceExplorer._density(sigma)
  if r.shape!=s.shape:raise ValueError("state dimensions differ")
  vals,vecs=np.linalg.eigh(r);root=(vecs*np.sqrt(np.clip(vals,0,None)))@vecs.conj().T;middle=root@s@root
  return float(np.clip(np.sum(np.sqrt(np.clip(np.linalg.eigvalsh((middle+middle.conj().T)/2),0,None)))**2,0,1))
 @classmethod
 def detect_quantum_phase_transitions(cls,states:Sequence[np.ndarray],parameters:Sequence[float],dims:tuple[int,int])->QuantumPhaseReport:
  p=cls._vector(parameters,"parameters")
  if len(states)!=len(p) or len(p)<3 or np.any(np.diff(p)<=0):raise ValueError("at least three states with strictly increasing parameters required")
  ent=np.array([cls.von_neumann_entropy(cls.partial_trace(x,dims,"A")) for x in states]);fid=np.array([cls._fidelity(a,b) for a,b in zip(states,states[1:])]);grad=np.gradient(ent,p)
  score=np.abs(grad);threshold=float(np.median(score)+2*np.median(np.abs(score-np.median(score))));candidates=np.where(score>max(threshold,1e-12))[0]
  if not len(candidates) and score.max()>1e-12:candidates=np.array([int(np.argmax(score))])
  return QuantumPhaseReport(tuple(map(float,p)),tuple(map(float,ent)),tuple(map(float,fid)),tuple(map(float,grad)),tuple(map(int,candidates)),tuple(float(p[i]) for i in candidates))
 @staticmethod
 def compression_evidence(value:Any)->dict[str,Any]:
  raw=json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode();packed=zlib.compress(raw,9)
  return {"raw_bytes":len(raw),"compressed_bytes":len(packed),"compression_ratio":len(packed)/max(1,len(raw)),"sha256":"sha256:"+hashlib.sha256(raw).hexdigest(),"claim_boundary":"A compressor gives an upper bound for one encoding, not Kolmogorov complexity."}
 @classmethod
 def verify_complexity_evidence(cls,sizes:Sequence[float],solve_costs:Sequence[float],verification_costs:Sequence[float])->ComplexityEvidence:
  n=cls._vector(sizes,"sizes");solve=cls._vector(solve_costs,"solve_costs");verify=cls._vector(verification_costs,"verification_costs")
  if len(n)<4 or len(n)!=len(solve) or len(n)!=len(verify) or np.any(n<=0) or np.any(solve<=0) or np.any(verify<=0) or np.any(np.diff(n)<=0):raise ValueError("four positive ordered observations are required")
  logn=np.log(n);logs=np.log(solve);poly=np.polyfit(logn,logs,1);exp=np.polyfit(n,logs,1);pr=float(np.sqrt(np.mean((logs-np.polyval(poly,logn))**2)));er=float(np.sqrt(np.mean((logs-np.polyval(exp,n))**2)))
  asym=float(np.median(solve/verify));return ComplexityEvidence(tuple(map(float,n)),tuple(map(float,solve)),tuple(map(float,verify)),float(poly[0]),float(exp[0]),pr,er,"polynomial" if pr<=er else "exponential",asym)
 def validate_discovery(self,treatment_runs:Sequence[float],control_runs:Sequence[float],*,permutations:int=2000,min_effect:float=.05,max_p_value:float=.05,min_reproducibility:float=.8)->DiscoveryValidation:
  a=self._vector(treatment_runs,"treatment_runs");b=self._vector(control_runs,"control_runs")
  if len(a)<3 or len(b)<3 or permutations<1:raise ValueError("multiple runs and positive permutations required")
  effect=float(a.mean()-b.mean());pooled=np.concatenate((a,b));rng=random.Random(self.seed);extreme=0
  for _ in range(permutations):
   values=list(map(float,pooled));rng.shuffle(values);delta=np.mean(values[:len(a)])-np.mean(values[len(a):]);extreme+=abs(delta)>=abs(effect)-1e-15
  p=(extreme+1)/(permutations+1);paired=a[:min(len(a),len(b))]-b[:min(len(a),len(b))];sign=float(np.mean(np.sign(paired)==np.sign(effect))) if effect else float(np.mean(paired==0));scale=max(abs(effect),float(np.std(pooled)),1e-12);repro=float(np.clip(1-np.std(paired)/scale,0,1));protocol={"seed":self.seed,"n_treatment":len(a),"n_control":len(b),"permutations":permutations,"min_effect":min_effect,"max_p_value":max_p_value,"min_reproducibility":min_reproducibility};ph="sha256:"+hashlib.sha256(json.dumps(protocol,sort_keys=True,separators=(",",":")).encode()).hexdigest();passed=abs(effect)>=min_effect and p<=max_p_value and repro>=min_reproducibility
  return DiscoveryValidation(effect,p,repro,sign,bool(np.isfinite(pooled).all()),bool(passed),ph)
 @staticmethod
 def guided_exploration(phi_value:float,coherence_matrix:np.ndarray,directions:Mapping[str,Sequence[float]])->dict[str,Any]:
  phi=float(phi_value);matrix=np.asarray(coherence_matrix,float)
  if not math.isfinite(phi) or phi<0 or matrix.ndim!=2 or matrix.shape[0]!=matrix.shape[1] or not np.all(np.isfinite(matrix)) or not directions:raise ValueError("valid scalar field, square coherence matrix, and directions required")
  weights={}
  for name,vector in directions.items():
   v=np.asarray(vector,float).reshape(-1)
   if len(v)!=matrix.shape[0] or not np.all(np.isfinite(v)):raise ValueError("direction dimensions must match coherence matrix")
   weights[name]=float(phi*np.linalg.norm(matrix@v)/(np.linalg.norm(v)+1e-12))
  total=sum(weights.values());priorities={k:(v/total if total else 1/len(weights)) for k,v in weights.items()}
  return {"priorities":priorities,"claim_boundary":"Heuristic field-guided prioritisation; no consciousness inference and no evidence of mathematical truth."}

__all__=["SCHEMA","MathematicalFrontier","QuantumPhaseReport","ComplexityEvidence","DiscoveryValidation","TheoreticalSpaceExplorer"]
