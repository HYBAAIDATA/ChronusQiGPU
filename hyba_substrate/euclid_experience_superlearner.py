"""Experience-first policy learning for the EUCLID research substrate.

Recovered convergence edition: tabular TD learning, learned transition model,
Dyna replay, intrinsic novelty, transfer priors, autonomous curriculum and an
append-only transition hash chain. Human demonstrations are not silently used.
"""
from __future__ import annotations
import json, math, random, time, uuid
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Sequence
from .euclid_learning_system import MemoryKind
from .memory_preservation import canonical_json_bytes, sha256_bytes, verified_atomic_json_write
SCHEMA_VERSION="HYBA_EUCLID_EXPERIENCE_SUPERLEARNER_V1"
@dataclass(frozen=True)
class ExperienceTask:
 task_id:str; actions:tuple[str,...]; difficulty:float; reward_min:float; reward_max:float; transfer_group:str|None=None; metadata:dict[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class ExperienceTransition:
 transition_id:str; timestamp:float; task_id:str; state_key:str; action:str; reward:float; next_state_key:str; done:bool; td_error:float; intrinsic_bonus:float; previous_transition_hash:str|None; transition_hash:str; metadata:dict[str,Any]=field(default_factory=dict)
@dataclass
class WorldModelEntry:
 visits:int=0; reward_sum:float=0.0; next_state_counts:dict[str,int]=field(default_factory=dict); terminal_count:int=0
 @property
 def mean_reward(self)->float:return self.reward_sum/self.visits if self.visits else 0.0
 def most_likely_next(self)->str:return max(self.next_state_counts,key=self.next_state_counts.get) if self.next_state_counts else "null"
@dataclass(frozen=True)
class CurriculumSelection:
 task_id:str; priority:float; mastery:float; learning_progress:float; uncertainty:float; reason:str
class ExperienceSuperlearner:
 def __init__(self,state_path:str|Path|None=None,*,learning_system:Any|None=None,learning_rate:float=.2,discount:float=.95,epsilon:float=.15,planning_steps:int=8,curiosity_weight:float=.05,seed:int=20260718):
  for name,value in (("learning_rate",learning_rate),("discount",discount),("epsilon",epsilon)):
   number=float(value)
   if not math.isfinite(number) or not 0<=number<=1:raise ValueError(f"{name} must be finite and in [0,1]")
  if planning_steps<0 or curiosity_weight<0:raise ValueError("planning_steps and curiosity_weight must be nonnegative")
  self.state_path=str(Path(state_path).resolve()) if state_path else None; self.learning_system=learning_system; self.learning_rate=float(learning_rate); self.discount=float(discount); self.epsilon=float(epsilon); self.planning_steps=int(planning_steps); self.curiosity_weight=float(curiosity_weight); self.seed=int(seed); self._rng=random.Random(self.seed); self.human_data_used=False; self.tasks={}; self.q_values={}; self.action_visits={}; self.world_model={}; self.transitions=[]; self.task_rewards={}; self.transfer_records=[]; self._last_state_hash=None
  if self.state_path and Path(self.state_path).exists():self._load()
 @staticmethod
 def _unit(value:Any,name:str)->float:
  number=float(value)
  if not math.isfinite(number) or not 0<=number<=1:raise ValueError(f"{name} must be finite and in [0,1]")
  return number
 @staticmethod
 def _state_key(state:Any)->str:return canonical_json_bytes(state).decode("utf-8")
 @staticmethod
 def _pair_key(task_id:str,state_key:str)->str:return json.dumps([task_id,state_key],separators=(",",":"),ensure_ascii=False)
 @staticmethod
 def _model_key(task_id:str,state_key:str,action:str)->str:return json.dumps([task_id,state_key,action],separators=(",",":"),ensure_ascii=False)
 def register_task(self,task_id:str,actions:Sequence[str],*,difficulty:float=.5,reward_range:tuple[float,float]=(0.0,1.0),transfer_group:str|None=None,metadata:Mapping[str,Any]|None=None,persist:bool=True)->ExperienceTask:
  task_id=str(task_id).strip(); action_tuple=tuple(str(x).strip() for x in actions)
  if not task_id or not action_tuple or any(not x for x in action_tuple) or len(set(action_tuple))!=len(action_tuple):raise ValueError("task_id and unique nonempty actions are required")
  low,high=map(float,reward_range)
  if not math.isfinite(low) or not math.isfinite(high) or high<=low:raise ValueError("reward_range must be finite and increasing")
  candidate=ExperienceTask(task_id,action_tuple,self._unit(difficulty,"difficulty"),low,high,transfer_group,dict(metadata or {}))
  if task_id in self.tasks:
   if self.tasks[task_id]!=candidate:raise ValueError("task_id is already registered with a different specification")
   return self.tasks[task_id]
  self.tasks[task_id]=candidate; self.task_rewards[task_id]=[]
  if persist:self._checkpoint()
  return candidate
 def register_action(self,task_id:str,action:str)->ExperienceTask:
  """Extend a registered task's declared action vocabulary in place.

  A task's action set is a contract, not a cap: new measured actions widen it
  (existing q/visit rows are backfilled) rather than crashing the episode.
  """
  task=self.tasks.get(task_id)
  if task is None:raise ValueError("unknown task")
  action=str(action).strip()
  if not action:raise ValueError("action must be nonempty")
  if action in task.actions:return task
  merged=replace(task,actions=task.actions+(action,))
  self.tasks[task_id]=merged
  for key,row in self.q_values.items():
   if json.loads(key)[0]==task_id:row.setdefault(action,0.0)
  for key,row in self.action_visits.items():
   if json.loads(key)[0]==task_id:row.setdefault(action,0)
  self._checkpoint()
  return merged
 def _ensure_state(self,task_id:str,state_key:str)->tuple[dict[str,float],dict[str,int]]:
  if task_id not in self.tasks:raise ValueError("unknown task")
  pair=self._pair_key(task_id,state_key)
  if pair not in self.q_values:
   self.q_values[pair]={a:0.0 for a in self.tasks[task_id].actions}; self.action_visits[pair]={a:0 for a in self.tasks[task_id].actions}
  return self.q_values[pair],self.action_visits[pair]
 def select_action(self,task_id:str,state:Any,*,explore:bool=True)->str:
  state_key=self._state_key(state); q,visits=self._ensure_state(task_id,state_key)
  if explore and self._rng.random()<self.epsilon:return self._rng.choice(list(q))
  scored={a:v+self.curiosity_weight/math.sqrt(1+visits[a]) for a,v in q.items()}; best=max(scored.values()); return min(a for a,v in scored.items() if abs(v-best)<=1e-15)
 def observe(self,task_id:str,state:Any,action:str,reward:float,next_state:Any,*,done:bool=False,metadata:Mapping[str,Any]|None=None,persist:bool=True)->ExperienceTransition:
  if task_id not in self.tasks or action not in self.tasks[task_id].actions:raise ValueError("unknown task or action")
  reward_value=float(reward)
  if not math.isfinite(reward_value):raise ValueError("reward must be finite")
  state_key,next_key=self._state_key(state),self._state_key(next_state); q,visits=self._ensure_state(task_id,state_key); next_q,_=self._ensure_state(task_id,next_key); visits[action]+=1; intrinsic=self.curiosity_weight/math.sqrt(visits[action]); target=reward_value+intrinsic+(0.0 if done else self.discount*max(next_q.values())); td=target-q[action]; q[action]+=self.learning_rate*td
  model=self.world_model.setdefault(self._model_key(task_id,state_key,action),WorldModelEntry()); model.visits+=1; model.reward_sum+=reward_value; model.next_state_counts[next_key]=model.next_state_counts.get(next_key,0)+1; model.terminal_count+=int(done)
  previous=self.transitions[-1].transition_hash if self.transitions else None; base={"timestamp":time.time(),"task_id":task_id,"state_key":state_key,"action":action,"reward":reward_value,"next_state_key":next_key,"done":bool(done),"td_error":td,"intrinsic_bonus":intrinsic,"previous_transition_hash":previous,"metadata":dict(metadata or {})}; digest=sha256_bytes(canonical_json_bytes(base)); transition=ExperienceTransition("transition-"+uuid.uuid4().hex,base["timestamp"],task_id,state_key,action,reward_value,next_key,bool(done),td,intrinsic,previous,digest,base["metadata"]); self.transitions.append(transition); self.task_rewards[task_id].append(reward_value); self._plan()
  if self.learning_system is not None:
   scale=max(abs(self.tasks[task_id].reward_min),abs(self.tasks[task_id].reward_max),1.0); normalized=min(1.0,abs(td)/scale)
   self.learning_system.record_experience(domain=task_id,memory_kind=MemoryKind.PROCEDURAL,observation=state,prediction=q[action]-self.learning_rate*td,action=action,outcome=reward_value,uncertainty=min(1.0,1/math.sqrt(1+visits[action])),prediction_error=normalized,modules=("experience_superlearner",),metadata={"transition_hash":digest},persist=persist)
  if persist:self._checkpoint()
  return transition
 def _plan(self)->None:
  if not self.world_model or self.planning_steps<=0:return
  keys=list(self.world_model)
  for _ in range(self.planning_steps):
   key=self._rng.choice(keys); task_id,state_key,action=json.loads(key); model=self.world_model[key]; next_key=model.most_likely_next(); q,_=self._ensure_state(task_id,state_key); next_q,_=self._ensure_state(task_id,next_key); terminal=model.terminal_count/model.visits; target=model.mean_reward+(1-terminal)*self.discount*max(next_q.values()); q[action]+=self.learning_rate*(target-q[action])
 def transfer_prior(self,source_task_id:str,target_task_id:str,*,strength:float=.5,persist:bool=True)->dict[str,Any]:
  strength=self._unit(strength,"strength")
  if source_task_id not in self.tasks or target_task_id not in self.tasks:raise ValueError("source and target tasks must be registered")
  source,target=self.tasks[source_task_id],self.tasks[target_task_id]
  if not source.transfer_group or source.transfer_group!=target.transfer_group:raise ValueError("tasks must share a declared transfer group")
  shared=set(source.actions)&set(target.actions); rows=[r for k,r in self.q_values.items() if json.loads(k)[0]==source_task_id]; priors={a:sum(r.get(a,0.0) for r in rows)/len(rows) for a in shared} if rows else {a:0.0 for a in shared}; affected=0
  for key,row in self.q_values.items():
   if json.loads(key)[0]!=target_task_id:continue
   for action,prior in priors.items():row[action]=(1-strength)*row[action]+strength*prior
   affected+=1
  record={"source_task_id":source_task_id,"target_task_id":target_task_id,"strength":strength,"shared_actions":sorted(shared),"affected_states":affected,"timestamp":time.time(),"external_validation":False}; self.transfer_records.append(record)
  if persist:self._checkpoint()
  return record
 def task_metrics(self,task_id:str,window:int=100)->dict[str,float]:
  if task_id not in self.tasks or window<=1:raise ValueError("known task and window > 1 required")
  task=self.tasks[task_id]; rewards=self.task_rewards[task_id][-window:]
  if not rewards:return {"mean_reward":0.0,"mastery":0.0,"learning_progress":0.0,"uncertainty":1.0,"samples":0.0}
  mean=sum(rewards)/len(rewards); mastery=max(0.0,min(1.0,(mean-task.reward_min)/(task.reward_max-task.reward_min))); mid=len(rewards)//2
  progress=0.0
  if mid:
   earlier=sum(rewards[:mid])/mid; later=sum(rewards[mid:])/(len(rewards)-mid); progress=max(-1.0,min(1.0,(later-earlier)/(task.reward_max-task.reward_min)))
  visits=sum(sum(row.values()) for key,row in self.action_visits.items() if json.loads(key)[0]==task_id); return {"mean_reward":mean,"mastery":mastery,"learning_progress":progress,"uncertainty":1/math.sqrt(1+visits),"samples":float(len(rewards))}
 def autonomous_curriculum(self,limit:int=10)->list[CurriculumSelection]:
  if limit<=0:raise ValueError("limit must be positive")
  selections=[]
  for task_id,task in self.tasks.items():
   m=self.task_metrics(task_id); priority=min(1.0,.45*(1-m["mastery"])+.25*m["uncertainty"]+.2*max(0.0,m["learning_progress"])+.1*task.difficulty); selections.append(CurriculumSelection(task_id,priority,m["mastery"],m["learning_progress"],m["uncertainty"],f"mastery={m['mastery']:.3f}; progress={m['learning_progress']:.3f}; uncertainty={m['uncertainty']:.3f}"))
  return sorted(selections,key=lambda x:(-x.priority,x.task_id))[:limit]
 def evidence_report(self)->dict[str,Any]:
  return {"schema":"HYBA_EUCLID_EXPERIENCE_EVIDENCE_V1","generated_at":time.time(),"human_data_used":self.human_data_used,"tasks":{k:asdict(v) for k,v in self.tasks.items()},"task_metrics":{k:self.task_metrics(k) for k in self.tasks},"transitions":len(self.transitions),"world_model_entries":len(self.world_model),"transition_chain_head":self.transitions[-1].transition_hash if self.transitions else None,"transfer_records":self.transfer_records,"curriculum":[asdict(x) for x in self.autonomous_curriculum()] if self.tasks else [],"boundaries":{"internal_synthetic_evidence":True,"external_superiority_established":False,"superintelligence_established":False,"human_demonstrations_required":False,"seeded_formal_knowledge_retained":True}}
 def _payload(self)->dict[str,Any]:
  return {"schema":SCHEMA_VERSION,"previous_state_hash":self._last_state_hash,"config":{"learning_rate":self.learning_rate,"discount":self.discount,"epsilon":self.epsilon,"planning_steps":self.planning_steps,"curiosity_weight":self.curiosity_weight,"seed":self.seed,"human_data_used":self.human_data_used},"tasks":{k:asdict(v) for k,v in self.tasks.items()},"q_values":self.q_values,"action_visits":self.action_visits,"world_model":{k:asdict(v) for k,v in self.world_model.items()},"transitions":[asdict(v) for v in self.transitions],"task_rewards":self.task_rewards,"transfer_records":self.transfer_records}
 def _checkpoint(self)->None:
  if not self.state_path:return
  payload=self._payload(); payload["state_hash"]=sha256_bytes(canonical_json_bytes(payload)); verified_atomic_json_write(Path(self.state_path),payload); self._last_state_hash=payload["state_hash"]
 def _load(self)->None:
  payload=json.loads(Path(self.state_path).read_text()); supplied=payload.pop("state_hash",None)
  if payload.get("schema")!=SCHEMA_VERSION or supplied!=sha256_bytes(canonical_json_bytes(payload)):raise ValueError("persisted experience learner state is incompatible or corrupted")
  config=payload["config"]
  if bool(config.get("human_data_used")):raise ValueError("human demonstration state is not accepted by this experience-only learner")
  self.learning_rate=float(config["learning_rate"]);self.discount=float(config["discount"]);self.epsilon=float(config["epsilon"]);self.planning_steps=int(config["planning_steps"]);self.curiosity_weight=float(config["curiosity_weight"]);self.seed=int(config["seed"]);self._rng=random.Random(self.seed);self.tasks={k:ExperienceTask(**v) for k,v in payload.get("tasks",{}).items()};self.q_values={k:{a:float(v) for a,v in row.items()} for k,row in payload.get("q_values",{}).items()};self.action_visits={k:{a:int(v) for a,v in row.items()} for k,row in payload.get("action_visits",{}).items()};self.world_model={k:WorldModelEntry(**v) for k,v in payload.get("world_model",{}).items()};self.transitions=[ExperienceTransition(**v) for v in payload.get("transitions",[])];self.task_rewards={k:[float(v) for v in values] for k,values in payload.get("task_rewards",{}).items()};self.transfer_records=list(payload.get("transfer_records",[]));self._last_state_hash=supplied;self._validate_chain()
 def _validate_chain(self)->None:
  previous=None
  for transition in self.transitions:
   if transition.previous_transition_hash!=previous:raise ValueError("experience transition chain is discontinuous")
   base={"timestamp":transition.timestamp,"task_id":transition.task_id,"state_key":transition.state_key,"action":transition.action,"reward":transition.reward,"next_state_key":transition.next_state_key,"done":transition.done,"td_error":transition.td_error,"intrinsic_bonus":transition.intrinsic_bonus,"previous_transition_hash":transition.previous_transition_hash,"metadata":transition.metadata}
   if sha256_bytes(canonical_json_bytes(base))!=transition.transition_hash:raise ValueError("experience transition hash mismatch")
   previous=transition.transition_hash
__all__=["SCHEMA_VERSION","ExperienceTask","ExperienceTransition","WorldModelEntry","CurriculumSelection","ExperienceSuperlearner"]
