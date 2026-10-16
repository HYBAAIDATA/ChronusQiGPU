import numpy as np
import pytest
import sympy as sp
from chronos_one_igpu import manifold as m
from chronos_one_igpu.igpu.exact_geometry import ExactRay


def test_historical_order_exact_replacement_projection_parity():
    rays=m.exact_m32_rays_ordered();assert len(rays)==32 and all(r.is_unit()for r in rays)
    actual=m.build_m32();old=m._classical_m32_positions();assert np.allclose(actual,old,rtol=0,atol=1e-14)
    assert [r.transport()for r in rays]==m.exact_m32_transport()


def test_no_numerical_identity_matching(monkeypatch):
    def denied(*args,**kwargs):raise AssertionError('numeric identity matcher must not execute')
    monkeypatch.setattr(m,'_classical_m32_positions',denied);monkeypatch.setattr(np,'argmax',denied)
    assert len(m.exact_m32_rays_ordered())==32


def test_exact_adjacency_preserves_threshold_contract():
    exact=np.asarray(m.exact_m32_adjacency_ordered());positions=m._classical_m32_positions();reference=(positions@positions.T>=0.70).astype(int);np.fill_diagonal(reference,0)
    assert np.array_equal(exact,reference)and np.array_equal(exact,exact.T)
    obj=m.M32Manifold();assert np.array_equal(obj.adjacency,exact)


def test_uniform_state_exact_and_compatibility_projection():
    obj=m.M32Manifold();state=obj.get_state_exact()
    assert sp.simplify(sum(sp.conjugate(x)*x for x in state))==1
    assert not any(x.has(sp.Float)for x in state)
    assert np.allclose(obj.get_state(),[complex(x)for x in state])


def test_duplicate_ray_mutation_rejected(monkeypatch):
    rays=m._exact_m32_rays();monkeypatch.setattr(m,'_exact_m32_rays',lambda:(rays[0],)*32)
    with pytest.raises(ArithmeticError):m.exact_m32_rays_ordered()


def test_nonunit_ray_mutation_rejected(monkeypatch):
    rays=m._exact_m32_rays();bad=ExactRay(rays[0].numerator,rays[0].denominator_squared*2);monkeypatch.setattr(m,'_exact_m32_rays',lambda:(bad,*rays[1:]))
    with pytest.raises(ArithmeticError):m.exact_m32_rays_ordered()
