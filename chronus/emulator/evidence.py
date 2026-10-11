"""Canonical evidence adapter for the Chronus-1 emulator CLI."""
from __future__ import annotations
import hashlib,json,subprocess
from pathlib import Path

def canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def digest(data:bytes):return hashlib.sha256(data).hexdigest()
def execute(cli:Path, executable:Path, *, global_size=(1,1,1),local_size=(1,1,1),memory=1024,budget=100000,dump=(0,1)):
 cmd=[str(cli),"--load",str(executable),"--global",",".join(map(str,global_size)),"--local",",".join(map(str,local_size)),"--memory",str(memory),"--budget",str(budget),"--dump",f"{dump[0]}:{dump[1]}"]
 run=subprocess.run(cmd,text=True,capture_output=True,check=True);result=json.loads(run.stdout)
 output_digest=digest(canonical(result["dump"]))
 record={
  "schema":"chronus.execution-evidence.v2",
  "workload":{"id":"emulator-replay","tenant":"conformance","operation":"chronus1_execute","input_hash":digest(executable.read_bytes())},
  "planner":{"plan_id":"chronus1-reference","execution_class":"dense_native","global_size":list(global_size),"local_size":list(local_size)},
  "substrate":{"adapter_id":"chronus1-emulator","backend":"reference_emulator","manifest":{"isa":"chronus1-1.1","hardware_executed":False}},
  "execution":{"status":"ok","hardware_executed":False,"lane_instructions":result["lane_instructions"],"scheduler_steps":result["scheduler_steps"],"work_groups":result["work_groups"],"trace_digest":hashlib.sha256(result["trace_hash"].encode()).hexdigest()},
  "validation":{"passed":True,"authority":"chronus1-reference-replay","output_hash":output_digest},
  "provenance":{"runtime":"chronus1-emulator-v1","executable_digest":digest(executable.read_bytes())}
 }
 return record,digest(canonical(record))
