"""Core semantic-version, schema migration, ABI and compatibility contracts."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import struct
from typing import Any,Callable,Mapping
class ChangeLevel(str,Enum):MAJOR="MAJOR";MINOR="MINOR";PATCH="PATCH"
@dataclass(frozen=True)
class Change:alters_byte_layout:bool=False;removes_public_symbol:bool=False;changes_public_semantics:bool=False;adds_public_symbol:bool=False;adds_optional_field:bool=False;bug_fix:bool=False
def classify(change:Change)->ChangeLevel:
 if change.alters_byte_layout or change.removes_public_symbol or change.changes_public_semantics:return ChangeLevel.MAJOR
 if change.adds_public_symbol or change.adds_optional_field:return ChangeLevel.MINOR
 if change.bug_fix:return ChangeLevel.PATCH
 raise ValueError("unclassified change")
class DowngradeNotSupported(ValueError):pass
class MigrationMissing(ValueError):pass
class SchemaMigrator:
 def __init__(self,steps:Mapping[tuple[int,int],Callable[[dict],dict]]):self.steps=dict(steps)
 def migrate(self,obj:dict,to_version:int)->dict:
  current=int(obj.get("schema_version",1))
  if current>to_version:raise DowngradeNotSupported
  result=dict(obj)
  while current<to_version:
   step=self.steps.get((current,current+1))
   if not step:raise MigrationMissing((current,current+1))
   result=step(dict(result));current+=1
   if result.get("schema_version")!=current:raise ValueError("migration did not set version")
  return result
def upgrade_v1_to_v2(obj:dict,compute_residual:Callable[[dict],Any])->dict:
 obj.update(schema_version=2,tenant="UNDEFINED_TENANT",instance="UNDEFINED_INSTANCE",residual_boundary=compute_residual(obj),lineage_and_time={"prev_hash":"GENESIS","seq":0});return obj
def upgrade_v2_to_v3(obj:dict,default_fold:Callable[[str],str])->dict:
 obj.update(schema_version=3,fold_contract_ref=default_fold(obj["payload_type"]));return obj
# Version is intentionally out-of-band: the frozen descriptor has no version slot.
HOT_DESCRIPTOR_V1=struct.Struct("<Q14I")
def check_abi(version:int,buffer:bytes)->bool:
 if version!=1:raise ValueError("unknown ABI version")
 if len(buffer)!=HOT_DESCRIPTOR_V1.size:raise ValueError("ABI size mismatch")
 return True
def read_hot(version:int,buffer:bytes)->tuple[int,...]:check_abi(version,buffer);return HOT_DESCRIPTOR_V1.unpack(buffer)
def parse_version(v:str)->tuple[int,int,int]:
 parts=v.split(".");
 if len(parts)!=3:raise ValueError(v)
 return tuple(int(x) for x in parts)
def satisfies(version:str,requirement:str)->bool:
 if requirement.endswith(".x"):return version.split(".")[:2]==requirement.split(".")[:2]
 if requirement.startswith(">="):return parse_version(version)>=parse_version(requirement[2:])
 return version==requirement
@dataclass(frozen=True)
class CompatibilityRow:core:str;pythia:str;enterprise:str;tested:bool=False
MATRIX=(CompatibilityRow("0.1.x","0.x","0.1.x"),CompatibilityRow("0.2.x","0.x","0.2.x"))
def compatible(core_version:str,pythia_requires:str,enterprise_requires:str)->bool:return satisfies(core_version,pythia_requires) and satisfies(core_version,enterprise_requires)
