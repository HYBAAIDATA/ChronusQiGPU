"""Independent installed replay of hash-pinned or signed evidence, no redispatch.

Unsigned CI artifacts establish replay arithmetic, not trusted release signing.
A separate custody directory may require an externally pinned Ed25519 signer.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
from chronos_one_igpu import OneIGPU
from chronos_one_igpu.m5_ultra import elevate_pads,m5_ultra_fabric
from chronos_one_igpu.igpu.m5_contract_custody import verify as verify_custody


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-report',required=True);p.add_argument('--report-sha256',required=True);p.add_argument('--rc-sha',required=True);p.add_argument('--output',required=True);p.add_argument('--custody-dir');p.add_argument('--trusted-key-digest');args=p.parse_args()
    path=Path(args.source_report)
    if not path.is_file()or path.stat().st_size>16*1024*1024:raise ValueError('bounded replay bundle')
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=args.report_sha256:raise ValueError('replay source artifact hash mismatch')
    source=json.loads(data);bundle=source['replay_bundle']
    if args.custody_dir:
        if not args.trusted_key_digest:raise ValueError('externally pinned signing identity required')
        signed=verify_custody(args.custody_dir,args.trusted_key_digest)
        if signed.get('report_sha256')!=args.report_sha256 or signed.get('rc_sha')!=args.rc_sha:raise ValueError('signed replay source binding mismatch')
    elif args.trusted_key_digest:raise ValueError('signing identity without custody proof')
    if bundle['rc_sha']!=args.rc_sha or source['rc_sha']!=args.rc_sha:raise ValueError('replay revision mismatch')
    receipts=bundle['receipts'];model=bundle['model']
    if not isinstance(receipts,list)or not 1<=len(receipts)<=256 or set(model)!={'kind','pads','topology'}or model['kind']not in('canonical','elevated'):raise ValueError('bounded replay model/receipt contract')
    actual=m5_ultra_fabric(model['topology'])if model['kind']=='canonical'else elevate_pads(model['pads'],topology=model['topology'])
    if actual.n_pads!=model['pads']:raise ValueError('replay model pad identity')
    results=[]
    with OneIGPU(working_width=32,prime_rom_limit=1000)as gpu:
        r=gpu.m5_resident(model=actual).ultra_contract(args.rc_sha)
        for receipt in receipts:
            assert r.replay(receipt,receipt['device_contract_identity'])
            results.append({'binding':receipt['replay_binding'],'executed_backend':receipt['executed_backend'],'pass':True})
    machine_path=Path('/etc/machine-id');machine=machine_path.read_text().strip()if machine_path.exists()else ''
    identity=hashlib.sha256((machine+'|'+platform.node()+'|'+platform.system()).encode()).hexdigest();producer=source.get('producer_context',{})
    report={'schema':'chronos.independent_evidence_replay/1','rc_sha':args.rc_sha,'source_report_sha256':args.report_sha256,'replayed_receipts':results,'consumer_context':{'runner_identity_hash':identity,'ci_run_id':os.environ.get('GITHUB_RUN_ID'),'ci_job':os.environ.get('GITHUB_JOB')},'producer_context':producer,'distinct_runner_context_observed':bool(producer.get('runner_identity_hash')and producer['runner_identity_hash']!=identity),'physical_machine_independence_claimed':False,'trusted_release_signature_verified':bool(args.custody_dir),'hardware_redispatched':False,'certified':False,'registry_published':False}
    Path(args.output).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'replayed':len(results),'hardware_redispatched':False,'certified':False}))

if __name__=='__main__':main()
