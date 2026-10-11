"""One-command #106 mathematical-intrinsics acceptance."""
from __future__ import annotations
import subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from compiler.intrinsics import INTRINSICS,compile_intrinsic,execute_reference
from conformance.build import build
from conformance.intrinsic_cases import extend
from cross_verification import CorpusStore

def ok(x):print(f'{x:60s} PASS')
def main():
 subprocess.run([sys.executable,'scripts/check_chronus105.py'],cwd=ROOT,check=True);ok('#105 cross-verification authority')
 subprocess.run([sys.executable,'-m','pytest','-q','tests/test_chronus106_intrinsics.py'],cwd=ROOT,check=True);ok('typed exact/approximate intrinsic semantics')
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);base=build(root);extended=extend(root);assert extended['case_count']>base['case_count'];CorpusStore(root,extended['corpus_sha256']);ok('same #104 corpus schemas extended and re-verified')
 assert INTRINSICS=={'FIBONACCI','LUCAS','BINET_EXACT','ZECKENDORF_ENCODE','ZECKENDORF_DECODE','CASSINI_VERIFY','PISOT_SCHEDULE','PHI_WEIGHT'};ok('complete mathematical intrinsic registry')
 print('Chronus #106 mathematical intrinsics gate: PASS');print('INTEL_OPENCL_PHYSICAL: PHYSICAL_EVIDENCE_REQUIRED');print('FOLDED_NATIVE: OPEN');print('CI STATUS: NOT REPORTED')
if __name__=='__main__':main()
