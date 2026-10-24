"""Operator-governed, reversible source modification.

Production writes are disabled by default.  The controller enforces path
containment, stable-core protection, syntax/safety validation, separation of
duties, content-hash pinning, atomic writes, immutable backups, and rollback.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import tempfile
import time
import uuid
from dataclasses import asdict,dataclass,field
from enum import Enum
from pathlib import Path
from typing import Callable,Iterable

from .memory_preservation import verified_atomic_json_write

class ModificationStatus(str,Enum):
    VALIDATED="validated";APPROVED="approved";APPLIED="applied";ROLLED_BACK="rolled_back";REJECTED="rejected"

@dataclass(frozen=True)
class ModificationProposal:
    proposal_id:str;target_relative:str;proposer:str;rationale:str
    expected_hash:str;proposed_hash:str;approval_digest:str;created_at:float
    new_source:str=field(repr=False)

@dataclass(frozen=True)
class ApprovalRecord:
    proposal_id:str;operator_id:str;approval_digest:str;approved_at:float;expires_at:float

@dataclass
class ModificationRecord:
    proposal:ModificationProposal;status:ModificationStatus
    approval:ApprovalRecord|None=None;backup_path:str|None=None;applied_hash:str|None=None
    events:list[dict[str,object]]=field(default_factory=list)

class GovernedModificationController:
    DEFAULT_PROTECTED=("pythia_mining/stratum_submission_firewall.py","pythia_mining/stratum_client.py",
        "pythia_mining/production_mining_gateway.py","hyba_substrate/safe_self_modification.py")
    FORBIDDEN_IMPORTS={"os","subprocess","socket","ctypes","multiprocessing"}
    FORBIDDEN_CALLS={"exec","eval","compile","__import__"}

    def __init__(self,root:str,backup_root:str,allowed_operators:Iterable[str],*,enable_apply:bool=False,
                 protected_paths:Iterable[str]|None=None,approval_ttl_s:int=900,state_path:str|None=None):
        self.root=Path(root).resolve();self.backup_root=Path(backup_root).resolve();self.backup_root.mkdir(parents=True,exist_ok=True)
        self.allowed_operators={str(x) for x in allowed_operators if str(x)};self.enable_apply=bool(enable_apply)
        self.protected_paths=set(protected_paths or self.DEFAULT_PROTECTED);self.approval_ttl_s=int(approval_ttl_s);self.state_path=state_path
        if not self.root.is_dir() or not self.allowed_operators or self.approval_ttl_s<=0:raise ValueError("valid root, operators, and approval TTL required")
        self.records:dict[str,ModificationRecord]={}
    @staticmethod
    def _hash(data:bytes)->str:return "sha256:"+hashlib.sha256(data).hexdigest()
    def _target(self,relative:str)->Path:
        if not relative or Path(relative).is_absolute():raise ValueError("target must be a relative path")
        raw=self.root/relative
        if raw.is_symlink():raise ValueError("symbolic-link targets are forbidden")
        target=raw.resolve()
        try:target.relative_to(self.root)
        except ValueError as e:raise ValueError("target escapes repository root") from e
        normalized=target.relative_to(self.root).as_posix()
        if normalized in self.protected_paths:raise PermissionError(f"stable-core target is protected: {normalized}")
        if target.suffix!=".py" or not target.is_file():raise ValueError("target must be an existing Python file")
        return target
    @classmethod
    def validate_source(cls,source:str)->None:
        if not source or len(source.encode())>1_000_000:raise ValueError("source must be non-empty and <= 1 MB")
        tree=ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                names=[a.name.split(".")[0] for a in node.names] if isinstance(node,ast.Import) else [(node.module or "").split(".")[0]]
                if cls.FORBIDDEN_IMPORTS.intersection(names):raise ValueError("forbidden import in proposed source")
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in cls.FORBIDDEN_CALLS:
                raise ValueError(f"forbidden call: {node.func.id}")
    def propose(self,target_relative:str,new_source:str,*,proposer:str,rationale:str)->ModificationProposal:
        if not proposer or not rationale.strip():raise ValueError("proposer and rationale required")
        target=self._target(target_relative);self.validate_source(new_source);current=target.read_bytes();proposed=new_source.encode()
        proposal_id=str(uuid.uuid4());expected=self._hash(current);new_hash=self._hash(proposed)
        digest=self._hash(f"{proposal_id}|{target_relative}|{expected}|{new_hash}|{proposer}|{rationale}".encode())
        p=ModificationProposal(proposal_id,target.relative_to(self.root).as_posix(),proposer,rationale,expected,new_hash,digest,time.time(),new_source)
        self.records[proposal_id]=ModificationRecord(p,ModificationStatus.VALIDATED,events=[{"event":"validated","at":time.time()}]);self._checkpoint();return p
    def approve(self,proposal_id:str,*,operator_id:str,approval_digest:str)->ApprovalRecord:
        record=self._record(proposal_id)
        if record.status is not ModificationStatus.VALIDATED:raise ValueError("proposal is not awaiting approval")
        if operator_id not in self.allowed_operators:raise PermissionError("operator is not authorized")
        if operator_id==record.proposal.proposer:raise PermissionError("separation of duties requires a different approver")
        if approval_digest!=record.proposal.approval_digest:raise ValueError("approval digest mismatch")
        now=time.time();approval=ApprovalRecord(proposal_id,operator_id,approval_digest,now,now+self.approval_ttl_s)
        record.approval=approval;record.status=ModificationStatus.APPROVED;record.events.append({"event":"approved","operator":operator_id,"at":now});self._checkpoint();return approval
    def apply(self,proposal_id:str,post_validator:Callable[[Path],bool]|None=None)->ModificationRecord:
        if not self.enable_apply:raise PermissionError("source application is disabled")
        record=self._record(proposal_id)
        if record.status is not ModificationStatus.APPROVED or record.approval is None:raise ValueError("approved proposal required")
        if time.time()>record.approval.expires_at:raise PermissionError("operator approval expired")
        target=self._target(record.proposal.target_relative);current=target.read_bytes()
        if self._hash(current)!=record.proposal.expected_hash:raise RuntimeError("target changed after proposal validation")
        self.validate_source(record.proposal.new_source)
        fd,tmp=tempfile.mkstemp(prefix=target.name+".",suffix=".candidate",dir=str(target.parent))
        try:
            with os.fdopen(fd,"wb") as f:f.write(record.proposal.new_source.encode());f.flush();os.fsync(f.fileno())
            candidate=Path(tmp)
            if post_validator is not None and not bool(post_validator(candidate)):raise RuntimeError("post-validation failed")
            backup=self.backup_root/f"{proposal_id}.bak"
            if backup.exists():raise RuntimeError("immutable backup already exists")
            with open(backup,"xb") as f:f.write(current);f.flush();os.fsync(f.fileno())
            os.replace(tmp,target)
            record.backup_path=str(backup);record.applied_hash=self._hash(target.read_bytes());record.status=ModificationStatus.APPLIED
            record.events.append({"event":"applied","at":time.time(),"hash":record.applied_hash});self._checkpoint();return record
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    def rollback(self,proposal_id:str)->ModificationRecord:
        if not self.enable_apply:raise PermissionError("source application is disabled")
        record=self._record(proposal_id)
        if record.status is not ModificationStatus.APPLIED or not record.backup_path:raise ValueError("applied proposal required")
        target=self._target(record.proposal.target_relative)
        if self._hash(target.read_bytes())!=record.applied_hash:raise RuntimeError("target changed after application; refusing blind rollback")
        backup=Path(record.backup_path);original=backup.read_bytes()
        fd,tmp=tempfile.mkstemp(prefix=target.name+".",suffix=".rollback",dir=str(target.parent))
        try:
            with os.fdopen(fd,"wb") as f:f.write(original);f.flush();os.fsync(f.fileno())
            os.replace(tmp,target)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        if self._hash(target.read_bytes())!=record.proposal.expected_hash:raise RuntimeError("rollback verification failed")
        record.status=ModificationStatus.ROLLED_BACK;record.events.append({"event":"rolled_back","at":time.time()});self._checkpoint();return record
    def reject(self,proposal_id:str,operator_id:str,reason:str)->ModificationRecord:
        if operator_id not in self.allowed_operators or not reason.strip():raise PermissionError("authorized operator and reason required")
        record=self._record(proposal_id)
        if record.status in (ModificationStatus.APPLIED,ModificationStatus.ROLLED_BACK):raise ValueError("cannot reject finalized proposal")
        record.status=ModificationStatus.REJECTED;record.events.append({"event":"rejected","operator":operator_id,"reason":reason,"at":time.time()});self._checkpoint();return record
    def _record(self,proposal_id:str)->ModificationRecord:
        if proposal_id not in self.records:raise ValueError("unknown proposal")
        return self.records[proposal_id]
    def _checkpoint(self):
        if not self.state_path:return
        payload={"schema":"HYBA_GOVERNED_MODIFICATION_V1","enable_apply":self.enable_apply,"records":{
            k:{"proposal":{x:y for x,y in asdict(v.proposal).items() if x!="new_source"},"status":v.status.value,
               "approval":asdict(v.approval) if v.approval else None,"backup_path":v.backup_path,"applied_hash":v.applied_hash,"events":v.events}
            for k,v in self.records.items()}}
        verified_atomic_json_write(Path(self.state_path).resolve(),payload)

__all__=["ModificationStatus","ModificationProposal","ApprovalRecord","ModificationRecord","GovernedModificationController"]
