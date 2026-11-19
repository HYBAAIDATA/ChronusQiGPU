import ast
import itertools
from pathlib import Path
import pytest
from hypothesis import given, settings, strategies as st
from chronus.quantum.geometric_polychoron import Cyclotomic5 as C
from chronus.quantum.ring_state import scale_vector
from chronus.quantum.ring_mps import MAX_BOND, MAX_SITES, contract_mps

pytestmark = pytest.mark.real


def product_site(a,b): return [[[a],[b]]]


def c(n): return C(n,0,0,0)


class TestInvariant:
    def test_bounded_product_states(self):
        for a,b,c0,d in itertools.product(range(-2,3), repeat=4):
            result=contract_mps([product_site(c(a),c(b)),product_site(c(c0),c(d))])
            assert result == tuple(c(x) for x in (a*c0,a*d,b*c0,b*d))


class TestProperty:
    @settings(max_examples=100, deadline=None, derandomize=True)
    @given(st.lists(st.integers(-30,30), min_size=4, max_size=4))
    def test_explicit_two_site_product(self, x):
        a,b,c0,d=map(c,x)
        assert contract_mps([product_site(a,b),product_site(c0,d)]) == (a*c0,a*d,b*c0,b*d)


class TestAdversarial:
    def test_rejections(self):
        with pytest.raises(TypeError): contract_mps(iter([]))
        with pytest.raises(ValueError): contract_mps([[]])
        with pytest.raises(ValueError): contract_mps([[[[C.one()]]]])
        with pytest.raises(ValueError): contract_mps([[[[],[C.one()]]]])
        with pytest.raises(ValueError): contract_mps([[[[C.one()],[C.one(),C.one()]]]])
        with pytest.raises(ValueError): contract_mps([[[[C.one(),C.one()],[C.one(),C.one()]]]])
        with pytest.raises(TypeError): contract_mps([[[[1],[C.one()]]]])
        with pytest.raises(ValueError): contract_mps([[[[C.one()]*(MAX_BOND+1),[C.one()]*(MAX_BOND+1)]]])

    def test_no_inexact_numeric_literals(self):
        tree=ast.parse(Path('src/chronus/quantum/ring_mps.py').read_text())
        assert not any(isinstance(n,ast.Constant) and isinstance(n.value,(float,complex)) for n in ast.walk(tree))


class TestEdge:
    def test_limits_and_empty(self):
        with pytest.raises(ValueError): contract_mps([])
        zero=C.zero(); one=C.one()
        assert len(contract_mps([product_site(one,zero)]*MAX_SITES)) == 2**MAX_SITES
        with pytest.raises(ValueError): contract_mps([product_site(one,zero)]*(MAX_SITES+1))


class TestUnit:
    def test_nontrivial_bond(self):
        first=[[[c(1),c(2)],[c(3),c(4)]]]
        second=[[[c(5)],[c(6)]],[[c(7)],[c(8)]]]
        assert contract_mps([first,second]) == tuple(c(v) for v in (19,22,43,50))


class TestIntegration:
    def test_scaled_output(self):
        sites=[product_site(C.one(), C.zeta()),product_site(C.phi(), C.one())]
        result=contract_mps(sites)
        sites[0]=product_site(C.phi(),C.phi()*C.zeta())
        assert contract_mps(sites)==scale_vector(C.phi(),result)


class TestEndToEnd:
    def test_prepare_contract_and_project(self):
        out=contract_mps([product_site(C.phi(),C.one()),product_site(C.one(),C.phi_inv())])
        assert out == (C.phi(),C.one(),C.one(),C.phi_inv())
        assert tuple(x.to_f257_phi() for x in out)[1] == C.one().to_f257_phi()
