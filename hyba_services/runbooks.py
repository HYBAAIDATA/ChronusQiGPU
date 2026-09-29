"""Machine-executable runbooks with signed step evidence."""
from __future__ import annotations
from dataclasses import asdict,dataclass
import hashlib,hmac,json,time
from typing import Any,Callable,Mapping
@dataclass(frozen=True)
class Runbook:id:str;title:str;trigger:str;prerequisites:tuple[str,...];steps:tuple[str,...];verification:tuple[str,...];rollback:tuple[str,...];escalation:tuple[str,...];evidence_emitted:tuple[str,...]
@dataclass(frozen=True)
class RunbookEvidence:runbook_id:str;started_at:int;finished_at:int;operator:str;tenant:str;steps_executed:tuple[str,...];verification_result:bool;rollback_used:bool;signature_algorithm:str;signature:str
class RunbookFailed(RuntimeError):pass
class RunbookRunner:
 def __init__(self,key:bytes):
  if len(key)<32:raise ValueError("runbook key too short")
  self.key=key
 def execute(self,runbook:Runbook,operator:str,tenant:str,actions:Mapping[str,Callable[[],Any]])->RunbookEvidence:
  started=time.time_ns();done=[];rollback=False
  try:
   for prereq in runbook.prerequisites:
    if prereq not in actions or not actions[prereq]():raise RunbookFailed(f"prerequisite: {prereq}")
   for step in runbook.steps:
    if step not in actions:raise RunbookFailed(f"missing step: {step}")
    actions[step]();done.append(step)
   verified=all(name in actions and bool(actions[name]()) for name in runbook.verification)
   if not verified:raise RunbookFailed("verification failed")
  except Exception:
   rollback=True
   for step in runbook.rollback:
    if step in actions:actions[step]()
   raise
  finally:finished=time.time_ns()
  unsigned={"runbook_id":runbook.id,"started_at":started,"finished_at":finished,"operator":operator,"tenant":tenant,"steps_executed":tuple(done),"verification_result":True,"rollback_used":rollback,"signature_algorithm":"HMAC-SHA256"};raw=json.dumps(unsigned,sort_keys=True,separators=(",",":")).encode();return RunbookEvidence(**unsigned,signature=hmac.new(self.key,raw,hashlib.sha256).hexdigest())
RUNBOOKS={
 "key_rotation":Runbook("key_rotation","Tenant key rotation","rotation_due",("new_key_attested",),("stage_new_key","enter_overlap","reissue_tokens","exit_overlap","retire_old_key"),("new_tokens_verify","old_key_retired"),("restore_old_key",),("security_owner",),("rotation_receipt",)),
 "schema_migration":Runbook("schema_migration","Forward schema migration","version_change",("migration_supported","snapshot_verified"),("enter_read_only","drain_in_flight","apply_steps","verify_schema","verify_witness","resume_writes"),("target_schema_verified","chain_verified"),("restore_snapshot","resume_previous_version"),("architecture_owner",),("migration_receipt","snapshot_hash")),
 "witness_loss":Runbook("witness_loss","Witness-loss recovery","anchor_stale",("last_receipt_verified",),("archive_chain","truncate_to_verified","revalidate_forward","quarantine_invalid","reanchor"),("new_anchor_verified",),("restore_archived_chain",),("security_owner","incident_response"),("incident_evidence",)),
 "guardian_deny_plus_witness_unavailable":Runbook("guardian_deny_plus_witness_unavailable","Guardian denial and witness outage","compound_failure",(),("hold_execution","verify_deny_reason","attempt_witness_failover","enter_degraded_deny"),("execution_held",),(),("incident_response",),("compound_failure_receipt",)),
 "cassini_mismatch_plus_audit_chain_tamper":Runbook("cassini_mismatch_plus_audit_chain_tamper","Integrity and chain tamper","compound_failure",(),("quarantine_objects","freeze_tenant_writes","restore_chain_from_witness","revalidate_objects","resume_degraded"),("objects_revalidated",),("keep_writes_frozen",),("incident_response",),("compound_failure_receipt",)),
 "backend_unavailable_plus_quota_exceeded":Runbook("backend_unavailable_plus_quota_exceeded","Backend and quota outage","compound_failure",(),("fail_closed","request_quota","wait_backend","resume"),("backend_attested",),(),("operations",),("compound_failure_receipt",)),
 "tenant_crossing_plus_revoked_entitlement":Runbook("tenant_crossing_plus_revoked_entitlement","Tenant crossing and revoked credential","compound_failure",(),("deny_request","invalidate_session","rotate_tenant_keys","audit_access","notify_security"),("session_invalid","keys_rotated"),(),("security_owner",),("compound_failure_receipt",))}
