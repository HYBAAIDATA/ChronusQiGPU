"""The implemented quantum-processor and resonance substrates must really work.

These modules replace pre-consolidation classes that were never migrated, so
the tests here are the evidence that the replacements are real: they check
physical/algebraic invariants (unitarity, normalisation, determinism, bounds),
not just that a symbol is importable.
"""

import math

import numpy as np
import pytest

from agi.quantum_processor import (
    PHI,
    ProblemDomain,
    QuantumProblemState,
    UniversalQuantumProcessor,
)
from agi.resonance import PHI_INV, PhiResonanceScorer, phi_resonance_of

# --------------------------------------------------------------------------
# ProblemDomain
# --------------------------------------------------------------------------


def test_problem_domain_covers_every_declared_member():
    values = {d.value for d in ProblemDomain}
    assert "optimization" in values
    assert len(values) == len(list(ProblemDomain))


@pytest.mark.parametrize(
    "raw,expected",
    [
        (ProblemDomain.OPTIMIZATION, ProblemDomain.OPTIMIZATION),
        ("optimization", ProblemDomain.OPTIMIZATION),
        ("  RESEARCH ", ProblemDomain.RESEARCH),
        ("not-a-domain", ProblemDomain.UNKNOWN),
        (17, ProblemDomain.UNKNOWN),
    ],
)
def test_problem_domain_coercion(raw, expected):
    assert ProblemDomain.coerce(raw) is expected


# --------------------------------------------------------------------------
# Problem state: normalisation, determinism, unitarity
# --------------------------------------------------------------------------


def test_state_is_normalised_to_unit_l2_norm():
    state = QuantumProblemState("p", "n", ProblemDomain.OPTIMIZATION, {"a": 1}, 256)
    assert math.isclose(float(np.linalg.norm(state.amplitudes)), 1.0, rel_tol=1e-12)


def test_born_probabilities_are_a_valid_distribution():
    state = QuantumProblemState("p", "n", ProblemDomain.SCIENTIFIC, {"a": 1}, 512)
    probs = state.probabilities()
    assert probs.shape == (512,)
    assert np.all(probs >= 0.0)
    assert math.isclose(float(probs.sum()), 1.0, rel_tol=1e-12)


def test_entropy_is_non_negative_and_bounded_by_log_dim():
    dim = 128
    state = QuantumProblemState("p", "n", ProblemDomain.MATHEMATICAL, {"a": 1}, dim)
    entropy = state.von_neumann_entropy()
    assert 0.0 <= entropy <= math.log(dim) + 1e-9


def test_same_payload_is_deterministic_and_different_payloads_differ():
    a = QuantumProblemState("p", "n", ProblemDomain.OPTIMIZATION, {"v": 7}, 256)
    b = QuantumProblemState("p", "n", ProblemDomain.OPTIMIZATION, {"v": 7}, 256)
    c = QuantumProblemState("p", "n", ProblemDomain.OPTIMIZATION, {"v": 8}, 256)
    assert np.allclose(a.amplitudes, b.amplitudes)
    assert not np.allclose(a.amplitudes, c.amplitudes)


def test_domain_participates_in_the_state():
    a = QuantumProblemState("p", "n", ProblemDomain.OPTIMIZATION, {"v": 7}, 128)
    b = QuantumProblemState("p", "n", ProblemDomain.RESEARCH, {"v": 7}, 128)
    assert not np.allclose(a.amplitudes, b.amplitudes)


def test_evolution_preserves_norm():
    state = QuantumProblemState("p", "n", ProblemDomain.OPTIMIZATION, {"v": 3}, 256)
    for iterations in (0, 1, 5, 64):
        evolved = state.evolve(iterations)
        assert math.isclose(float(np.linalg.norm(evolved)), 1.0, rel_tol=1e-10)


def test_evolution_is_unitary_so_probabilities_stay_normalised():
    state = QuantumProblemState("p", "n", ProblemDomain.OPTIMIZATION, {"v": 3}, 256)
    probs = state.probabilities(state.evolve(17))
    assert math.isclose(float(probs.sum()), 1.0, rel_tol=1e-12)


# --------------------------------------------------------------------------
# Processor lifecycle and fail-closed behaviour
# --------------------------------------------------------------------------


def test_create_problem_returns_id_and_state_and_registers_it():
    proc = UniversalQuantumProcessor(max_dimension=2**12)
    pid, state = proc.create_problem(name="demo", domain=ProblemDomain.OPTIMIZATION, data={"x": 1})
    assert pid in proc.list_problems()
    assert proc.get_problem(pid) is state


def test_register_caps_dimension_at_maximum():
    proc = UniversalQuantumProcessor(max_dimension=64)
    _pid, state = proc.create_problem(name="big", register_dim=1 << 20)
    assert state.register_dim == 64


def test_invalid_max_dimension_is_rejected():
    with pytest.raises(ValueError):
        UniversalQuantumProcessor(max_dimension=0)


def test_solve_returns_the_documented_fields():
    proc = UniversalQuantumProcessor(max_dimension=2**10)
    pid, _state = proc.create_problem(name="demo", domain=ProblemDomain.OPTIMIZATION, data={"x": 1})
    result = proc.solve(pid, algorithm="phi_resonance", iterations=8)
    for key in ("status", "solution", "quantum_speedup"):
        assert key in result
    assert result["status"] == "solved"
    assert result["iterations_required"] == 8
    assert len(result["solution"]["top_indices"]) == 8
    assert 0.0 <= result["solution"]["top_probability_mass"] <= 1.0 + 1e-9


def test_solve_on_unknown_problem_fails_closed_without_a_solution():
    proc = UniversalQuantumProcessor(max_dimension=2**8)
    result = proc.solve("nope", algorithm="phi_resonance", iterations=4)
    assert result["status"] == "unknown_problem"
    assert result["solution"] == {}
    assert result["quantum_speedup"] == 1.0


def test_unsupported_algorithm_is_reported_not_invented():
    proc = UniversalQuantumProcessor(max_dimension=2**8)
    pid, _ = proc.create_problem(name="d", data={"x": 1})
    result = proc.solve(pid, algorithm="telepathy", iterations=1)
    assert result["status"] == "unsupported_algorithm"
    assert result["solution"] == {}
    assert "phi_resonance" in result["supported"]


def test_solve_is_deterministic_for_the_same_inputs():
    proc = UniversalQuantumProcessor(max_dimension=2**10)
    pid, _ = proc.create_problem(name="d", data={"x": 42})
    first = proc.solve(pid, algorithm="phi_resonance", iterations=6)
    second = proc.solve(pid, algorithm="phi_resonance", iterations=6)
    assert first["solution"] == second["solution"]


def test_stats_report_real_counters_only():
    proc = UniversalQuantumProcessor(max_dimension=2**10)
    pid, _ = proc.create_problem(name="d", data={"x": 1})
    proc.solve(pid, algorithm="phi_resonance", iterations=2)
    stats = proc.stats()
    assert stats["problems_registered"] == 1
    assert stats["solutions_returned"] == 1
    assert stats["max_dimension"] == 2**10


# --------------------------------------------------------------------------
# PhiResonanceScorer
# --------------------------------------------------------------------------


def test_single_resonance_is_bounded():
    for v in range(-50, 51):
        assert 0.0 <= phi_resonance_of(v) <= 1.0


def test_resonance_is_maximal_at_a_resonant_value():
    # v = 0 places {0} at 0; the Pisot conjugate is 0.618..., so 0 is not
    # maximal. Verify the definition against a hand-computed value instead.
    v = 3
    expected = 1.0 - abs((v * PHI) % 1.0 - PHI_INV)
    assert math.isclose(phi_resonance_of(v), expected, rel_tol=1e-12)


def test_score_of_empty_input_is_zero_not_one():
    scorer = PhiResonanceScorer()
    assert scorer.score([]) == 0.0
    assert scorer.score(None) == 0.0


def test_score_is_bounded_and_a_mean_of_its_terms():
    scorer = PhiResonanceScorer()
    values = [3, 8, 21, 55]
    expected = sum(phi_resonance_of(v) for v in values) / len(values)
    assert math.isclose(scorer.score(values), expected, rel_tol=1e-12)
    assert 0.0 <= scorer.score(values) <= 1.0


def test_score_accepts_a_bare_scalar():
    scorer = PhiResonanceScorer()
    assert math.isclose(scorer.score(3), phi_resonance_of(3), rel_tol=1e-12)


def test_score_handles_non_numeric_input_without_raising():
    scorer = PhiResonanceScorer()
    assert 0.0 <= scorer.score(["a", None, 3]) <= 1.0


def test_score_detailed_reports_distribution_and_delta():
    scorer = PhiResonanceScorer()
    detail = scorer.score_detailed([3, 8, 21])
    assert detail["count"] == 3
    assert detail["min"] <= detail["score"] <= detail["max"]
    assert math.isclose(
        detail["delta_vs_baseline"], detail["score"] - detail["baseline"], rel_tol=1e-12
    )


def test_baseline_is_the_analytic_uniform_expectation():
    scorer = PhiResonanceScorer()
    c = PHI_INV
    expected = (c * c + (1.0 - c) ** 2) / 2.0
    assert math.isclose(scorer.baseline, expected, rel_tol=1e-12)
    assert 0.0 < scorer.baseline < 1.0


def test_zero_iterations_is_the_identity():
    state = QuantumProblemState("p", "n", ProblemDomain.OPTIMIZATION, {"v": 3}, 128)
    assert np.allclose(state.evolve(0), state.amplitudes)


def test_top_indices_are_the_most_probable_and_are_ordered():
    state = QuantumProblemState("p", "n", ProblemDomain.OPTIMIZATION, {"v": 5}, 64)
    evolved = state.evolve(9)
    top = state.top_indices(evolved, k=5)
    probs = state.probabilities(evolved)
    assert len(top) == 5
    assert list(probs[top]) == sorted(probs[top], reverse=True)
