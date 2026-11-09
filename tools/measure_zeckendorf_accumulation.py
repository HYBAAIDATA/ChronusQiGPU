#!/usr/bin/env python3
"""Measure the existing software Zeckendorf reference, not a hardware ALU."""
import argparse, hashlib, json, math, platform, time, types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(); p.add_argument('--source-commit',required=True); p.add_argument('--source-blob',required=True); p.add_argument('--mcp-source-json'); p.add_argument('--output',required=True); args=p.parse_args()
    if args.mcp_source_json:
        raw=json.loads(Path(args.mcp_source_json).read_text())['content'][1]['resource']['text'].encode()
    else: raw=(ROOT/'src/chronus/hw/zeckendorf.py').read_bytes()
    blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    if blob!=args.source_blob: raise ValueError('source blob mismatch')
    m=types.ModuleType('reference_zeckendorf'); exec(compile(raw,'src/chronus/hw/zeckendorf.py','exec'),m.__dict__)
    start=2**53; count=10000; one=m.fold_to_zeckendorf(1); state=m.fold_to_zeckendorf(start)
    t=time.perf_counter_ns()
    for _ in range(count): state=m.add(state,one)
    integer_ns=time.perf_counter_ns()-t; actual=m.unfold(state)
    floating=float(start); t=time.perf_counter_ns()
    for _ in range(count): floating+=1.0
    float_ns=time.perf_counter_ns()-t
    expected=start+count
    try: m.fold_to_zeckendorf(2**80)
    except ValueError as e: boundary={'input':str(2**80),'outcome':'ValueError','message':str(e)}
    else: boundary={'input':str(2**80),'outcome':'accepted'}
    result={'label':'software reference demonstration; not hardware ALU or ring-backed workload', 'source_commit':args.source_commit,'source_blob':blob,
      'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'workload':{'initial':start,'increments':count,'increment':1},
      'expected_integer':expected,'zeckendorf_result':actual,'float_result':floating,'float_error':int(floating)-expected,
      'zeckendorf_elapsed_ns':integer_ns,'float_elapsed_ns':float_ns,
      'zeckendorf_additions_per_second':count*1e9/integer_ns,'float_additions_per_second':count*1e9/float_ns,
      'large_input_boundary':boundary,'python':platform.python_version(),'platform':platform.platform(),
      'timing_scope':'single warm process; includes Python-level loop and implementation overhead; no device timing or inference of hardware bottleneck removal'}
    Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n'); print(json.dumps(result,sort_keys=True))
    if actual!=expected: raise AssertionError('reference integer accumulation mismatch')
if __name__=='__main__': main()
