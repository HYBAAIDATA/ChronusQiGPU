"""Governed boot self-diagnostic: self-verification, never self-permission."""
from __future__ import annotations
import hashlib,importlib,os,secrets,tempfile,time,uuid
from dataclasses import asdict,dataclass,field
from enum import Enum
from pathlib import Path
from typing import Any,Callable,Mapping
from hyba_substrate.memory_preservation import FilesystemPersistenceAuditor,MemoryVault,verified_atomic_json_write
from resonance_intelligence.audit_system import AuditEventType,AuditSystem
from resonance_intelligence.fallback_modes import FallbackMode,RedundancyManager
from .subsystem_registry import HealthLevel,SubsystemRegistry

class StartupVerdict(str,Enum):GREEN="green";YELLOW="yellow";RED="red"
class CheckLevel(str,Enum):PASS="pass";DEGRADED="degraded";FAIL="fail"
@dataclass(frozen=True)
class StartupCheck:
 phase:int;name:str;status:CheckLevel;critical:bool;latency_ms:float;error_code:str|None;details:Mapping[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class StartupReport:
 report_id:str;started_at:float;completed_at:float;verdict:StartupVerdict;checks:tuple[StartupCheck,...];subsystems:Mapping[str,Any];audit_head:str|None;handoff:Mapping[str,bool];live_share_submission_enabled:bool
 def to_dict(self):
  return {"schema":"HYBA_EUCLID_STARTUP_REPORT_V1","report_id":self.report_id,"started_at":self.started_at,"completed_at":self.completed_at,"verdict":self.verdict.value,"checks":[{**asdict(x),"status":x.status.value} for x in self.checks],"subsystems":dict(self.subsystems),"audit_head":self.audit_head,"handoff":dict(self.handoff),"live_share_submission_enabled":self.live_share_submission_enabled}
class StartupOrchestrator:
 BACKEND_MODULES=("resonance_intelligence.global_state","resonance_intelligence.identity_drift","resonance_intelligence.meta_intelligence","resonance_intelligence.feedback_core","resonance_intelligence.causal_attribution","resonance_intelligence.coherence_runtime","hyba_substrate.world_system_model","hyba_substrate.emergence_experiment","hyba_substrate.organism_coherence","hyba_substrate.euclid_experience_superlearner","hyba_substrate.safe_self_modification")
 def __init__(self,registry:SubsystemRegistry,*,root:str|Path,vault_path:str|Path,report_path:str|Path,audit:AuditSystem|None=None,redundancy:RedundancyManager|None=None,frontend_probes:Mapping[str,Callable[[],bool]]|None=None,pool_probe:Callable[[],Mapping[str,Any]]|None=None,baseline_hashes:Mapping[str,str]|None=None):
  self.registry=registry;self.root=Path(root).resolve();self.vault_path=Path(vault_path).resolve();self.report_path=Path(report_path).resolve();self.audit=audit or AuditSystem();self.redundancy=redundancy or RedundancyManager();self.frontend_probes=dict(frontend_probes or {});self.pool_probe=pool_probe;self.baseline_hashes=dict(baseline_hashes or {})
 def _run(self,phase,name,critical,fn):
  start=time.perf_counter();details={};error=None
  try:
   outcome=fn();passed=bool(outcome if not isinstance(outcome,Mapping) else outcome.get("passed",False));details=dict(outcome) if isinstance(outcome,Mapping) else {"result":bool(outcome)};status=CheckLevel.PASS if passed else (CheckLevel.FAIL if critical else CheckLevel.DEGRADED);error=None if passed else details.get("error_code","CHECK_FALSE")
  except Exception as exc:status=CheckLevel.FAIL if critical else CheckLevel.DEGRADED;error=type(exc).__name__;details={"error_type":type(exc).__name__}
  item=StartupCheck(phase,name,status,critical,(time.perf_counter()-start)*1000,error,details);self.audit.log_event(AuditEventType.CONFIGURATION_CHANGE,"startup",name,{"phase":phase,"status":status.value,"error_code":error},"critical" if status is CheckLevel.FAIL and critical else "warning" if status is not CheckLevel.PASS else "info");return item
 def _filesystem(self):return {"passed":FilesystemPersistenceAuditor().audit([self.vault_path])["all_verified"],"path":str(self.vault_path)}
 def _strict_json(self):
  probe=self.vault_path/("startup-json-"+uuid.uuid4().hex+".json");result=verified_atomic_json_write(probe,{"probe":True,"finite":1.0});probe.unlink(missing_ok=True);Path(str(probe)+".sha256").unlink(missing_ok=True);return {"passed":result.readback_verified}
 def _memory_vault_roundtrip(self):
  with tempfile.TemporaryDirectory(prefix="euclid-startup-vault-",dir=self.vault_path) as directory:
   root=Path(directory);source=root/"probe.json";verified_atomic_json_write(source,{"values":list(range(16)),"identity":"EUCLID"},preserve_history=False)
   vault=MemoryVault([root/"vault"]);manifest=vault.preserve_json_files([source],label="startup Merkle and compression probe");verification=vault.verify_snapshot(manifest["snapshot_id"])
   artifact=manifest["artifacts"][0]
   return {"passed":bool(verification["verified"] and artifact["folded_objects"]>0),"merkle_root":artifact["merkle_root"],"folded_objects":artifact["folded_objects"],"numeric_folds":len(artifact["numeric_folds"])}
 def _entropy_clock(self):
  a=time.time();token=secrets.token_bytes(32);b=time.time();return {"passed":len(token)==32 and b>=a,"clock_delta":b-a,"entropy_digest":hashlib.sha256(token).hexdigest()[:16]}
 def _backend_imports(self):
  failed=[]
  for name in self.BACKEND_MODULES:
   try:importlib.import_module(name)
   except Exception as exc:failed.append({"module":name,"error":type(exc).__name__})
  return {"passed":not failed,"checked":len(self.BACKEND_MODULES),"failed":failed}
 def _fingerprints(self):
  mismatches=[]
  for relative,expected in self.baseline_hashes.items():
   path=(self.root/relative).resolve()
   try:path.relative_to(self.root)
   except ValueError:mismatches.append({"path":relative,"reason":"escape"});continue
   actual="sha256:"+hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
   if actual!=expected:mismatches.append({"path":relative,"reason":"hash_mismatch_or_missing"})
  return {"passed":not mismatches,"pinned":len(self.baseline_hashes),"mismatches":mismatches}
 def _frontend(self):
  if not self.frontend_probes:return {"passed":False,"error_code":"FRONTEND_PROBES_NOT_CONFIGURED","protocols":[]}
  results={}
  for name,probe in self.frontend_probes.items():
   try:results[name]=bool(probe())
   except Exception:results[name]=False
  return {"passed":all(results.values()),"protocols":results}
 def _pool(self):
  share_enabled=os.getenv("HYBA_ENABLE_LIVE_SHARE_SUBMIT","").strip().lower() in {"1","true","yes","on"}
  if share_enabled:return {"passed":False,"error_code":"LIVE_SHARE_SUBMISSION_ENABLED","share_submission_disabled":False}
  if self.pool_probe is None:return {"passed":False,"error_code":"POOL_PROBE_NOT_CONFIGURED","share_submission_disabled":True,"network_action_performed":False}
  result=dict(self.pool_probe());return {"passed":bool(result.get("handshake") and result.get("authenticated") and result.get("telemetry")),"share_submission_disabled":True,**result}
 def _share_submission_disabled(self):
  enabled=os.getenv("HYBA_ENABLE_LIVE_SHARE_SUBMIT","").strip().lower() in {"1","true","yes","on"}
  return {"passed":not enabled,"live_share_submission_enabled":enabled,"error_code":"LIVE_SHARE_SUBMISSION_ENABLED" if enabled else None}
 def boot(self):
  started=time.time();checks=[]
  # Phase 0: inability to preserve evidence is a hard stop.
  checks.append(self._run(0,"vault_filesystem",True,self._filesystem));checks.append(self._run(0,"strict_json_writer",True,self._strict_json));checks.append(self._run(0,"merkle_compression_roundtrip",True,self._memory_vault_roundtrip))
  # Phase 1: local wiring. Network checks are delegated to explicit probes.
  checks.append(self._run(1,"clock_and_entropy",True,self._entropy_clock));checks.append(self._run(1,"cpu_available",True,lambda:{"passed":(os.cpu_count() or 0)>0,"cpu_count":os.cpu_count() or 0}));checks.append(self._run(1,"gpu_observation",False,lambda:{"passed":True,"available":Path('/dev/nvidia0').exists(),"required":False}))
  checks.append(self._run(2,"backend_imports",True,self._backend_imports));checks.append(self._run(2,"hash_pinned_baselines",bool(self.baseline_hashes),self._fingerprints))
  checks.append(self._run(3,"frontend_contracts",False,self._frontend));checks.append(self._run(4,"live_share_submission_disabled",True,self._share_submission_disabled));checks.append(self._run(4,"pool_observation",False,self._pool))
  subsystem_raw=self.registry.run_health_checks();subsystems={};critical_failed=False;degraded=False
  for name,row in subsystem_raw.items():
   descriptor=row["descriptor"];status=row["status"];critical_failed|=descriptor.critical and status.status is HealthLevel.FAILED;degraded|=status.status is not HealthLevel.HEALTHY
   subsystems[name]={"kind":descriptor.kind.value,"responsibility":descriptor.responsibility,"status":status.status.value,"confidence":status.confidence,"details":dict(status.details),"suggested_fallback":status.suggested_fallback,"error_code":status.error_code,"latency_ms":row["latency_ms"]}
   checks.append(self._run(5,"subsystem:"+name,descriptor.critical,lambda s=status:{"passed":s.status is not HealthLevel.FAILED,"health_status":s.status.value,"confidence":s.confidence,"error_code":s.error_code}))
  hard_failure=any(c.status is CheckLevel.FAIL and c.critical for c in checks) or critical_failed
  advisory=any(c.status is not CheckLevel.PASS for c in checks) or degraded
  verdict=StartupVerdict.RED if hard_failure else StartupVerdict.YELLOW if advisory else StartupVerdict.GREEN
  if verdict is StartupVerdict.RED:self.redundancy.set_fallback_mode(FallbackMode.EMERGENCY,reason="startup critical failure")
  elif verdict is StartupVerdict.YELLOW:self.redundancy.set_fallback_mode(FallbackMode.DEGRADED,reason="startup advisory degradation")
  else:self.redundancy.set_fallback_mode(FallbackMode.FULL,reason="startup checks passed")
  live_share=os.getenv("HYBA_ENABLE_LIVE_SHARE_SUBMIT","").strip().lower() in {"1","true","yes","on"};handoff={"higher_cognition":verdict is not StartupVerdict.RED,"learning":verdict is not StartupVerdict.RED,"mining_readiness":verdict is not StartupVerdict.RED,"live_share_submission":False}
  self.audit.log_event(AuditEventType.CONFIGURATION_CHANGE,"startup","startup_verdict",{"verdict":verdict.value,"report_path":str(self.report_path),"handoff":handoff},"critical" if verdict is StartupVerdict.RED else "warning" if verdict is StartupVerdict.YELLOW else "info")
  integrity=self.audit.verify_chain_integrity();report=StartupReport("startup-"+uuid.uuid4().hex,started,time.time(),verdict,tuple(checks),subsystems,integrity["head"],handoff,live_share)
  verified_atomic_json_write(self.report_path,report.to_dict());return report

__all__=["StartupVerdict","CheckLevel","StartupCheck","StartupReport","StartupOrchestrator"]
