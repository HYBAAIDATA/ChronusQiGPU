from fractions import Fraction
import sympy as sp
import pytest
from chronus.virtual_igpu.geometric import execute_modular, verify_modular


def test_cassini_gradient_decreases_declared_potential_and_singularities_refuse():
    request = {
        "op": "cassini_step",
        "position": [2, 1],
        "centers": [[-1, 0], [1, 0]],
        "step": [1, 10],
        "momentum": [0, 0],
        "mode": "gradient",
    }
    out = execute_modular(request)
    assert Fraction(*out["potential_product_after"]) < Fraction(*out["potential_product_before"])
    assert verify_modular(request, out) == []
    request["position"] = [1, 0]
    with pytest.raises(ValueError, match="singular"):
        execute_modular(request)


def test_cassini_symplectic_map_has_canonical_jacobian():
    x, y, px, py, h = sp.symbols("x y px py h", real=True)
    potential = sp.log(((x - 1) ** 2 + y * y) * ((x + 1) ** 2 + y * y)) / 2
    p = sp.Matrix([px - h * sp.diff(potential, x), py - h * sp.diff(potential, y)])
    mapping = sp.Matrix([x + h * p[0], y + h * p[1], *p])
    jacobian = mapping.jacobian([x, y, px, py])
    omega = sp.Matrix([[0, 0, 1, 0], [0, 0, 0, 1], [-1, 0, 0, 0], [0, -1, 0, 0]])
    assert (jacobian.T * omega * jacobian - omega).applyfunc(sp.simplify) == sp.zeros(4)
    request = {
        "op": "cassini_step",
        "position": [2, 1],
        "centers": [[-1, 0], [1, 0]],
        "step": [1, 10],
        "momentum": [1, 2],
        "mode": "hamiltonian",
    }
    out = execute_modular(request)
    exact = mapping.subs({x: 2, y: 1, px: 1, py: 2, h: sp.Rational(1, 10)})
    assert [Fraction(*v) for v in out["position"] + out["momentum"]] == [Fraction(v) for v in exact]


def test_modular_geodesic_unit_metric_and_jacobi_equation():
    t = sp.Symbol("t", real=True)
    v = 2 * sp.exp(t)
    x, y = (1 + 2 * v * v) / (1 + v * v), v / (1 + v * v)  # [2,1,1,1], determinant +1
    assert sp.simplify((sp.diff(x, t) ** 2 + sp.diff(y, t) ** 2) / y**2 - 1) == 0
    j = 3 * sp.cosh(t) + 2 * sp.sinh(t)
    assert sp.simplify(sp.diff(j, t, 2) - j) == 0
    request = {"op": "geodesic", "matrix": [2, 1, 1, 1], "height": 2, "time": 0, "jacobi": [3, 2]}
    out = execute_modular(request)
    assert out["hyperbolic_speed_squared"] == 1 and verify_modular(request, out) == []
