"""Dependency-injected executable references for the HYBA service catalogue."""
from __future__ import annotations
from dataclasses import asdict,dataclass
import hashlib,json,os,sqlite3,time
from pathlib import Path
from typing import Any,Callable,Iterable,Mapping
from .observability import Metric,MetricKind,Observability,Source,dashboard
class FeatureDisabled(PermissionError):pass
class AckRequired(PermissionError):pass
class ServicePolicyError(PermissionError):pass
@dataclass(frozen=True)
class ServiceContext:tenant:str;instance:str;profile:str
class FlowService:
 def __init__(self,objects,sink,obs:Observability):self.objects=objects;self.sink=sink;self.obs=obs
 def start(self,events:Iterable,ctx:ServiceContext,classify,pick_scale,max_events:int|None=None):
  count=0
  for event in events:
   if max_events is not None and count>=max_events:break
   obj=self.objects.create(event,classify(event),pick_scale(event),ctx.tenant,ctx.instance);self.sink.put(obj);self.obs.emit(Metric("services.flow.events.total",MetricKind.COUNTER,"events",{"family":obj.payload_type},1,int(time.time()),ctx.tenant,ctx.instance,ctx.profile,Source.SERVICES));count+=1
  return count
class OntologyService:
 def __init__(self,path,verbs,permissions,classes,obs):
  self.verbs=set(verbs);self.permissions=set(permissions);self.classes=set(classes);self.obs=obs;self.db=sqlite3.connect(path);self.db.execute("CREATE TABLE IF NOT EXISTS bindings(tenant TEXT,name TEXT,obj_class TEXT,verbs TEXT,permissions TEXT,PRIMARY KEY(tenant,name))")
 def publish(self,tenant,instance,profile,binding):
  if not set(binding['verbs'])<=self.verbs or not set(binding['permissions'])<=self.permissions or binding['obj_class'] not in self.classes:raise ValueError("invalid ontology binding")
  with self.db:self.db.execute("INSERT INTO bindings VALUES(?,?,?,?,?)",(tenant,binding['name'],binding['obj_class'],json.dumps(binding['verbs']),json.dumps(binding['permissions'])))
  self.obs.emit(Metric("services.ontology.bindings.total",MetricKind.COUNTER,"bindings",{"name":binding['name']},1,int(time.time()),tenant,instance,profile,Source.SERVICES));return binding
 def resolve(self,tenant,name):
  row=self.db.execute("SELECT obj_class,verbs,permissions FROM bindings WHERE tenant=? AND name=?",(tenant,name)).fetchone()
  if not row:raise KeyError(name)
  return {"name":name,"obj_class":row[0],"verbs":json.loads(row[1]),"permissions":json.loads(row[2])}
 def close(self):self.db.close()
def agent_tick(candidate,regime,ctx,obs,supported,veto,actuator=None,safe="SAFE"):
 if not supported(candidate,regime) or veto(candidate):return safe
 if actuator is not None and not actuator(candidate):return safe
 obs.emit(Metric("services.agent_fabric.actions.total",MetricKind.COUNTER,"actions",{"action":str(candidate)},1,int(time.time()),ctx.tenant,ctx.instance,ctx.profile,Source.SERVICES));return candidate
@dataclass(frozen=True)
class QualityReport:schema_ok:bool;ranges_ok:bool;freshness_ok:bool;lineage_ok:bool;drift_score:str
def validate_quality(obj,expectations,checks):return QualityReport(bool(checks['schema'](obj,expectations)),bool(checks['ranges'](obj,expectations)),bool(checks['freshness'](obj,expectations)),bool(checks['lineage'](obj,expectations)),str(checks['drift'](obj,expectations)))
class ShareService:
 def __init__(self,path):self.db=sqlite3.connect(path);self.db.execute("CREATE TABLE IF NOT EXISTS shares(product_id TEXT PRIMARY KEY,tenant TEXT,residency TEXT,licence TEXT,state TEXT,at INTEGER)")
 def publish(self,product,tenant,residency):
  policy=product['policy']
  if policy.get('residency')!=residency or not policy.get('licence'):raise ServicePolicyError("residency and licence required")
  with self.db:self.db.execute("INSERT INTO shares VALUES(?,?,?,?,?,?)",(product['id'],tenant,residency,policy['licence'],'ACTIVE',int(time.time())));return product['id']
 def revoke(self,product_id):
  with self.db:self.db.execute("UPDATE shares SET state='REVOKED',at=? WHERE product_id=?",(int(time.time()),product_id))
 def close(self):self.db.close()
class ControlEvidenceService:
 def __init__(self,obs:Observability,obligations,locate,verify,sign):self.obs=obs;self.obligations=obligations;self.locate=locate;self.verify=verify;self.sign=sign
 def collect(self,control_id,ctx:ServiceContext):
  obligations=tuple(self.obligations(control_id,ctx.tenant));items=[]
  for obligation in obligations:
   item=self.locate(obligation,ctx.tenant,ctx.instance)
   if not self.verify(item):raise ValueError(f"unverified evidence: {obligation}")
   items.append(item)
  body={"control_id":control_id,"obligations":obligations,"evidence":tuple(getattr(x,"evidence_id",str(x)) for x in items),"verified_at":int(time.time())};body["signature"]=self.sign(body)
  self.obs.emit(Metric("services.evidence.receipts.total",MetricKind.COUNTER,"receipts",{"control":control_id},1,int(time.time()),ctx.tenant,ctx.instance,ctx.profile,Source.SERVICES));return body
class VaultCatalogue:
 def __init__(self,vault,path):self.vault=vault;self.db=sqlite3.connect(path);self.db.execute("CREATE TABLE IF NOT EXISTS legal_holds(tenant TEXT,resource_id TEXT,reason TEXT,created_at INTEGER,PRIMARY KEY(tenant,resource_id))")
 def backup(self,*args,**kwargs):return self.vault.backup(*args,**kwargs)
 def restore(self,*args,**kwargs):return self.vault.restore(*args,**kwargs)
 def legal_hold(self,tenant,resource_id,reason):
  if not reason:raise ValueError("legal-hold reason required")
  with self.db:self.db.execute("INSERT OR REPLACE INTO legal_holds VALUES(?,?,?,?)",(tenant,resource_id,reason,int(time.time())))
  return {"tenant":tenant,"resource_id":resource_id,"reason":reason}
 def close(self):self.db.close()
def federated_query(participants,query,aggregate):
 if not participants or not all(p.authenticated for p in participants):raise ServicePolicyError("participants must authenticate")
 if query['policy'].get('privacy_budget',0)<=0:raise ServicePolicyError("privacy budget exhausted")
 return aggregate([p.execute(query) for p in participants])
def edge_enroll(device,registry):
 identity=registry.enroll(device)
 if not identity.signed_by_attestation:raise ServicePolicyError("device attestation required")
 return identity
def edge_sync(buffer,verify,put):
 items=list(buffer.read())
 for item in items:
  if not verify(item):raise ValueError("edge envelope invalid")
  put(item)
 buffer.clear();return len(items)
def ota_update(device,bundle,verify):
 if not verify(bundle):raise ValueError("bundle signature invalid")
 device.stage(bundle)
 if device.self_test_passes():device.commit();return "COMMITTED"
 device.rollback();return "ROLLED_BACK"
def capture_notebook(session,environment)->dict:
 body=json.dumps(session,sort_keys=True,separators=(",",":"),default=str).encode();return {"session_hash":hashlib.sha256(body).hexdigest(),"cells":session['cells'],"outputs":session['outputs'],"env_hash":hashlib.sha256(json.dumps(environment,sort_keys=True).encode()).hexdigest(),"data_refs":session.get('data_references',()),"reproducible":True}
def promote_capture(capture,target,render_manifest,submit):return submit(render_manifest(capture),target)
class FunctionRegistry:
 LANGUAGES={"SQL","Python","Rust","C++","WASM","Algebraic"}
 def __init__(self):self.functions={}
 def register(self,fn):
  if fn.get('language') not in self.LANGUAGES or 'determinism' not in fn or 'resource_budget' not in fn or 'network_policy' not in fn:raise ValueError("function contract incomplete")
  self.functions[fn['id']]=dict(fn)
 def invoke(self,fn_id,args,ctx,authorize,sandbox_execute):
  fn=self.functions[fn_id]
  if not authorize("invoke",ctx,fn):raise ServicePolicyError("invoke denied")
  return sandbox_execute(fn,args)
def insight_alert(rule,tenant,query,fire):return fire(rule,tenant) if rule['matches'](query(rule['expr'],tenant)) else None
class DeployService:
 def __init__(self,compile_fn,apply_fn,attest_fn,previous_lock):self.compile_fn=compile_fn;self.apply_fn=apply_fn;self.attest_fn=attest_fn;self.previous_lock=previous_lock
 def compile(self,manifest):return self.compile_fn(manifest)
 def deploy(self,blueprint,target):self.apply_fn(blueprint,target);return self.attest_fn(blueprint,target)
 def rollback(self,deployment_id):lock=self.previous_lock(deployment_id);self.apply_fn(lock,None);return self.attest_fn(lock,None)
class ProofFacade:
 def __init__(self,proof_service,store):self.proofs=proof_service;self.store=store
 def certify(self,*args,**kwargs):
  proof=self.proofs.certify(*args,**kwargs);self.store[proof.proof_id]=proof;return proof
 def public(self,proof_id):return self.store[proof_id]
def quantum_submit(circuit,submit,physical_conformance,enabled=False):
 if not enabled:raise FeatureDisabled("quantum_access")
 if circuit.get('backend')=='physical_qpu' and not physical_conformance(circuit['backend']):raise ServicePolicyError("physical backend unconformant")
 return submit(circuit)
def privacy_run(mechanism,query,data,executors):
 if not all(mechanism.get(k) for k in ('threat_model','leakage_analysis','performance_baseline')):raise ServicePolicyError("privacy evidence incomplete")
 kind=mechanism.get('kind')
 if kind not in executors:raise FeatureDisabled(f"privacy mechanism: {kind}")
 return executors[kind](query,data,mechanism)
def autonomous_apply(proposal,apply_acknowledged):
 if proposal.get('requires_approval'):return "PENDING_APPROVAL"
 if not proposal.get('acknowledged'):raise AckRequired
 return apply_acknowledged(proposal)
def autonomous_propose(action,approved,collect):
 if not approved(action):raise ServicePolicyError("action outside approved envelope")
 return {"action":action,"evidence":collect(action),"requires_approval":True,"acknowledged":False}
def autonomous_rollback(action_id,revert):return revert(action_id)
def energy_schedule(workloads,telemetry,scheduler):
 if not telemetry.get('measured'):raise ValueError("measured telemetry required")
 return scheduler(workloads,telemetry['carbon'],telemetry['power'],telemetry['thermal'])
def energy_report(tenant,window,measure_energy,measure_carbon):return {"tenant":tenant,"window":window,"energy_joules":measure_energy(tenant,window),"carbon_grams":measure_carbon(tenant,window),"claim":"measured_only"}
