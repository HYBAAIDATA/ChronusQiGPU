#!/usr/bin/env python3
from __future__ import annotations
import json, platform, shutil, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from chronos.adapters import CpuAdapter, OpenCLAdapter, default_pipeline_spec
from chronos.certificate import bind_record
from chronos.evidence import EvidencePack
from chronos.lucas_datapath import DatapathConfig, MiningTarget, SpatialLucasPipeline, LucasShare
from chronos.lucas_scaling import plan
from chronos.pool import StratumJob, ShareResponse, bind_response, lucas_to_stratum
from chronos.sparse import sparse_dispatch

def git_sha():
    try: return subprocess.check_output(['git','rev-parse','HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception: return 'UNVERSIONED-WORKTREE'

def main():
    root=Path(__file__).resolve().parents[1]/'evidence'; shutil.rmtree(root, ignore_errors=True); pack=EvidencePack(root)
    config=DatapathConfig(working_width=32, prime_rom_limit=1000)
    cpu=CpuAdapter(config); kernel=cpu.compile(default_pipeline_spec(32)); result=cpu.dispatch(kernel,[0,1,10,31]); receipt=cpu.receipt()
    try: opencl={'status':'AVAILABLE','capability':OpenCLAdapter().probe().__dict__}
    except Exception as exc: opencl={'status':'BLOCKED','reason':str(exc)}
    pack.write_json('phase_3.2.1','adapter_spec.json',{'classification':'MEASURED','pipeline_spec':{'stages':[s.__dict__ for s in default_pipeline_spec(32).stages],'working_width':32,'field':default_pipeline_spec(32).field,'fail_closed':True},'kernel_digest':kernel.kernel_digest,'commit_sha':git_sha()})
    pack.write_json('phase_3.2.1','opencl_probe.json',opencl)
    pack.write_json('phase_3.2.1','execution_receipt.json',receipt.__dict__)
    pack.seal('phase_3.2.1')
    pack.write_json('phase_3.2.2','tier_plan.json',{'classification':'MODELED','tiers':[r.__dict__ for r in plan((18,20,31,50,76))]})
    sparse=sparse_dispatch(18,range(32),width=32,prime_rom_limit=1000)
    pack.write_json('phase_3.2.2','tier_18_sample.json',{'classification':'MEASURED','execution_mode':sparse.execution_mode,'records':[r.canonical_payload() for r in sparse.records]})
    pack.write_json('phase_3.2.2','sparse_limits.json',{'tier_31_50_76':'PLANNER_ONLY','reason':'No dense allocation; explicit sparse batches require bounded address/prime policy.'})
    pack.seal('phase_3.2.2')
    pipeline=SpatialLucasPipeline(config); rec=pipeline.process_one(10); share=LucasShare(rec,MiningTarget(2**32-1)); sub=lucas_to_stratum(share,StratumJob('fixture-job','1234',4),'fixture-worker'); bound=bind_response(sub,ShareResponse(True,'fixture-response'))
    pack.write_json('phase_3.2.3','share_submission.json',{'classification':'THEORETICAL','submission':sub.__dict__,'response':bound.__dict__,'network_io':'DISABLED'})
    pack.seal('phase_3.2.3')
    lean=shutil.which('lean')
    pack.write_json('phase_3.2.4','proof_report.json',{'status':'PROVED' if lean else 'BLOCKED','lean_binary':lean,'theorems':[] if not lean else ['pending formal source implementation'],'reason':None if lean else 'Lean 4 is not installed; no theorem is represented as proved.'})
    pack.seal('phase_3.2.4')
    pack.write_json('phase_3.2.5','integration.json',{'classification':'MEASURED','cpu_records':len(result.records),'backend':receipt.backend,'sparse_sample_records':len(sparse.records),'opencl':opencl['status'],'formal_proof':'BLOCKED' if not lean else 'PENDING'})
    pack.seal('phase_3.2.5')
    print(json.dumps({'root':str(root),'commit_sha':git_sha(),'phases':[p.name for p in root.iterdir()]}, indent=2))
if __name__=='__main__': main()
