"""Exact-rank probe of SO(6) action on 3-forms; not invariant enumeration."""
from fractions import Fraction
from itertools import combinations
import random

TRIPLES=list(combinations(range(6),3)); PAIRS=list(combinations(range(6),2))

def h(t, i,j,k):
    x=[i,j,k]
    if len(set(x))<3: return 0
    inversions=sum(x[a]>x[b] for a in range(3) for b in range(a+1,3))
    return (-1 if inversions%2 else 1)*t[tuple(sorted(x))]

def action(t,p,q,i,j,k):
    def delta(row, component):
        return (h(t,q,*component) if row==p else -h(t,p,*component) if row==q else 0)
    return delta(i,(j,k))+delta(j,(k,i))+delta(k,(i,j))

def rank(matrix):
    a=[[Fraction(x) for x in row] for row in matrix]; piv=0
    for col in range(len(a[0])):
        row=next((r for r in range(piv,len(a)) if a[r][col]), None)
        if row is None: continue
        a[piv],a[row]=a[row],a[piv]; v=a[piv][col]; a[piv]=[z/v for z in a[piv]]
        for r in range(piv+1,len(a)):
            v=a[r][col]
            if v: a[r]=[x-v*y for x,y in zip(a[r],a[piv])]
        piv+=1
        if piv==len(a): break
    return piv

def run():
    rng=random.Random(20261109)
    print('scope: exact rank of 20-by-15 infinitesimal so(6) orbit matrix')
    print('not a contraction-enumeration algorithm; not a five-invariant discovery result')
    for n in range(5):
        t={k:rng.randint(-3,3) for k in TRIPLES}
        matrix=[[action(t,p,q,*ijk) for p,q in PAIRS] for ijk in TRIPLES]
        r=rank(matrix)
        print(f'sample={n} coefficients={[t[k] for k in TRIPLES]} orbit_rank={r} local_codimension={20-r}')
    t={k:0 for k in TRIPLES}
    print('zero_form_rank:',rank([[action(t,p,q,*ijk) for p,q in PAIRS] for ijk in TRIPLES]))
if __name__ == '__main__': run()
