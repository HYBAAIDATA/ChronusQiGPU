"""Real execution of exact cross-domain adapters, discovery and workbench."""
from fractions import Fraction

import pytest

from chronus.geodesic.problems import SATProblem, IsingProblem, QuadraticLandscape
from chronus.geodesic.benchmarks import benchmark, h4_graph_order, run_trial
from chronus.geodesic.workbench import MathematicalWorkbench
from turing.exact.geometry.hilbert import SparseState, TensorHilbert


def test_sat_exact_benchmark_parity_and_measured_data():
    instance = SATProblem(3, ((1,2), (-1,3), (-2,-3)))
    order = h4_graph_order(instance.domain_size)
    assert set(order) == set(range(instance.domain_size))
    report = benchmark(instance, repetitions=2, input_classification="SYNTHETIC_TEST_FIXTURE",
                       git_commit="TEST")
    assert report["minima_parity_verified"]
    assert report["same_oracle_call_count_verified"]
    assert report["quantum_speedup_claimed"] is False
    assert len(report["trials"]) == 4
    assert all(t["oracle_calls"] == 8 for t in report["trials"])
    assert all(type(t["duration_ns"]) is int and t["duration_ns"] >= 0
               for t in report["trials"])


def test_ising_and_landscape_exact_different_domains():
    ising = IsingProblem(2, ((0,1,Fraction(-1,2)),))
    assert ising.objective(0) == Fraction(-1,2)
    assert ising.objective(1) == Fraction(1,2)
    landscape = QuadraticLandscape(2,
            ((Fraction(1),Fraction(0)), (Fraction(0),Fraction(1))),
            (Fraction(1), Fraction(0)))
    assert landscape.objective(1) == 0
    assert landscape.objective(0) == 1
    for problem in (ising,landscape):
        a = run_trial(problem,tuple(range(problem.domain_size)),"A")
        b = run_trial(problem,h4_graph_order(problem.domain_size),"B")
        assert a.argmin == b.argmin
        assert a.objective_minimum == b.objective_minimum
    with pytest.raises(ValueError):
        h4_graph_order(4097)


def test_jupyter_workbench_starts_from_real_turing_state_and_updates_exactly():
    space = TensorHilbert((32,600))
    state = SparseState.basis(space,(3,119))
    explorer = MathematicalWorkbench(state)
    first = explorer.inspect()
    assert first["classification"] == "EXACT_USER_SUPPLIED_TURING_STATE"
    assert first["basis_dimension"] == 19200
    assert first["basis"][0]["probability"] == "1"
    next_state = explorer.inject_phase(space.index((3,119)),"i")
    assert next_state["basis"][0]["real"] == "0"
    assert next_state["basis"][0]["imag"] == "1"
    assert next_state["norm_squared"] == "1"
    with pytest.raises(ValueError):
        explorer.inject_phase(space.index((3,119)),"sqrt(2)")


def test_workbench_phase_injection_is_atomic_for_large_exact_state():
    from turing.exact.geometry.hilbert import ExactComplex
    sp = TensorHilbert((1024,))
    amp = ExactComplex(Fraction(1,32))
    state = SparseState(sp,{i:amp for i in range(1024)})
    explorer = MathematicalWorkbench(state,max_entries=1024)
    assert explorer.inspect()["nonzero_amplitudes"] == 1024
    with pytest.raises(ValueError):
        explorer.inject_phase(0,"i",max_entries=256)
    assert explorer.state == state
    changed = explorer.inject_phase(0,"i",max_entries=1024)
    assert changed["nonzero_amplitudes"] == 1024
    assert changed["basis"][0]["imag"] == "1/32"
