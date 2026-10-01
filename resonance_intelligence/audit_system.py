"""Append-only, hash-chained governance audit ledger."""
from __future__ import annotations
import math,time,uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any,Callable,Mapping
from hyba_substrate.memory_preservation import canonical_json_bytes,sha256_bytes,verified_atomic_json_write
class AuditEventType(str,Enum):
 DECISION="decision";CONSTRAINT_VIOLATION="constraint_violation";KILL_SWITCH_TRIGGER="kill_switch_trigger";CONTAINMENT_ESCALATION="containment_escalation";MODULE_ISOLATION="module_isolation";DRIFT_DETECTED="drift_detected";ANOMALY_DETECTED="anomaly_detected";CONFIGURATION_CHANGE="configuration_change";ACCESS_GRANTED="access_granted";ACCESS_DENIED="access_denied"
class ComplianceStatus(str,Enum):COMPLIANT="compliant";WARNING="warning";NON_COMPLIANT="non_compliant";CRITICAL="critical"
@dataclass(frozen=True)
class AuditEvent:
 event_id:str;event_type:AuditEventType;timestamp:float;actor:str;action:str;details:Mapping[str,Any];severity:str;previous_hash:str|None;event_hash:str
 def payload(self):return {"event_id":self.event_id,"event_type":self.event_type.value,"timestamp":self.timestamp,"actor":self.actor,"action":self.action,"details":dict(self.details),"severity":self.severity,"previous_hash":self.previous_hash}
 def verify_signature(self):return sha256_bytes(canonical_json_bytes(self.payload()))==self.event_hash
@dataclass(frozen=True)
class ComplianceRule:
 rule_id:str;rule_name:str;description:str;check_function:Callable[[Mapping[str,Any]],tuple[bool,str]];severity:ComplianceStatus=ComplianceStatus.NON_COMPLIANT;is_active:bool=True
 def check(self,state):
  if not self.is_active:return True,"rule inactive",ComplianceStatus.COMPLIANT
  try:valid,msg=self.check_function(state);return bool(valid),str(msg),ComplianceStatus.COMPLIANT if valid else self.severity
  except Exception as exc:return False,f"rule error: {type(exc).__name__}: {exc}",ComplianceStatus.NON_COMPLIANT
@dataclass(frozen=True)
class AuditReport:
 report_id:str;report_time:float;time_range_start:float;time_range_end:float;total_events:int;events_by_type:Mapping[str,int];compliance_status:ComplianceStatus;findings:tuple[str,...];recommendations:tuple[str,...];ledger_head:str|None
class AuditSystem:
 def __init__(self,enable_tamper_evidence=True,max_events=100000):
  if max_events<=0:raise ValueError("max_events must be positive")
  self.enable_tamper_evidence=bool(enable_tamper_evidence);self.max_events=int(max_events);self.audit_log=[];self.compliance_rules={}
 def log_event(self,event_type,actor,action,details,severity="info"):
  if len(self.audit_log)>=self.max_events:raise OverflowError("audit capacity reached; archive before continuing")
  if not str(actor).strip() or not str(action).strip():raise ValueError("actor and action required")
  event_id="audit-"+uuid.uuid4().hex;timestamp=time.time();previous=self.audit_log[-1].event_hash if self.audit_log and self.enable_tamper_evidence else None
  payload={"event_id":event_id,"event_type":AuditEventType(event_type).value,"timestamp":timestamp,"actor":str(actor),"action":str(action),"details":dict(details),"severity":str(severity),"previous_hash":previous}
  event=AuditEvent(event_id,AuditEventType(event_type),timestamp,str(actor),str(action),dict(details),str(severity),previous,sha256_bytes(canonical_json_bytes(payload)));self.audit_log.append(event);return event
 def add_compliance_rule(self,rule_id,rule_name,description,check_function,severity=ComplianceStatus.NON_COMPLIANT):
  if rule_id in self.compliance_rules or not all(str(x).strip() for x in (rule_id,rule_name,description)) or not callable(check_function):raise ValueError("invalid or duplicate compliance rule")
  item=ComplianceRule(rule_id,rule_name,description,check_function,ComplianceStatus(severity));self.compliance_rules[rule_id]=item;return item
 def check_compliance(self,state):
  violations=[];rank={ComplianceStatus.COMPLIANT:0,ComplianceStatus.WARNING:1,ComplianceStatus.NON_COMPLIANT:2,ComplianceStatus.CRITICAL:3};overall=ComplianceStatus.COMPLIANT
  for item in self.compliance_rules.values():
   valid,message,status=item.check(state)
   if not valid:violations.append({"rule_id":item.rule_id,"rule_name":item.rule_name,"message":message,"status":status.value});overall=max((overall,status),key=lambda x:rank[x])
  return {"total_rules":len(self.compliance_rules),"compliant_rules":len(self.compliance_rules)-len(violations),"non_compliant_rules":len(violations),"violations":violations,"overall_status":overall.value}
 def verify_chain_integrity(self):
  previous=None;violations=[]
  for index,event in enumerate(self.audit_log):
   if not event.verify_signature():violations.append(f"event {index} signature invalid")
   if self.enable_tamper_evidence and event.previous_hash!=previous:violations.append(f"event {index} linkage invalid")
   previous=event.event_hash
  return {"enabled":self.enable_tamper_evidence,"valid":not violations,"violations":violations,"total_events":len(self.audit_log),"head":previous}
 def generate_audit_report(self,start=None,end=None):
  end=time.time() if end is None else float(end);start=(self.audit_log[0].timestamp if self.audit_log else 0.0) if start is None else float(start)
  if not all(math.isfinite(x) for x in (start,end)) or start>end:raise ValueError("invalid report range")
  events=[e for e in self.audit_log if start<=e.timestamp<=end];counts={}
  for e in events:counts[e.event_type.value]=counts.get(e.event_type.value,0)+1
  critical=[e for e in events if e.severity=="critical"];violations=[e for e in events if e.event_type is AuditEventType.CONSTRAINT_VIOLATION]
  status=ComplianceStatus.CRITICAL if critical else ComplianceStatus.NON_COMPLIANT if violations else ComplianceStatus.COMPLIANT
  findings=tuple(filter(None,(f"{len(critical)} critical events" if critical else "",f"{len(violations)} constraint violations" if violations else "")))
  return AuditReport("report-"+uuid.uuid4().hex,time.time(),start,end,len(events),counts,status,findings,("review unresolved critical evidence",) if findings else (),self.audit_log[-1].event_hash if self.audit_log else None)
 def export(self,path):
  payload={"schema":"HYBA_EUCLID_AUDIT_V1","events":[{**e.payload(),"event_hash":e.event_hash} for e in self.audit_log],"integrity":self.verify_chain_integrity()};return verified_atomic_json_write(path,payload)

__all__=["AuditEventType","ComplianceStatus","AuditEvent","ComplianceRule","AuditReport","AuditSystem"]
