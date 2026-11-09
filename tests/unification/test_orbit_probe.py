import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('probe',Path(__file__).resolve().parents[2]/'scripts/unification/threeform_orbit_probe.py')
p=importlib.util.module_from_spec(spec); spec.loader.exec_module(p)

def test_antisymmetry_and_repeated_indices():
    t={k:0 for k in p.TRIPLES}; t[(0,1,2)] = 4
    assert p.h(t,0,1,2)==4 and p.h(t,1,0,2)==-4 and p.h(t,0,0,2)==0

def test_exact_rank_and_zero():
    assert p.rank([[1,2],[2,4]])==1
    assert p.rank([[1,0],[0,1]])==2
    assert p.rank([[0,0],[0,0]])==0

def test_sampled_so6_orbit_rank():
    t=dict(zip(p.TRIPLES,[-2,-3,0,-1,1,-2,0,-1,-2,-3,3,0,-3,-2,0,-2,-1,3,-2,-1]))
    assert p.rank([[p.action(t,a,b,*ijk) for a,b in p.PAIRS] for ijk in p.TRIPLES]) == 15
