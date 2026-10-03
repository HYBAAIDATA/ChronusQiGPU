from __future__ import annotations
import hashlib,json,shutil,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from conformance.canonical import canonical,case_id,sha,tree_digest
from conformance.generators.semantic import named,generated
from conformance.generators.inputs import values
from conformance.generators.isa import cases as isa_cases
from conformance.oracle import vector_add,reduce_sum_local,matmul_tiled,ORACLE,POLICY
from compiler import compile_ir

def put(root,kind,data):
 d=sha(data);p=root/'artifacts'/kind/d;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);return d

def build(root):
 root=Path(root);shutil.rmtree(root,ignore_errors=True);(root/'cases/semantic').mkdir(parents=True)
 records=[]
 (root/'cases/isa').mkdir(parents=True)
 (root/'results/reference').mkdir(parents=True)
 for m in isa_cases():
  rec={'schema':'chronus.conformance.case.v1','case_id':'','class':'isa','operation':m['name'],'seed':m.get('seed'),'ir_sha256':None,'input_sha256':None,'executable_sha256':None,'expected_sha256':None,'expected_status':m['status'],'expected_trap':m['trap'],'limits':{'instruction_budget':10000000,'barrier_budget':4096}}
  rec['case_id']=case_id(rec);(root/'cases/isa'/f'{rec["case_id"][7:]}.json').write_bytes(canonical(rec));records.append(rec)
  result={'schema':'chronus.conformance.result.v1','case_id':rec['case_id'],'runner':'not-run','runner_sha256':None,'actual_sha256':None,'trace_sha256':None,'actual_status':'NOT_RUN','actual_trap':None,'passed':False}
  (root/'results/reference'/f'{rec["case_id"][7:]}.json').write_bytes(canonical(result))
 for index,(op,seed,ir,status) in enumerate(named()+generated()):
  irb=canonical(ir);ih=put(root,'ir',irb);inp=exe=expected=None
  if status=='PASS':
   c=compile_ir(ir);exe=put(root,'binaries',c.container)
   if op=='vector_add':
    n=ir['shape']['n'];a=values(seed,n);b=values(seed+1,n);raw=a.tobytes()+b.tobytes();out=vector_add(a,b)
   elif op=='reduce_sum_local':
    n=ir['shape']['n'];a=values(seed,n);raw=a.tobytes();out=reduce_sum_local(a)
   else:
    a=values(seed,1024).reshape(32,32);b=values(seed+1,1024).reshape(32,32);raw=a.tobytes()+b.tobytes();out=matmul_tiled(a,b)
   inp=put(root,'inputs',raw);expected=put(root,'expected',out.astype('<f4').tobytes())
  rec={'schema':'chronus.conformance.case.v1','case_id':'','class':'semantic','operation':op,'seed':seed,'ir_sha256':ih,'input_sha256':inp,'executable_sha256':exe,'expected_sha256':expected,'expected_status':status,'expected_trap':None,'limits':{'instruction_budget':10000000,'barrier_budget':4096}}
  rec['case_id']=case_id(rec);(root/'cases/semantic'/f'{rec["case_id"][7:]}.json').write_bytes(canonical(rec));records.append(rec)
  result={'schema':'chronus.conformance.result.v1','case_id':rec['case_id'],'runner':'not-run','runner_sha256':None,'actual_sha256':None,'trace_sha256':None,'actual_status':'NOT_RUN','actual_trap':None,'passed':False}
  (root/'results/reference'/f'{rec["case_id"][7:]}.json').write_bytes(canonical(result))
 seed_digest=sha(canonical([x[1] for x in named()+generated()]))
 case_root=sha(canonical(sorted(r['case_id'] for r in records)));artifact_root=tree_digest(root/'artifacts')
 source=Path(__file__).read_bytes()+ (ROOT/'conformance/generators/semantic.py').read_bytes()+ (ROOT/'conformance/generators/inputs.py').read_bytes()
 manifest={'schema':'chronus.conformance.corpus.v1','generator_version':'1.0.0','generator_source_sha256':sha(source),'isa_version':'chronus1-1.0','abi_version':'chronus-abi-1','container_version':'chronus-1.1','compiler_version':'chronus-subset-v0.1','assembler_version':'chronus-asm-1','canonicalization_version':'canonical-json-v1','seed_set_digest':seed_digest,'case_count':len(records),'artifact_root':artifact_root,'case_root':case_root,'corpus_sha256':'0'*64,'byte_order':'little','float_representation':'IEEE-754 binary32'}
 manifest['corpus_sha256']=sha(canonical({**manifest,'corpus_sha256':None}));(root/'corpus.json').write_bytes(canonical(manifest));return manifest
