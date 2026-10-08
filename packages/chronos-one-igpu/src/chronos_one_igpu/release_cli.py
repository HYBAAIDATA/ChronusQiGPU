"""Operator-facing standalone release checks and exact-family CLI."""
import argparse,json,platform,hashlib
from importlib import metadata
from importlib.resources import files
from pathlib import Path

def doctor():
    from . import OneIGPU,FamilyCertificate
    from .paradigm import run_triad
    with OneIGPU(working_width=32,prime_rom_limit=1000)as gpu:
        gpu.dispatch([10,12,15,18,20]).verify();certificate=gpu.family_certificate([10,12,15]);FamilyCertificate.verify(certificate)
        inventory=gpu.compose()
    from .igpu import PreparedSHA256d
    from .golden_quantum import AdvancedMathematicalOracles as Oracle
    mining=PreparedSHA256d();checks={'exact_core':True,'family_composition':True,'paradigm':run_triad().passed,'asic_like_sha256d':mining.execute_sha256d(bytes(76),[0,1])==tuple(Oracle.nonce_digest(bytes(76),n)for n in[0,1])}
    from .pythi_native import compute_receipt,verify_receipt
    from .igpu.structured_solver import StructuredHamiltonian
    import numpy as np
    native_receipt=compute_receipt(b'chronos-doctor');checks['native_protocol']=verify_receipt(native_receipt,b'chronos-doctor')
    operator=StructuredHamiltonian([.5]*4,1.618);checks['structured_operator_exact']=operator.matvec_exact([1]*4)==[(sum(row),0)for row in operator.dense_exact()]
    for name in('lucas256.cl','sha256d.cl','structured_matvec.cl','hendrix600.cl'):checks[name]=bool(files('chronos_one_igpu').joinpath('igpu/kernels/'+name).read_bytes())
    return {'schema':'chronos_release_doctor_v1','python':platform.python_version(),'version':metadata.version('hyba-chronos-one-igpu'),'checks':checks,'inventory':inventory,'mining_backend':mining.capability(),'passed':all(checks.values()),'scope':'installed-package diagnostics, not production certification'}

def main():
    parser=argparse.ArgumentParser(prog='chronos-igpu',description='Chronos standalone core and mathematical extensions')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor');sub.add_parser('version')
    m5=sub.add_parser('m5-info');m5.add_argument('--virtual-units',type=int,default=800);m5.add_argument('--bind',choices=['native','auto','metal','opencl'],default='native')
    target=sub.add_parser('qualify-target');target.add_argument('--device-selector');target.add_argument('--runs',type=int,default=3);target.add_argument('--nonce-budget',type=int,default=4096);target.add_argument('--output',default='target-qualification.json')
    native=sub.add_parser('native-compute');native.add_argument('header_hex');native.add_argument('--chain-id',default='local-pythi-v1');native.add_argument('--epoch',type=int,default=1)
    q=sub.add_parser('m5-quantum');q.add_argument('--state',choices=['ghz','cluster'],required=True);q.add_argument('--pads',choices=[4,10],type=int,default=4);q.add_argument('--topology',choices=['chain','ring','full_mesh','mesh'],default='chain')
    sub.add_parser('feature-info')
    feature=sub.add_parser('feature-run');feature.add_argument('task_file');feature.add_argument('--profile-file');feature.add_argument('--db-path');feature.add_argument('--checkpoint',action='store_true')
    sub.add_parser('native-security-gate')
    projection=sub.add_parser('projection-analysis');projection.add_argument('--rung-bits',type=int,default=8)
    resident=sub.add_parser('resident-info');resident.add_argument('--virtual-units',type=int,default=8000);resident.add_argument('--bind',choices=['opencl','metal'])
    artifact=sub.add_parser('verify-artifact');artifact.add_argument('path');artifact.add_argument('--sha256',required=True)
    family=sub.add_parser('family');family.add_argument('indices',nargs='+',type=int)
    verify=sub.add_parser('verify-family');verify.add_argument('certificate')
    args=parser.parse_args()
    if args.command=='doctor':result=doctor()
    elif args.command=='m5-info':
        from . import OneIGPU
        from .igpu.resident import ResidentConfig
        with OneIGPU()as gpu:result=gpu.m5_resident(ResidentConfig(host_binding=args.bind,virtual_units=args.virtual_units)).manifest()
    elif args.command=='version':result={'version':metadata.version('hyba-chronos-one-igpu')}
    elif args.command=='qualify-target':
        from .qualification import qualify_target
        result=qualify_target(args.device_selector,args.runs,args.nonce_budget);Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    elif args.command=='native-compute':
        from .pythi_native import NativePolicy
        from . import OneIGPU
        with OneIGPU()as gpu:result=gpu.compute_pythi(bytes.fromhex(args.header_hex),NativePolicy(chain_id=args.chain_id,epoch=args.epoch))
    elif args.command=='projection-analysis':
        from .projection_analysis import projection_contract
        result=projection_contract(args.rung_bits)
    elif args.command=='resident-info':
        from . import OneIGPU
        from .igpu.resident import ResidentConfig
        with OneIGPU()as gpu:
            if args.bind:gpu.bind_host_gpu(args.bind)
            result=gpu.resident(ResidentConfig(virtual_units=args.virtual_units)).manifest()
    elif args.command=='m5-quantum':
        from . import OneIGPU
        from .m5_ultra import m5_ultra_fabric,elevate_pads
        model=m5_ultra_fabric(args.topology)if args.pads==4 else elevate_pads(10,topology=args.topology)
        with OneIGPU()as gpu:result=gpu.m5_resident(model=model).execute_quantum('exact_m5_'+args.state)
    elif args.command in('feature-info','feature-run'):
        from . import OneIGPU
        from .igpu.feature_profile import FeatureProfile
        profile=None
        if args.command=='feature-run'and args.profile_file:
            p=Path(args.profile_file)
            if p.stat().st_size>65536:parser.error('bounded feature profile required')
            profile=FeatureProfile.from_dict(json.loads(p.read_text()))
        with OneIGPU(db_path=None if args.command=='feature-info'else args.db_path)as gpu:
            with gpu.feature_runtime(profile)as runtime:
                if args.command=='feature-info':result=runtime.manifest()
                else:
                    p=Path(args.task_file)
                    if p.stat().st_size>4*1024*1024:parser.error('bounded feature task required')
                    result=runtime.execute(json.loads(p.read_text()))
                    if args.checkpoint:result={'receipt':result,'object_id':runtime.checkpoint(result)}
    elif args.command=='native-security-gate':
        from .pythi_native import security_gate
        result=security_gate()
    elif args.command=='verify-artifact':
        path=Path(args.path)
        if not path.is_file()or path.stat().st_size>500*1024*1024:parser.error('bounded artifact file required')
        h=hashlib.sha256()
        with path.open('rb')as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
        result={'sha256':h.hexdigest(),'matches':h.hexdigest()==args.sha256.lower()}
        if not result['matches']:print(json.dumps(result));raise SystemExit(1)
    elif args.command=='family':
        from .family_algebra import FamilyCertificate
        result=FamilyCertificate.create(args.indices)
    else:
        from .family_algebra import FamilyCertificate
        path=Path(args.certificate)
        if path.stat().st_size>4*1024*1024:parser.error('certificate file quota exceeded')
        result={'verified':FamilyCertificate.verify(json.loads(path.read_text()))}
    print(json.dumps(result,indent=2))
    if args.command=='doctor'and not result['passed']:raise SystemExit(1)
    if args.command=='qualify-target'and not result['hardware_measured']:raise SystemExit(2)
if __name__=='__main__':main()
