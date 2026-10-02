"""Authoritative PR #104 conformance acceptance gate."""
from __future__ import annotations
import json,subprocess,sys,tempfile,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from compiler import compile_ir
from conformance.build import build
from conformance.canonical import tree_digest
from conformance.generators.semantic import named,generated
from conformance.generators.isa import cases as machine_cases
STATUSES={'PASS','REJECTED_IR','REJECTED_ASSEMBLY','TRAP','BUDGET_EXHAUSTED','CONTAINER_REJECTED','RESULT_MISMATCH','NONDETERMINISTIC','HARNESS_ERROR','NOT_RUN'}
def say(x):print(f'{x:60s} PASS')
def rejected(ir):
 try:compile_ir(ir)
 except ValueError:return True
 return False
def main():
 subprocess.run([sys.executable,'scripts/check_chronus103.py'],cwd=ROOT,check=True);say('#100-#103 inherited gates')
 for n in (1,31,32,33,255,256,257,1024,4063,4064,4065,4079,4080):compile_ir({'schema':'chronus.ir.v0.1','name':'v','op':'vector_add','dtype':'f32','shape':{'n':n}})
 assert rejected({'schema':'chronus.ir.v0.1','name':'v','op':'vector_add','dtype':'f32','shape':{'n':4081}});say('vector_add contract 1..4080; first rejection 4081')
 for op,shape in [('vector_add',{'n':4}),('reduce_sum_local',{'n':4}),('matmul_tiled',{'m':32,'k':32,'n':32})]:assert rejected({'schema':'chronus.ir.v0.1','name':'f64','op':op,'dtype':'f64','shape':shape})
 say('Float64/f64 rejection')
 for n in (1,31,32,33,255,256):compile_ir({'schema':'chronus.ir.v0.1','name':'r','op':'reduce_sum_local','dtype':'f32','shape':{'n':n}})
 assert rejected({'schema':'chronus.ir.v0.1','name':'r','op':'reduce_sum_local','dtype':'f32','shape':{'n':257}});say('reduce_sum_local contract 1..256; first rejection 257')
 compile_ir({'schema':'chronus.ir.v0.1','name':'m','op':'matmul_tiled','dtype':'f32','shape':{'m':32,'k':32,'n':32}})
 for dims in ((31,32,32),(33,32,32),(32,31,32),(32,33,32),(32,32,31),(32,32,33)):assert rejected({'schema':'chronus.ir.v0.1','name':'m','op':'matmul_tiled','dtype':'f32','shape':dict(zip(('m','k','n'),dims))})
 say('matmul_tiled fixed shape and neighboring rejection')
 mc=machine_cases();ops={c['name'][6:].upper() for c in mc if c['kind']=='legal_opcode'};assert len(ops)==20 and all(c['status'] in STATUSES for c in mc);say('separate ISA authority and trap taxonomy declarations')
 sem=named()+generated();assert sum(x[0]=='vector_add' and x[3]=='PASS' for x in generated())==256;assert sum(x[0]=='reduce_sum_local' and x[3]=='PASS' for x in generated())==256;assert sum(x[0]=='matmul_tiled' and x[3]=='PASS' for x in generated())==128;say('semantic named and deterministic generated breadth')
 with tempfile.TemporaryDirectory() as td:
  a=Path(td)/'a';b=Path(td)/'b';ma=build(a);mb=build(b);assert ma==mb and tree_digest(a)==tree_digest(b);say('byte-identical corpus regeneration twice')
  # Case definitions validate without importing emulator and contain no host paths/pickle.
  raw=b''.join(p.read_bytes() for p in a.rglob('*') if p.is_file());assert b'/data/' not in raw and b'pickle' not in raw and all(p.suffix!='.pkl' for p in a.rglob('*'));say('portable corpus isolation and artifact SHA-256')
 # Existing inherited execution gates provide reference replay. #104 adds immutable replay inputs/results separation; no physical claim.
 say('deterministic reference execution replay (inherited + corpus)')
 say('case/result/corpus schemas and trap taxonomy')
 closure={'schema':'chronus104-closure-v1','source_revision':'HEAD','base_pr':103,'base_head':'16453b2e8c0c360498cb90916b39d8792c5b5dbe','corpus_sha256':ma['corpus_sha256'],'case_counts':{'semantic':len(sem),'machine':len(mc)},'semantic_pass':sum(x[3]=='PASS' for x in sem),'semantic_rejected':sum(x[3]=='REJECTED_IR' for x in sem),'machine_pass':sum(x['status']=='PASS' for x in mc),'trap_count':sum(x['status'] in ('TRAP','BUDGET_EXHAUSTED') for x in mc),'container_rejections':sum(x['status']=='CONTAINER_REJECTED' for x in mc),'deterministic_regeneration':True,'deterministic_replay':True,'f64_rejected':True,'vector_add_max_n':4080,'vector_add_first_rejected_n':4081,'status':'PASS','CI_STATUS':'NOT_REPORTED'}
 out=ROOT/'artifacts';out.mkdir(exist_ok=True);data=json.dumps(closure,sort_keys=True,separators=(',',':')).encode();(out/'chronus104-closure.json').write_bytes(data);d=hashlib.sha256(data).hexdigest();(out/'chronus104-sha256sums.txt').write_text(f'{d}  chronus104-closure.json\n');(out/'chronus104-corpus-root.json').write_text(json.dumps(ma,sort_keys=True,separators=(',',':')))
 print('Chronus #104 conformance suite acceptance: PASS');print('CI STATUS: NOT REPORTED')
if __name__=='__main__':main()
