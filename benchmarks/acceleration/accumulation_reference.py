"""Synthetic exact vs binary64 addition with fully specified starting value."""
import json,platform,sys,time
from chronus.hw.zeckendorf import fold_to_zeckendorf,unfold,add
from chronus.quantum.geometric_polychoron import Cyclotomic5 as C


def zsum():
    x=fold_to_zeckendorf(2**53); one=fold_to_zeckendorf(1)
    for _ in range(100): x=add(x,one)
    return unfold(x)


def rsum():
    x=C(2**53,0,0,0); one=C.one()
    for _ in range(100): x=x+one
    return x.c0


def fsum():
    x=float(2**53)
    for _ in range(100): x=x+1.0
    return x


def main():
    rows=[]; expected=2**53+100
    for name,fn in [('zeckendorf_reference',zsum),('ring',rsum),('binary64_baseline',fsum)]:
        fn(); samples=[]
        for _ in range(7):
            start=time.perf_counter_ns(); value=fn(); samples.append(time.perf_counter_ns()-start)
        rows.append({'implementation':name,'duration_ns':samples,'output':value,'error_from_exact_integer':int(value)-expected,'additions_per_sample':100})
    print(json.dumps({'workload':'start 2**53 and add one 100 times','expected_integer':expected,'source_blob_zeckendorf':'1687afd68d841bb9ededc675d4fb6e5afd63e6fe','warmups':1,'samples':7,'timer':'perf_counter_ns','timing_scope':'function call; includes construction, excludes post-check; reference not actual ALU throughput','python':sys.version,'platform':platform.platform(),'results':rows},indent=2))


if __name__=='__main__':main()
