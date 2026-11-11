"""Compare the same bounded product-state MPS on both source paths."""
import hashlib, json, platform, statistics, sys, time
import numpy as np
from chronus.quantum.geometric_polychoron import Cyclotomic5 as C
from chronus.quantum.ring_mps import contract_mps
from chronus.tensor.network import build_network


def main():
    results=[]
    for n in (1,2,4,6,8,10):
        # |0> product state; normalisation in the baseline is therefore a no-op.
        one, zero = C.one(), C.zero()
        sites=[[[[one],[zero]]]]*n
        network, _ = build_network(n, topology='MPS', chi_max=1)
        record={'n_sites':n,'fold_depth':n,'output_count':2**n}
        for name, fn in [('ring',lambda:contract_mps(sites)),('fp_baseline',network.to_statevector)]:
            fn(); samples=[]
            for _ in range(5):
                start=time.perf_counter_ns(); out=fn(); samples.append(time.perf_counter_ns()-start)
            if name=='ring':
                raw=[[v.c0,v.c1,v.c2,v.c3] for v in out]
                expected=[one]+[zero]*(len(out)-1)
                assert list(out)==expected
            else:
                raw=[[float(v.real),float(v.imag)] for v in out]
                assert np.array_equal(out, np.array([1]+[0]*(len(out)-1), dtype=complex))
            record[name]={'times_ns':samples,'median_ns':statistics.median(samples),'output':raw}
        record['max_absolute_difference']=max(abs(complex(rv[0], 0)-complex(*fv)) for rv, fv in zip(record['ring']['output'],record['fp_baseline']['output']))
        results.append(record)
    print(json.dumps({'system':'MPS product state (zero interaction)','input':'n copies of local [1,0], bond dimension 1','baseline':'chronus.tensor.network.build_network and TensorNetwork.to_statevector', 'tolerance':1e-12,'maximum_depth_tested':10,'first_tolerance_exceedance':None,'interpretation':'Neither path exceeded tolerance in the tested range; no depth advantage shown. This is not a many-body application with interactions.','timing_scope':'contraction calls including normalisation in baseline; construction excluded','warmups':1,'repetitions':5,'timer':'perf_counter_ns','python':sys.version,'numpy':np.__version__,'platform':platform.platform(),'source_blob_network':'1ad877573d585e28282bb00b147a084e9635a594','source_blob_types':'2d08a1ce3bf015c2f54f901e95dc28a34f280dbf','results':results},indent=2))


if __name__=='__main__': main()
