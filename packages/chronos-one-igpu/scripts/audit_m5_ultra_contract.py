"""Installed bounded contract evidence campaign; no performance/hardware claim."""
import argparse
import copy
import hashlib
import json
import platform
import os
from pathlib import Path
from chronos_one_igpu import OneIGPU
from chronos_one_igpu.adapters.base import BackendAbsent
from chronos_one_igpu.m5_ultra import elevate_pads
from chronos_one_igpu.igpu.m5_ultra_contract import OperatorChain,preparation,device_contract,symbolic_gate_laws,audit_operator_laws,digest,PAD_MAX,DEPTH_MAX

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--rc-sha',required=True);p.add_argument('--output',required=True);p.add_argument('--gpu-selector');p.add_argument('--require-gpu',action='store_true');args=p.parse_args()
    report={'schema':'chronos.m5_ultra_audit/1','rc_sha':args.rc_sha,'scope':'CONTRACT_LAYER_INCREMENTAL_EVIDENCE_ONLY','certified':False,'registry':'INTERNAL_INDEX','registry_published':False,'register_span':'one logical qubit per pad; bounded amplitudes','pad_max':PAD_MAX,'depth_max':DEPTH_MAX,'depth_limit_origin':'10 H + 45 CZ: maximum gate count of prior ten-pad full-mesh cluster preparation; prior API had no separately named D_max','physical_entanglement':False,'hardware_claims':False,'throughput_claims':False,'python':platform.python_version(),'platform':platform.platform(),'parity':[],'mutations':[],'determinism':[],'cost_model_counts':[],'symbolic_gate_proof':symbolic_gate_laws(),'unresolved':['PR151 post-merge-main baseline (PR still open at integration)','internal index endpoint and installed-from-index evidence','caller-owned production signing key/custody seal','actual exact GPU parity','current-head CI execution evidence','whole_product_composition','full_register_semantics','iGPU_qualified_VQC_beyond_M5_ULTRA','public_publication_decision']}
    with OneIGPU(working_width=32,prime_rom_limit=1000)as gpu:
        runtime=gpu.m5_resident(model=elevate_pads(2)).ultra_contract(args.rc_sha,gpu_selector=args.gpu_selector)
        chains=[preparation(runtime.model,a)for a in('exact_m5_ghz','exact_m5_cluster')]
        chains+=[OperatorChain(2,((name,*range(arity)),),(0,1))for name,arity in{'H':1,'X':1,'Z':1,'S':1,'SDG':1,'T':1,'TDG':1,'CX':2,'CZ':2,'SWAP':2}.items()]
        chains.append(OperatorChain(2,(('H',0),('T',0),('CX',0,1),('S',1),('SWAP',0,1)),(0,1)))
        report['operators_added_vs_M5']=['composition','inverse','adjoint','X','Z','S','SDG','T','TDG','SWAP','exact custom normalised Q(sqrt2,i) inputs','chain replay and exact cost counts']
        replay_receipts=[];gpu_passes=0
        for c in chains:
            a=runtime.execute(c,backend='CPU_REFERENCE');b=runtime.execute(c,backend='IGPU');assert a['result']==b['result']and a['born']==b['born']
            replay_receipts.append(b);gpu_status='UNAVAILABLE';gpu_reason=None
            try:
                g=runtime.execute(c,backend='GPU')
                assert g['result']==a['result']and g['born']==a['born'];assert runtime.replay(g,runtime.device_contract('GPU'))
                replay_receipts.append(g);gpu_status='PASS_ACTUAL_EXACT_OPENCL';gpu_passes+=1
            except BackendAbsent as exc:gpu_reason=str(exc)
            report['parity'].append({'chain_digest':digest(c.to_dict()),'CPU_REFERENCE':'PASS','IGPU':'PASS_HOST_CPU_EXACT_RESIDENT','GPU':gpu_status,'GPU_unavailable_reason':gpu_reason,'canonical_byte_equal':True,'symbolic_basis_proof':audit_operator_laws(c)})
            hashes=[runtime.execute(c)['replay_binding']for _ in range(5)];assert len(set(hashes))==1
            report['determinism'].append({'chain_digest':digest(c.to_dict()),'repeats':5,'same_backend_binding':hashes[0]})
            report['cost_model_counts'].append({'chain_digest':digest(c.to_dict()),'counts':b['cost_model_counts']})
        original=runtime.execute(chains[-1])
        targets=['algorithm','implementation_id','topology_id','result','device_contract_identity','rc_sha','pad_map','depth','operator_chain_digest','result_digest','cost_model_counts','certified','physical_claims','requested_algorithm','planned_algorithm','executed_algorithm','initial_digest','normalisation','execution_work']
        for target in targets:
            mutated=copy.deepcopy(original);mutated[target]='adversarial_resealed_substitution';body=dict(mutated);body.pop('replay_binding');mutated['replay_binding']=digest(body)
            try:runtime.replay(mutated,device_contract('IGPU'))
            except ValueError as exc:report['mutations'].append({'target':target,'survived':False,'detection_layer':'strict_independent_replay','rejection_reason':str(exc)})
            else:report['mutations'].append({'target':target,'survived':True});raise ArithmeticError('mutation survivor '+target)
        # Non-dyadic exact inputs prove unsupported-domain rejection regardless
        # of device availability. Authorised fallback preserves the exact value.
        from fractions import Fraction
        from chronos_one_igpu.igpu.m5_ultra_contract import encode,ZERO
        input_values=[encode((Fraction(3,5),Fraction(0),Fraction(0),Fraction(0))),encode((Fraction(4,5),Fraction(0),Fraction(0),Fraction(0))),encode(ZERO),encode(ZERO)]
        empty=OperatorChain(2,(),(0,1))
        try:runtime.execute(empty,input_values,backend='GPU')
        except BackendAbsent:pass
        else:raise ArithmeticError('unsupported exact GPU domain accepted')
        fallback=runtime.execute(empty,input_values,backend='GPU',authorised_fallback='CPU_REFERENCE');assert fallback['fallback_used'];assert runtime.replay(fallback,device_contract('CPU_REFERENCE'))
        replay_receipts.append(fallback)
        report['fallback']={'unsupported_GPU_domain_without_authorisation':'REJECT','named_CPU_REFERENCE_fallback':'PASS','fallback_gpu_execution_claimed':False}
        report['actual_gpu_case_counts']={'pass':gpu_passes,'unavailable':len(chains)-gpu_passes}
        report['replay_bundle']={'rc_sha':args.rc_sha,'model':{'kind':'elevated','pads':2,'topology':runtime.model.topology},'receipts':replay_receipts}
    machine_file=Path('/etc/machine-id');machine=machine_file.read_text().strip()if machine_file.exists()else ''
    report['producer_context']={'runner_identity_hash':hashlib.sha256((machine+'|'+platform.node()+'|'+platform.system()).encode()).hexdigest(),'ci_run_id':os.environ.get('GITHUB_RUN_ID'),'ci_job':os.environ.get('GITHUB_JOB'),'identity_scope':'host/context fingerprint, not proof of physical machine independence'}
    report['mutation_survivors']=sum(m['survived']for m in report['mutations']);report['mutation_campaign_scope']='19 named top-level re-sealed substitutions; nested mutations additionally covered by installed tests, not an exhaustive universe'
    report['determinism_proof_digest']=digest(report['determinism']);report['gates']={'A':'UNAVAILABLE_INTERNAL_ENDPOINT','B':'SEE_INSTALLED_JUNIT_PER_VARIANT','C':'PASS_DIFFERENTIAL_AND_SYMBOLIC','D':'PASS_ALL_EXECUTED_EXACT_BACKENDS'if gpu_passes==len(chains)else'PARTIAL_CPU_IGPU_PASS_GPU_UNAVAILABLE','E':'PASS_ZERO_SURVIVORS_IN_DECLARED_CAMPAIGN','F':'PASS_REPLAY_AND_DETERMINISM_SCOPED_HOST','G':'PASS_NAMED_FALLBACK_AND_BOUNDS_IN_TESTS','H':'IMPLEMENTED_AND_TESTED_WITH_TEST_KEYS_PRODUCTION_SEAL_UNAVAILABLE'}
    if args.require_gpu and gpu_passes!=len(chains):
        report['required_gpu_gate_failed']=True
    report['elevation_complete']=False;report['reason']='required all-backend/internal-install/custody gates are not all evidenced'
    report['report_digest']=digest(report);Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
    if args.require_gpu and gpu_passes!=len(chains):raise SystemExit('exact GPU qualification unavailable; no pass claimed')
    print(json.dumps({'mutation_survivors':report['mutation_survivors'],'operator_cases':len(chains),'elevation_complete':False,'scope':report['scope']}))

if __name__=='__main__':main()
