"""Exact vector scaling against a simple independent polynomial baseline."""
import json, platform, random, statistics, sys, time
from chronus.quantum.geometric_polychoron import Cyclotomic5 as C
from chronus.quantum.ring_state import scale_vector


def direct_product(a, b):
    x = (a.c0,a.c1,a.c2,a.c3); y = (b.c0,b.c1,b.c2,b.c3)
    p = [0]*7
    for i in range(4):
        for j in range(4): p[i+j] += x[i]*y[j]
    # z^5=1, z^6=z, z^4=-(1+z+z²+z³)
    return C(p[0]-p[4]+p[5],p[1]-p[4]+p[6],p[2]-p[4],p[3]-p[4])


def record(v): return [[x.c0,x.c1,x.c2,x.c3] for x in v]


def main():
    rng=random.Random(20261109); results=[]
    for n in (16,128):
        scalar=C(1,-3,2,5); xs=[C(*(rng.randrange(-100,101) for _ in range(4))) for _ in range(n)]
        expected=tuple(direct_product(scalar,x) for x in xs)
        for name,fn in [('ring_state',lambda:scale_vector(scalar,xs)),('independent_polynomial',lambda:tuple(direct_product(scalar,x) for x in xs))]:
            fn(); samples=[]
            for _ in range(7):
                start=time.perf_counter_ns(); output=fn(); samples.append(time.perf_counter_ns()-start)
                if output!=expected: raise AssertionError('exact mismatch')
            results.append({'n':n,'implementation':name,'times_ns':samples,'median_ns':statistics.median(samples),'output_coefficients':record(output),'exact_match':output==expected})
    print(json.dumps({'workload':'explicit exact vector scaling in Z[zeta5]', 'seed':20261109, 'warmups':1, 'repetitions':7, 'timer':'perf_counter_ns','timing_scope':'complete function call, validation in ring_state only; input generation and verification excluded', 'python':sys.version,'platform':platform.platform(),'results':results},indent=2))


if __name__=='__main__': main()
