"""One authoritative #107 production-mining acceptance gate."""
from __future__ import annotations
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from chronus.mla1517.mining.production_integration import ProductionMiningIntegration
from conformance.build import build
from conformance.intrinsic_cases import extend
from cross_verification import CorpusStore

def ok(x):print(f'{x:64s} PASS')
def main():
 subprocess.run([sys.executable,'scripts/check_chronus106.py'],cwd=ROOT,check=True);ok('#100-#106 inherited authority')
 x=ProductionMiningIntegration.from_repository(ROOT);ok('#107 manifest, base SHA and authority boundaries')
 plan=x.plan_evidence(1024,256);assert plan['evidence_sha256'];ok('typed PISOT scheduling evidence in production plan path')
 subprocess.run([sys.executable,'-m','pytest','-q','tests/test_chronus107_production_mining.py'],cwd=ROOT,check=True);ok('deterministic production integration and recovery tests')
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);build(root);manifest=extend(root);CorpusStore(root,manifest['corpus_sha256']);ok('#104 corpus + #106 extension replay')
 evidence={'schema':'chronus107.acceptance-evidence.v1','base_sha':x.manifest['base_sha'],'manifest_sha256':x.manifest_digest,'extended_corpus_sha256':manifest['corpus_sha256'],'inherited_gates':'PASS','focused_tests':'PASS','deterministic_replay':'PASS','physical_opencl':'PHYSICAL_EVIDENCE_REQUIRED','live_pool':'NOT_RUN','ci':'NOT_REPORTED','f64':'UNSUPPORTED','opencl.BINET_EXACT':'UNSUPPORTED','FOLDED_NATIVE':'OPEN','claims':{'performance':False,'profitability':False}}
 data=json.dumps(evidence,sort_keys=True,separators=(',',':')).encode();out=ROOT/'artifacts';out.mkdir(exist_ok=True);(out/'chronus107-evidence.json').write_bytes(data);(out/'chronus107-sha256sums.txt').write_text(hashlib.sha256(data).hexdigest()+'  chronus107-evidence.json\n')
 print('Chronus #107 production mining integration gate: PASS');print('INTEL_OPENCL_PHYSICAL: PHYSICAL_EVIDENCE_REQUIRED');print('LIVE_POOL: NOT_RUN');print('CI STATUS: NOT_REPORTED')
if __name__=='__main__':main()
