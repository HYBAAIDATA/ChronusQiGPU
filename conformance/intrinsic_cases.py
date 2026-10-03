"""#106 extension of the #104 corpus; schemas and trap taxonomy stay unchanged."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any,Iterable,Mapping
from compiler.intrinsics import compile_intrinsic,execute_reference
from conformance.canonical import canonical,case_id,sha,tree_digest

def definitions()->Iterable[Mapping[str,Any]]:
 for intrinsic,values,result in (
  ('FIBONACCI',[0,1,2,10,92,93],'u64'),('LUCAS',[0,1,2,10,91,92],'u64'),('BINET_EXACT',[0,1,2,10,92,93],'u64'),('PHI_WEIGHT',[0,1,2,31,255],'f32')):
  key='index' if intrinsic=='PHI_WEIGHT' else 'n'
  for value in values:yield {'schema':'chronus.ir.v0.2','name':f'{intrinsic.lower()}_{value}','op':'intrinsic','intrinsic':intrinsic,'operands':{key:value},'result_type':result,'lowering':'REFERENCE_HOST'}
 for value in (0,1,2,3,2**32,2**63,2**64-1):yield {'schema':'chronus.ir.v0.2','name':f'ze_{value}','op':'intrinsic','intrinsic':'ZECKENDORF_ENCODE','operands':{'value':value},'result_type':'zeckendorf93','lowering':'REFERENCE_HOST'}
 for n in (1,2,10,50,92):
  from aethel.fibonacci import cassini_quadruple
  a,b,c,_=cassini_quadruple(n);yield {'schema':'chronus.ir.v0.2','name':f'cassini_{n}','op':'intrinsic','intrinsic':'CASSINI_VERIFY','operands':{'n':n,'f_prev':a,'f_n':b,'f_next':c},'result_type':'bool','lowering':'REFERENCE_HOST'}
 yield {'schema':'chronus.ir.v0.2','name':'pisot_256','op':'intrinsic','intrinsic':'PISOT_SCHEDULE','operands':{'extent':1024,'maximum_candidates':16,'maximum_work_group_size':256},'result_type':'candidate_set','lowering':'REFERENCE_HOST'}

def extend(root:Path)->Mapping[str,Any]:
 root=Path(root);manifest=json.loads((root/'corpus.json').read_text());source=Path(__file__).read_bytes()
 for ir in definitions():
  plan=compile_intrinsic(ir);expected=canonical(execute_reference(plan));ih=sha(canonical(ir));(root/'artifacts/ir'/ih).write_bytes(canonical(ir));eh=sha(expected);(root/'artifacts/expected'/eh).write_bytes(expected);xh=sha(plan.artifact);(root/'artifacts/binaries'/xh).write_bytes(plan.artifact)
  rec={'schema':'chronus.conformance.case.v1','case_id':'','class':'semantic','operation':ir['intrinsic'],'seed':None,'ir_sha256':ih,'input_sha256':None,'executable_sha256':xh,'expected_sha256':eh,'expected_status':'PASS','expected_trap':None,'limits':{'instruction_budget':10000000,'barrier_budget':4096}};rec['case_id']=case_id(rec);p=root/'cases/semantic'/f'{rec["case_id"][7:]}.json';p.write_bytes(canonical(rec))
 ids=[json.loads(p.read_text())['case_id'] for p in root.glob('cases/*/*.json')];manifest.update(generator_version='1.1.0',generator_source_sha256=sha(source),case_count=len(ids),case_root=sha(canonical(sorted(ids))),artifact_root=tree_digest(root/'artifacts'),corpus_sha256='0'*64);manifest['corpus_sha256']=sha(canonical({**manifest,'corpus_sha256':None}));(root/'corpus.json').write_bytes(canonical(manifest));return manifest
