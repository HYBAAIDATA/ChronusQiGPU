"""Executed equal-work exact kernel control; not AI training or M5 hardware.

Public Bitcoin genesis header bytes supply an 8x10 input. Exact Fibonacci
weights form a diagonal control. Prepared vs dense execute the same operation;
whole feature-runtime times are reported separately, never divided by kernel
measurements or represented as mining/quantum/competitor throughput.
"""
import argparse
import hashlib
import json
import platform
import random
from pathlib import Path
import time
from chronos_one_igpu import OneIGPU
from chronos_one_igpu.lucas_engine import fibonacci_pair
from chronos_one_igpu.igpu.exact_neural import PreparedNetwork,encode
from chronos_one_igpu.igpu.feature_profile import FeatureProfile


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',default='generic-feature-benchmark.json');ap.add_argument('--runs',type=int,default=30);args=ap.parse_args()
    if not 5<=args.runs<=1000:ap.error('bounded sample count required')
    header=bytes.fromhex('01000000'+'00'*32+'3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a'+'29ab5f49ffff001d1dac2b7c')
    x=[list(header[start:start+10])for start in range(0,80,10)]
    weights=[[fibonacci_pair(i+1)[0]if i==j else 0 for j in range(10)]for i in range(10)]
    layers=[{'weights':weights,'bias':[0]*10,'activation':'identity'}]
    start=time.perf_counter_ns();prepared=PreparedNetwork(layers);prepare_ns=time.perf_counter_ns()-start
    expected=encode(prepared.reference(x));prepared.execute(x)
    samples=[];rng=random.Random(20261008)
    for repeat in range(args.runs):
        paths=['prepared','dense'];rng.shuffle(paths)
        for path in paths:
            start=time.perf_counter_ns()
            if path=='prepared':output,work=prepared.execute(x)
            else:output=prepared.reference(x)
            elapsed=time.perf_counter_ns()-start
            if encode(output)!=expected:raise ArithmeticError('equal-work exact output mismatch')
            samples.append({'repeat':repeat,'path':path,'elapsed_ns':elapsed,'outputs':80})
    totals={path:sum(s['elapsed_ns']for s in samples if s['path']==path)for path in('prepared','dense')}
    task={'kind':'neural','input':x,'layers':layers}
    whole=[]
    with OneIGPU()as gpu:
        with gpu.feature_runtime(FeatureProfile((2,2),((0,1),)))as runtime:
            for repeat in range(args.runs):
                start=time.perf_counter_ns();receipt=runtime.execute(task);elapsed=time.perf_counter_ns()-start
                if receipt['output']!=expected:raise ArithmeticError('whole-runtime output mismatch')
                whole.append({'repeat':repeat,'elapsed_ns':elapsed,'prepared_program_cache_hit':receipt['prepared_program_cache_hit']})
    report={'schema':'chronos.generic_feature_benchmark/1','python':platform.python_version(),'platform':platform.platform(),
            'source_module_sha256':hashlib.sha256(Path(__import__('chronos_one_igpu.igpu.exact_neural',fromlist=['x']).__file__).read_bytes()).hexdigest(),
            'fixture':'public Bitcoin genesis header bytes; deterministic Fibonacci diagonal exact transform, not a trained neural model',
            'fixture_sha256':hashlib.sha256(header).hexdigest(),'runs_per_path':args.runs,'cold_program_prepare_ns':prepare_ns,
            'scope':'prepared exact neural kernel vs independent full dense field kernel, verification outside timed kernel; not whole product/hardware/mining',
            'equal_exact_outputs':True,'samples':samples,'aggregate_kernel_elapsed_ns':totals,
            'measured_prepared_vs_dense_kernel_ratio':totals['dense']/totals['prepared'],
            'prepared_scalar_products':work['scalar_products'],'dense_scalar_products':work['dense_scalar_products'],
            'whole_runtime_samples_separate':whole,'sha256d_evaluations':0,'physical_M5_execution':False,'competitor_comparison':False}
    Path(args.output).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k]for k in('runs_per_path','measured_prepared_vs_dense_kernel_ratio','prepared_scalar_products','dense_scalar_products','scope')}))


if __name__=='__main__':main()
