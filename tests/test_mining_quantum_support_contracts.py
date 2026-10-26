"""Invoke PYTHIA's named support arsenal; no mining advantage claim."""

from fractions import Fraction

import pytest
import sympy as sp

from chronus.mla1517.mining.pythia_authority import PythiaQuantumArsenal


@pytest.mark.parametrize(
    "name", ["hendrix", "tunnelling", "annealing", "swarming", "entanglement"]
)
def test_named_required_support_is_callable_through_pythia(name):
    assert callable(PythiaQuantumArsenal().resolve(name))


def test_tunnelling_invocation_has_independent_symbolic_reference():
    actual = PythiaQuantumArsenal().invoke("tunnelling", 2, 1)
    assert sp.simplify(actual - (1 - sp.exp(-2 * sp.pi))) == 0


def test_annealing_invocation_zero_field_gap():
    model = PythiaQuantumArsenal().invoke("annealing", 4, field=0)
    assert sp.simplify(model.gap() - 2) == 0


def test_entanglement_born_probabilities_and_correlated_measurements():
    state_type = PythiaQuantumArsenal().resolve("entanglement")
    state = state_type.ghz(2)
    assert state.measurement_probabilities(0) == (
        Fraction(1, 2),
        Fraction(1, 2),
    )
    result = state.measure(0, seed=7)
    assert state.measurement_probabilities(1) == (
        (Fraction(1), Fraction(0))
        if result == 0
        else (Fraction(0), Fraction(1))
    )


def test_swarm_invocation_preserves_seeded_sampling_boundary():
    arsenal = PythiaQuantumArsenal()

    def law(_):
        return {0: Fraction(1, 2), 1: Fraction(1, 2)}

    first = arsenal.invoke("swarming", 16, law, seed=7).run(3)
    second = arsenal.invoke("swarming", 16, law, seed=7).run(3)
    assert first.positions == second.positions
    assert sum(first.empirical_distribution().values()) == 1
    assert first.status()["truth_class"] == (
        "exact_quantum_distribution_classical_sampling"
    )


def test_unknown_capability_cannot_silently_become_another_algorithm():
    with pytest.raises(KeyError):
        PythiaQuantumArsenal().resolve("unregistered_algorithm")
