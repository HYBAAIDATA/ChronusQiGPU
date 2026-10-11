"""Reference and translated-backend adapter implementations."""
from __future__ import annotations
import json,subprocess,tempfile
from abc import ABC,abstractmethod
from pathlib import Path
from typing import Any,Callable,Mapping
import numpy as np
from compiler import compile_ir
from .corpus import CorpusStore
from .model import CapabilityManifest,Execution,canonical,sha256

class BackendAdapter(ABC):
 @abstractmethod
 def identity(self)->Mapping[str,Any]:...
 @abstractmethod
 def capabilities(self)->CapabilityManifest:...
 @abstractmethod
 def translate(self,case:Mapping[str,Any],corpus:CorpusStore)->bytes|None:...
 @abstractmethod
 def execute(self,case:Mapping[str,Any],corpus:CorpusStore)->Execution:...
 @abstractmethod
 def evidence(self)->Mapping[str,Any]:...

class ReferenceChronusAdapter(BackendAdapter):
 def __init__(self,root:Path,emulator:Path|None=None):self.root=Path(root);self.emulator=emulator or self.root/'emulator/build/chronus-emu'
 def identity(self):return {'adapter_id':'chronus1-reference','backend':'CHRONUS1_EMULATOR','executable':str(self.emulator)}
 def capabilities(self):
  return CapabilityManifest('chronus1-reference','CHRONUS1_EMULATOR','software-reference',False,['chronus-1.1','chronus.ir.v0.1'],['vector_add','reduce_sum_local','matmul_tiled'],['f32'],['direct-machine','compiled-ir'],'exact',{}, {x:'SOFTWARE_VERIFIED' for x in ('vector_add','reduce_sum_local','matmul_tiled')},compiler='chronus-subset-v0.1')
 def translate(self,case,corpus):return corpus.artifact('binaries',case.get('executable_sha256'))
 def execute(self,case,corpus):
  if case['class']=='isa':return Execution('NOT_APPLICABLE_TO_TRANSLATED_BACKEND',metadata={'reason':'#104 declaration has no executable artifact'})
  ir=json.loads(corpus.artifact('ir',case['ir_sha256']))
  if case['expected_status']=='REJECTED_IR':
   try:compile_ir(ir)
   except ValueError:return Execution('REJECTED_IR')
   return Execution('HARNESS_ERROR',metadata={'reason':'IR unexpectedly compiled'})
  comp=compile_ir(ir);raw=corpus.artifact('inputs',case['input_sha256']);op=case['operation'];n=ir['shape'].get('n')
  if op=='vector_add':a=np.frombuffer(raw[:4*n],'<f4');b=np.frombuffer(raw[4*n:],'<f4');uploads=[(comp.memory['A'],a),(comp.memory['B'],b),(comp.memory['ONE'],np.asarray([1],np.float32))];dump=(comp.memory['C'],n)
  elif op=='reduce_sum_local':a=np.frombuffer(raw,'<f4');uploads=[(comp.memory['A'],a),(comp.memory['ONE'],np.asarray([1],np.float32))];dump=(comp.memory['OUT'],1)
  else:a=np.frombuffer(raw[:4096],'<f4');b=np.frombuffer(raw[4096:],'<f4');uploads=[(comp.memory['A'],a),(comp.memory['B'],b)];dump=(comp.memory['C'],1024)
  if not self.emulator.is_file():return Execution('HARNESS_ERROR',metadata={'reason':'reference emulator unavailable'})
  with tempfile.TemporaryDirectory() as td:
   td=Path(td);exe=td/'case.chronus';exe.write_bytes(comp.container);cmd=[str(self.emulator),'--load',str(exe),'--global',','.join(map(str,comp.geometry.global_size)),'--local',','.join(map(str,comp.geometry.local_size)),'--memory',str(comp.memory['required_bytes']),'--dump',f'{dump[0]}:{dump[1]}']
   for i,(address,array) in enumerate(uploads):p=td/f'in{i}.bin';p.write_bytes(np.asarray(array,dtype='<f4').tobytes());cmd+=['--upload',f'{p}@{address}']
   try:r=json.loads(subprocess.check_output(cmd,text=True))
   except subprocess.CalledProcessError as exc:return Execution('HARNESS_ERROR',metadata={'returncode':exc.returncode})
  out=np.asarray(r['dump'],dtype='<u4').tobytes();return Execution('PASS',out,trace=str(r.get('trace_hash','')).encode(),translated_artifact=comp.container)
 def evidence(self):return {'authority':'Chronus-1 reference emulator','physical':False}

_OPENCL={
'vector_add':b'__kernel void chronus_vector_add(__global const float*a,__global const float*b,__global float*c,uint n){uint i=get_global_id(0);if(i<n)c[i]=fma(a[i],1.0f,b[i]);}',
'reduce_sum_local':b'__kernel void chronus_reduce(__global const float*a,__global float*out,__local float*s,uint n){uint i=get_local_id(0);s[i]=i<n?a[i]:0.0f;barrier(CLK_LOCAL_MEM_FENCE);for(uint d=get_local_size(0)/2;d;d>>=1){if(i<d)s[i]=fma(s[i+d],1.0f,s[i]);barrier(CLK_LOCAL_MEM_FENCE);}if(i==0)out[0]=s[0];}',
'matmul_tiled':b'__kernel void chronus_matmul(__global const float*a,__global const float*b,__global float*c){uint r=get_global_id(0),q=get_global_id(1);float x=0.0f;for(uint k=0;k<32;k++)x=fma(a[r*32+k],b[k*32+q],x);c[r*32+q]=x;}',}
class IntelOpenCLTranslatedAdapter(BackendAdapter):
 def __init__(self,runner:Callable[...,tuple[bytes,Mapping[str,Any]]]|None=None,identity:Mapping[str,Any]|None=None):self.runner=runner;self._identity=dict(identity or {})
 def identity(self):return {'adapter_id':'intel-opencl-translated','backend':'OPENCL_TRANSLATED',**self._identity}
 def capabilities(self):
  physical=self.runner is not None and bool(self._identity.get('physical_evidence_digest'))
  state='VERIFIED' if physical else 'PHYSICAL_EVIDENCE_REQUIRED'
  return CapabilityManifest('intel-opencl-translated','OPENCL_TRANSLATED',self._identity.get('device','UNBOUND'),physical,['chronus.ir.v0.1'],list(_OPENCL),['f32'],['translated-ir'],'translated-no-machine-traps',{'timestamps':physical},{x:state for x in _OPENCL},driver=self._identity.get('driver',''),runtime=self._identity.get('runtime',''),compiler=self._identity.get('compiler','OpenCL C'),physical_evidence_digest=self._identity.get('physical_evidence_digest'))
 def translate(self,case,corpus):
  if case['class']!='semantic' or case['operation'] not in _OPENCL:return None
  return _OPENCL[case['operation']]
 def execute(self,case,corpus):
  artifact=self.translate(case,corpus)
  if artifact is None:return Execution('NOT_APPLICABLE_TO_TRANSLATED_BACKEND')
  if self.runner is None:return Execution('PHYSICAL_EVIDENCE_REQUIRED',translated_artifact=artifact)
  output,evidence=self.runner(case,corpus,artifact)
  if not evidence.get('hardware_executed') or not evidence.get('device') or not evidence.get('driver'):return Execution('HARNESS_ERROR',metadata={'reason':'runner omitted physical identity'})
  return Execution('PASS',output,translated_artifact=artifact,physical_evidence=evidence)
 def evidence(self):return {'translation':'Chronus semantic operation -> OpenCL C','native_chronus_opcodes':False,'fallback':False}
