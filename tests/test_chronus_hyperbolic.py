from fractions import Fraction
import sympy as sp
import pytest
from turing_universal_quantum_computer.quantum_walk import HyperbolicGraphWalk
from chronus.virtual_igpu.abi import Workload
from chronus.virtual_igpu.adapters import CPUEmulatorAdapter
from chronus.virtual_igpu.verifier import verify_workload_result


def test_hyperbolic_hamiltonian_unitarity_and_continuous_composition():
    walk = HyperbolicGraphWalk([(0, 1), (1, 1)], [(0, 1)])
    assert walk.hamiltonian == sp.Matrix(
        [[sp.Rational(2, 3), -sp.Rational(2, 3)], [-sp.Rational(2, 3), sp.Rational(2, 3)]]
    )
    u, v = walk.propagator(Fraction(1, 3)), walk.propagator(Fraction(2, 3))
    assert (u.H * u - sp.eye(2)).applyfunc(sp.simplify) == sp.zeros(2)
    assert (u * v - walk.propagator(1)).applyfunc(sp.simplify) == sp.zeros(2)
    assert walk.propagator(0) == sp.eye(2)
    w = Workload(
        id="walk",
        tenant="test",
        kind="hyperbolic_walk",
        input={"coordinates": [[0, 1], [1, 1]], "edges": [[0, 1]], "basis": 0, "time": [1, 3]},
    )
    result = CPUEmulatorAdapter().execute(w)
    assert verify_workload_result(w, result)["verdict"] == "match"
    result.output["amplitudes"][0] = 0
    assert verify_workload_result(w, result)["verdict"] == "mismatch"


def test_hyperbolic_walk_domain_refusal():
    with pytest.raises(ValueError):
        HyperbolicGraphWalk([(0, 0)], [])
    with pytest.raises(TypeError):
        HyperbolicGraphWalk([(0.5, 1)], [])
    with pytest.raises(ValueError):
        HyperbolicGraphWalk([(0, 1), (1, 1)], [(0, 1), (1, 0)])
