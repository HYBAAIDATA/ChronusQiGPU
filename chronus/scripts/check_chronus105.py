"""One-command #105 cross-verification acceptance."""
from __future__ import annotations
import json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from conformance.build import build
from cross_verification import CorpusStore,Float32Policy,IntelOpenCLTranslatedAdapter
EXPECTED='0b4035e138256cfed08ba5d9e1b0058dc8e7c0dbce2e0ccb50039254de4e1712'
def ok(name):print(f'{name:60s} PASS')
def main():
 subprocess.run([sys.executable,'chronus/scripts/check_chronus104.py'],cwd=ROOT,check=True);ok('#104 immutable conformance authority')
 with tempfile.TemporaryDirectory() as td:
  manifest=build(Path(td));assert manifest['corpus_sha256']==EXPECTED;store=CorpusStore(Path(td),EXPECTED);ok('corpus loading and content-address verification')
  adapter=IntelOpenCLTranslatedAdapter();cap=adapter.capabilities();cap.validate();assert not cap.hardware_executed;ok('backend manifest validation and false-hardware rejection')
  cases=list(store.cases());translated=[c for c in cases if adapter.translate(c,store)]
  assert {c['operation'] for c in translated}=={'vector_add','reduce_sum_local','matmul_tiled'};ok('Intel OpenCL software translation hooks')
  assert all(adapter.execute(c,store).status=='PHYSICAL_EVIDENCE_REQUIRED' for c in translated[:3]);ok('physical gate explicit (not counted as PASS)')
 p=Float32Policy();assert p.nan_rule=='both-nan' and p.infinity_rule=='same-sign' and p.signed_zero_rule=='equal';ok('explicit IEEE-754 float32 comparison policy')
 subprocess.run([sys.executable,'-m','pytest','-q','chronus/tests/test_chronus105_cross_verification.py'],cwd=ROOT,check=True);ok('adapter, negative-boundary and deterministic tests')
 print('Chronus #105 cross-verification gate: PASS');print('INTEL_OPENCL_PHYSICAL: PHYSICAL_EVIDENCE_REQUIRED');print('CI STATUS: NOT REPORTED')
if __name__=='__main__':main()
