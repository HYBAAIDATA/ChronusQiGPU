"""Compile bounded modular proofs; never certify a sketch or failed compilation."""
from pathlib import Path
import os,subprocess,shutil,hashlib,json,sys
root=Path(__file__).resolve().parents[1];source=root/'proofs/lean/Projection.lean';out=root/'validation/v3.10.0-lean.json'
compiler=os.environ.get('LEAN_BIN')or shutil.which('lean')
if not compiler:
 report={'status':'NOT_RUN','reason':'Lean compiler unavailable','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
 out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));sys.exit(2)
version=subprocess.run([compiler,'--version'],capture_output=True,text=True,check=True).stdout.strip()
result=subprocess.run([compiler,str(source)],capture_output=True,text=True,timeout=120)
text=result.stdout+result.stderr
passed=result.returncode==0 and 'sorryAx'not in text and 'error:'not in text and not __import__('re').search(r'\b(sorry|admit|axiom)\b',source.read_text())
report={'status':'PASS'if passed else'FAIL','compiler':version,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'compiler_exit_code':result.returncode,'compiler_output':text,'theorems':['bounded modular Q-step closure','undo(step(p))=p','step(undo(p))=p','unfold(fold(p))=p','fold(unfold(p))=p','fold injectivity','constructive low-coordinate surjection','fiber coordinate uniqueness'],'trusted_axioms':['propext','Quot.sound'],'scope':'generic modular coordinate recurrence and constructive fiber coordinates; not a compiled proof of fast-doubling implementation equivalence, total fiber cardinality, SHA256 uniformity or consensus security','all_T1_T10_proven':False}
out.write_text(json.dumps(report,indent=2)+'\n');(root/'validation/v3.10.0-lean.txt').write_text(text);print(json.dumps({'status':report['status'],'compiler':version,'theorem_groups':len(report['theorems'])}));sys.exit(0 if passed else 1)
