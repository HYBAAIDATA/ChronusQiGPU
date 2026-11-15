#!/usr/bin/env python3
"""Compare a bounded ring MPS expansion with the repository FP MPS path."""
import argparse
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import platform
import time
import numpy as np
from chronus.quantum.geometric_polychoron import Cyclotomic5 as C
from chronus.tensor.exact_mps import contract
from chronus.tensor.network import TensorNetwork
from chronus.tensor.types import Leg, LegDirection, Node, SymmetricTensor


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--source-commit',required=True); parser.add_argument('--output',required=True); args=parser.parse_args()
    a,b=100000001,99999989
    depths=tuple(range(1,14))
    tolerance=Decimal('1e-18')
    rows=[]; detail=None
    for n in depths:
        exact_sites=[[[[C(a,0,0,0)], [C(b,0,0,0)]]]]*n
        t=time.perf_counter_ns(); exact=contract(exact_sites); exact_ns=time.perf_counter_ns()-t
        # Independent direct product reference, not the contraction code.
        expected=[a**(n-i.bit_count())*b**i.bit_count() for i in range(1<<n)]
        if any(x != C(y,0,0,0) for x,y in zip(exact,expected)):
            raise AssertionError('ring output differs from independent integer product')
        tn=TensorNetwork('MPS',1)
        for site in range(n):
            legs=[Leg(10000+site-1,1,direction=LegDirection.IN),Leg(site,2),Leg(10000+site,1)]
            block=np.array([[[a],[b]]],dtype=np.complex128)
            tn.add(Node(id=site,phys_legs=[legs[1]],virt_legs=[legs[0],legs[2]],tensor=SymmetricTensor(blocks={(0,0,0):block},legs=legs)))
        t=time.perf_counter_ns(); fp=tn.to_statevector(); fp_ns=time.perf_counter_ns()-t
        # FP baseline normalizes; compare to 100-digit Decimal normalization of exact integers.
        with localcontext() as ctx:
            ctx.prec=100
            norm=Decimal(sum(x*x for x in expected)).sqrt()
            diffs=[abs(Decimal.from_float(float(x.real))-Decimal(y)/norm) for x,y in zip(fp,expected)]
            max_drift=max(diffs)
        rows.append({'depth':n,'output_dimension':len(expected),'ring_ns':exact_ns,'fp_ns':fp_ns,
                     'ring_mismatches_vs_integer_oracle':0,'max_normalized_fp_absolute_drift_decimal':str(max_drift),
                     'fp_exceeds_tolerance':max_drift>tolerance})
        if n==8:
            detail={'depth':n,'ring_c0_in_lexicographic_order':[str(x) for x in expected],
                    'float_normalized_real_hex':[float(x.real).hex() for x in fp],
                    'float_imag_max':float(max(abs(x.imag) for x in fp))}
    result={'label':'experimental synthetic product-state MPS; no production or speedup claim',
            'literature':'https://doi.org/10.1103/RevModPhys.93.045003',
            'source_commit':args.source_commit,'input':{'physical_coefficients':[a,b],'bond_dimension':1,'depths':list(depths)},
            'comparison':'ring unnormalised exact integer coefficients against direct integer oracle; existing FP path normalises, compared against 100-digit Decimal normalisation of the same integers',
            'normalization_caveat':'Decimal is used only in the measurement oracle; the ring contraction itself does not normalize or use floating point',
            'fp_tolerance_absolute':str(tolerance),'depth_method':'all integer depths from 1 to 13 tested; report first crossing and last tested depth; no extrapolation',
            'rows':rows,'representative_outputs':detail,'python':platform.python_version(),'numpy':np.__version__,
            'benchmark_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    for row in rows: print(json.dumps(row))

if __name__=='__main__': main()
