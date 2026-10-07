"""Deterministic, evidence-producing adversarial and stress testing.

Noise and event draws are Born-rule measurements on the quantum substrate,
not classical PRNG distributions: gaussian noise is sampled from the Born
distribution of a Gaussian wavefunction on a discretized grid, uniform noise
from a uniform superposition, and binary event/mask draws from biased
qubits. The seeded ``random.Random`` is only the classical randomness source
for measurement-outcome selection — every distribution sampled is the |psi|^2
of a constructed state, not an invented parametric draw.
"""
from __future__ import annotations
import json,math,random,time,uuid
from dataclasses import asdict,dataclass,field
from enum import Enum
from pathlib import Path
from typing import Any
import numpy as np
from kellogg.quantum_tensor import Complex,QuantumState

_NOISE_DIM=257  # discretized noise Hilbert-space basis over [-1,1]
class StressTestType(str,Enum):
 ADVERSARIAL_INPUT="adversarial_input";NOISE_INJECTION="noise_injection";EDGE_CASE="edge_case";CHAOS_ENVIRONMENT="chaos_environment";RESOURCE_EXHAUSTION="resource_exhaustion";TIMING_ATTACK="timing_attack"
class AdversarialScenario(str,Enum):
 DATA_POISONING="data_poisoning";MODEL_INVERSION="model_inversion";MEMBERSHIP_INFERENCE="membership_inference";GRADIENT_LEAKAGE="gradient_leakage";BYPASS_ATTACK="bypass_attack"
@dataclass(frozen=True)
class AdversarialInput:
 input_name:str;input_data:Any;attack_type:AdversarialScenario;expected_behavior:str;severity:str="medium"
@dataclass(frozen=True)
class StressTestResult:
 result_id:str;test_type:StressTestType;test_name:str;passed:bool;system_response:Any;response_time_ms:float;error_type:str|None=None;metrics:dict[str,Any]=field(default_factory=dict);timestamp:float=field(default_factory=time.time)
class StressTestHarness:
 def __init__(self,seed:int=0,max_results:int=10000):
  if max_results<=0:raise ValueError("max_results must be positive")
  self.rng=random.Random(seed);self.test_results=[];self.adversarial_inputs=[];self.edge_cases=[];self.max_results=max_results
  self._noise_grid=np.linspace(-1.0,1.0,_NOISE_DIM)
  # Gaussian wavefunction: Born |psi|^2 is Gaussian; sigma chosen so the
  # distribution concentrates inside the grid.
  sigma=1.0/3.0
  self._gaussian_state=QuantumState.from_real_vector(np.exp(-(self._noise_grid**2)/(4.0*sigma*sigma)))
  self._uniform_state=QuantumState.uniform_superposition(_NOISE_DIM)
 def _born_indices(self,state,count):
  probs=state.probabilities()
  return self.rng.choices(range(len(probs)),weights=probs,k=count)
 def _biased_qubit(self,p_event):
  return QuantumState(2,[Complex(math.sqrt(1.0-p_event),0.0),Complex(math.sqrt(p_event),0.0)])
 def _add(self,r):
  if len(self.test_results)>=self.max_results:raise OverflowError("stress evidence capacity reached")
  self.test_results.append(r);return r
 def add_adversarial_input(self,input_name,input_data,attack_type,expected_behavior,severity="medium"):
  if not input_name or not expected_behavior or severity not in {"low","medium","high","critical"}:raise ValueError("invalid adversarial input")
  item=AdversarialInput(input_name,input_data,AdversarialScenario(attack_type),expected_behavior,severity);self.adversarial_inputs.append(item);return item
 def add_edge_case(self,edge_case_function):
  if not callable(edge_case_function):raise TypeError("edge case must be callable")
  self.edge_cases.append(edge_case_function)
 def inject_noise(self,data,noise_type="gaussian",noise_level=.1):
  arr=np.asarray(data,dtype=float)
  if not np.all(np.isfinite(arr)) or not math.isfinite(noise_level) or not 0<=noise_level<=1:raise ValueError("finite data and noise_level in [0,1] required")
  if noise_type=="gaussian":
   return arr+noise_level*self._noise_grid[np.asarray(self._born_indices(self._gaussian_state,arr.size))].reshape(arr.shape)
  if noise_type=="uniform":
   return arr+noise_level*self._noise_grid[np.asarray(self._born_indices(self._uniform_state,arr.size))].reshape(arr.shape)
  if noise_type=="salt_pepper":
   out=arr.copy();mask=np.asarray(self._born_indices(self._biased_qubit(noise_level),arr.size),dtype=bool).reshape(arr.shape)
   bits=self._born_indices(QuantumState.uniform_superposition(2),int(mask.sum()))
   out[mask]=bits;return out
  raise ValueError("unknown noise type")
 def _run(self,test_type,name,fn,validator,metrics):
  start=time.perf_counter();response=None;error=None
  try:response=fn();passed=bool(validator(response))
  except Exception as exc:passed=False;error=type(exc).__name__
  return self._add(StressTestResult(str(uuid.uuid4()),test_type,name,passed,response,(time.perf_counter()-start)*1000,error,metrics))
 def run_adversarial_test(self,system_under_test,item,oracle):
  if not callable(oracle):raise ValueError("explicit behavioral oracle required")
  return self._run(StressTestType.ADVERSARIAL_INPUT,item.input_name,lambda:system_under_test(item.input_data),lambda r:oracle(r,item.expected_behavior),{"attack_type":item.attack_type.value,"severity":item.severity})
 def run_noise_injection_test(self,system_under_test,clean_data,noise_levels=(.01,.05,.1,.2,.5),distance=lambda a,b:float(abs(float(a)-float(b))),max_degradation=.25):
  baseline=system_under_test(np.asarray(clean_data,dtype=float));results=[]
  for level in noise_levels:
   if not 0<=float(level)<=1:raise ValueError("noise level outside [0,1]")
   results.append(self._run(StressTestType.NOISE_INJECTION,f"noise_{level}",lambda l=level:system_under_test(self.inject_noise(clean_data,noise_level=l)),lambda r:math.isfinite(distance(baseline,r)) and distance(baseline,r)<=max_degradation,{"noise_level":float(level),"max_degradation":max_degradation}))
  return results
 def run_edge_case_tests(self,system_under_test,oracle):
  return [self._run(StressTestType.EDGE_CASE,f"edge_{i}",lambda f=f:system_under_test(f()),oracle,{}) for i,f in enumerate(self.edge_cases)]
 def simulate_chaos_environment(self,system_under_test,iterations=100,chaos_probability=.3,max_failure_rate=.1):
  if not 0<=chaos_probability<=1 or iterations<=0:raise ValueError("invalid chaos controls")
  failures=events=0;start=time.perf_counter();last=None
  draws=self._born_indices(self._biased_qubit(chaos_probability),iterations)
  for i,draw in enumerate(draws):
   if draw:
    events+=1
    try:last=system_under_test({"chaos_event":True,"sequence":i})
    except Exception:failures+=1
  rate=failures/max(events,1);return self._add(StressTestResult(str(uuid.uuid4()),StressTestType.CHAOS_ENVIRONMENT,"chaos",rate<=max_failure_rate,last,(time.perf_counter()-start)*1000,None,{"iterations":iterations,"chaos_events":events,"failures":failures,"failure_rate":rate}))
 def run_resource_exhaustion_test(self,system_under_test,work_items,max_failures=0):
  if not isinstance(work_items,(list,tuple)) or not work_items:raise ValueError("bounded work items required")
  failures=0;last=None;start=time.perf_counter()
  for item in work_items:
   try:last=system_under_test(item)
   except Exception:failures+=1
  return self._add(StressTestResult(str(uuid.uuid4()),StressTestType.RESOURCE_EXHAUSTION,"bounded_load",failures<=max_failures,last,(time.perf_counter()-start)*1000,None,{"work_items":len(work_items),"failures":failures,"failure_rate":failures/len(work_items)}))
 def run_timing_test(self,system_under_test,samples,max_ratio=2.0):
  if len(samples)<2 or max_ratio<1:raise ValueError("multiple samples and ratio >= 1 required")
  durations=[]
  for sample in samples:
   start=time.perf_counter();system_under_test(sample);durations.append(max((time.perf_counter()-start)*1000,1e-9))
  ratio=max(durations)/min(durations)
  return self._add(StressTestResult(str(uuid.uuid4()),StressTestType.TIMING_ATTACK,"timing_variance",ratio<=max_ratio,None,sum(durations),None,{"min_ms":min(durations),"max_ms":max(durations),"ratio":ratio}))
 def get_test_summary(self):
  total=len(self.test_results);passed=sum(r.passed for r in self.test_results);return {"total_tests":total,"passed":passed,"failed":total-passed,"pass_rate":passed/total if total else 0.0}
 def export(self,path):
  payload={"schema":"EUCLID_STRESS_EVIDENCE_V1","summary":self.get_test_summary(),"results":[{**asdict(r),"test_type":r.test_type.value} for r in self.test_results]};Path(path).write_text(json.dumps(payload,sort_keys=True,allow_nan=False,default=str),encoding="utf-8")
