"""Reproducible bounded standalone/core/overlay benchmark, including setup costs."""
import argparse,hashlib,json,random,statistics,tempfile,time,platform,shutil
from pathlib import Path
from chronos import OneIGPU
from chronos.igpu import ExactFoldState,GeneticPlanner,WitnessCache,verify_evidence
from chronos.igpu.geometry11d import fold_11d,unfold_11d,zeckendorf_certificate,restore_certificate
from chronos.igpu.scaling_validation import scaling_report
from chronos.golden_quantum import AdvancedMathematicalOracles as Oracle
from chronos.paradigm import nonce_walk,ScheduleName,run_triad
# Bitcoin genesis block header: canonical 80-byte public test vector, nonce 2083236893.
GENESIS=bytes.fromhex('01000000'+'00'*32+'3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a'+'29ab5f49'+'ffff001d'+'1dac2b7c')

def run(size=256,runs=5):
    if not 1<=size<=4096 or not 3<=runs<=30:raise ValueError('benchmark quota')
    expected='000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f'
    assert Oracle.nonce_digest(GENESIS[:76],2083236893)[::-1].hex()==expected
    rows=[];samples=[];names=['sequential','golden_stride','lucas_residue','folded_witness']
    # Fixed real block prefix, public protocol target. Zero target forces full equal work.
    for repeat in range(runs):
        rng=random.Random(20261007+repeat);shuffled=names[:];rng.shuffle(shuffled)
        for name in shuffled:
            for corpus,target in [('genesis_protocol',0x00000000FFFF0000000000000000000000000000000000000000000000000000),('no_success_control',0)]:
                start_nonce=2083236893-size//2;started=time.perf_counter()
                base=range(start_nonce,start_nonce+size)
                if name=='folded_witness':
                    order0=list(nonce_walk(size,ScheduleName.GOLDEN_STRIDE,start_nonce));fold=ExactFoldState.fold(order0);fold.verify()
                    order=(int(fold.unfold_partial([i])[0])for i in range(size))
                else:order=nonce_walk(size,ScheduleName(name),start_nonce)
                count=0;hits=[]
                for nonce in order:
                    digest=Oracle.nonce_digest(GENESIS[:76],nonce);count+=1
                    if Oracle.accepts(digest,target):hits.append(nonce)
                elapsed=time.perf_counter()-started
                assert count==size
                # Independent contiguous hashlib path checks hit list, not the scheduler.
                independent=[n for n in base if int.from_bytes(hashlib.sha256(hashlib.sha256(GENESIS[:76]+n.to_bytes(4,'little')).digest()).digest(),'little')<=target]
                assert sorted(hits)==independent
                samples.append({'repeat':repeat,'schedule':name,'corpus':corpus,'completed_sha256d':count,'elapsed_seconds':elapsed,'hashrate':count/elapsed,'valid_nonces':hits,'setup_and_partial_unfold_in_timing':True})
    for name in names:
        ss=[s for s in samples if s['schedule']==name]
        total=sum(s['completed_sha256d']for s in ss);secs=sum(s['elapsed_seconds']for s in ss)
        rows.append({'schedule':name,'completed_sha256d':total,'elapsed_seconds':secs,'aggregate_hashrate':total/secs,'median_hashrate':statistics.median(s['hashrate']for s in ss),'valid_candidates':sum(len(s['valid_nonces'])for s in ss)})
    baseline=rows[0]['aggregate_hashrate']
    gpu=OneIGPU(evidence_key=bytes(range(32)))
    v=[(i-5)/10 for i in range(11)];start=time.perf_counter()
    for _ in range(1000):folded=fold_11d(v)
    folding_duration=time.perf_counter()-start;certificate=zeckendorf_certificate(v);assert restore_certificate(certificate)==tuple(v);assert max(abs(a-b)for a,b in zip(v,unfold_11d(folded)))<1e-12
    plan=gpu.scaled_plan(size,15);gpu.dispatch([10,12,15,18,20]);trusted_head=gpu.golden.events[-1]['digest'];verify_evidence(gpu.golden.events,bytes(range(32)),trusted_head)
    with tempfile.TemporaryDirectory()as d:
        cache=WitnessCache(d);w=cache.execute_permutation(10000,[('X',0),('CNOT',0,9999),('SWAP',0,1)]);assert cache.replay_execution(w['execution_receipt']);capacity=cache.capacity();cache_bytes=cache.usage()-cache.image_bytes;cache.close()
    genetic=GeneticPlanner(seed=7);candidate=genetic.propose();observation_results=[]
    for s in samples[:3]:observation_results.append(genetic.observe(candidate,s['completed_sha256d'],s['elapsed_seconds']))
    physical={'status':'NOT_RUN','reason':'No executable physical OpenCL adapter detected'}
    with OneIGPU(mode='host_gpu_overlay')as overlay:
        if overlay.fabric.overlay is None:physical['reason']=overlay.compose()['overlay_unavailable_reason']
        else:
            started=time.perf_counter();nonces=list(range(size));actual=overlay.fabric.overlay.execute_sha256d(GENESIS[:76],nonces)
            assert list(actual)==[Oracle.nonce_digest(GENESIS[:76],n)for n in nonces]
            physical={'status':'PASS','receipt':overlay.fabric.overlay.last_receipt,'wall_seconds':time.perf_counter()-started,'items':size}
    total=sum(s['completed_sha256d']for s in samples);secs=sum(s['elapsed_seconds']for s in samples)
    report=scaling_report(image_bytes=None,cache_bytes=cache_bytes,completed_hashes=total,elapsed_seconds=secs,attested=True,replayed=True,trusted_head_verified=True,genetic_observations=3,exact_valid=True,native_available=True,overlay_available=physical['status']=='PASS',pipeline_available=True)
    gpu.close()
    return {'schema':'chronos_elevation_benchmark_v1','scope':'One host, finite public genesis-block window, equal completed hashes per schedule; not pool or network throughput','environment':{'python':platform.python_version(),'platform':platform.platform(),'docker_available':bool(shutil.which('docker'))},'corpus':{'genesis_header_hex':GENESIS.hex(),'known_hash':expected,'size':size,'runs':runs,'seed':20261007,'target_controls':['genesis_protocol','zero_no_success']},'samples':samples,'summary':rows,'baseline':'sequential','negative_results':[r['schedule']for r in rows[1:]if r['aggregate_hashrate']<=baseline],'folding':{'operations':1000,'elapsed_seconds':folding_duration,'measured_folds_per_second':1000/folding_duration,'backend':'cpu_reference','certificate_roundtrip':True,'norm_error_bound':1e-12},'cache':capacity,'lucas_plan':plan.manifest(),'genetic_observation_results':observation_results,'physical_opencl':physical,'scaling':report,'paradigm':run_triad().to_dict(),'claims':{'folded_predictive_advantage_demonstrated':False,'represented_dimension_as_hashes':False,'pool_accepted_shares':None,'power_measured':False,'docker_image_size_measured':False}}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--size',type=int,default=256);p.add_argument('--runs',type=int,default=5);p.add_argument('--output',default='benchmarks/elevation-results.json');a=p.parse_args();result=run(a.size,a.runs);Path(a.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'output':a.output,'sha256d_evaluations':result['scaling']['completed_sha256d_hashes'],'physical_opencl':result['physical_opencl'],'paradigm_passed':result['paradigm']['passed']}))
