"""Metallic-family search restructure: exact experiments and closed form."""

import pytest

from chronus.quantum import StateVector
from chronus.quantum.metallic_search import (
    METALLIC_COEFFICIENTS,
    QSqrt2,
    algebraic_search,
    exact_search,
    exact_search_multi,
    generalized_iterate,
    one_shot_phases,
    one_shot_phases_multi,
    phase_iterate,
    phase_iterate_multi,
    phase_matched_sweep,
)


def test_qsqrt2_exact_arithmetic_and_sign():
    half = QSqrt2(0, 1, 1)  # sqrt(2)/2 = 1/sqrt(2)
    # (sqrt(2)/2)^2 computed manually: (b^2 * 2, 2ab, 2e) = (2, 0, 2) = 2/4 = 1/2
    product = QSqrt2(half.b * half.b * 2, 2 * half.a * half.b, half.e * 2)
    assert product.a == 2 and product.b == 0 and product.e == 2
    assert QSqrt2(1, 0, 1).add(QSqrt2(0, 1, 2)).sign() > 0
    assert QSqrt2(-3, 2, 0).sign() < 0  # -3 + 2*sqrt2 < 0
    assert QSqrt2(3, -2, 0).sign() > 0  # 3 - 2*sqrt2 > 0
    with pytest.raises(ValueError):
        QSqrt2(1, 0, 0).scale(__import__("fractions").Fraction(1, 3))


def test_generalized_iterate_c2_reproduces_grover():
    for n in (1, 2, 3):
        state = StateVector(n)
        for q in range(n):
            state.apply("H", q)
        generalized_iterate(state, 0, METALLIC_COEFFICIENTS["grover"])
        reference = StateVector(n)
        for q in range(n):
            reference.apply("H", q)
        from chronus.quantum import grover_iterate
        grover_iterate(reference, 0)
        assert state.equivalent(reference)


def test_algebraic_grover_reproduces_sqrt_n_iteration_counts():
    counts = [algebraic_search("grover", n)[0] for n in range(2, 13)]
    assert counts == [1, 2, 3, 4, 6, 8, 12, 17, 25, 35, 50]


def test_overshoot_is_detected_not_hidden():
    # Metallic reflection coefficients c > 2 overshoot: no clean first peak
    # within the iteration cap, which the harness reports honestly.
    peak, history = algebraic_search("silver", 6, max_iterations=400)
    assert len(history) == 401  # never settled


def test_one_shot_phases_match_exhaustive_sweep():
    for n in (1, 2, 3):
        sweep = phase_matched_sweep(n, (1 << n) - 1, max_iterations=4)
        assert sweep["minimal_iterations"] == 1
        assert set(one_shot_phases(n)) == set(sweep["phase_pairs_at_minimum"])


def test_exact_search_converges_in_one_iteration_for_all_marks():
    for n in (1, 2, 3, 4, 6, 8, 10):
        for marked in range(1 << n) if n <= 4 else (0, 5, (1 << n) - 1):
            state = exact_search(n, marked)
            assert state.amplitudes[marked] in (1, 256)
            assert all(a == 0 for i, a in enumerate(state.amplitudes) if i != marked)


def test_phase_iterate_validates_inputs():
    with pytest.raises(ValueError):
        phase_iterate(StateVector(1), 0, 257, 1)
    with pytest.raises(ValueError):
        phase_iterate(StateVector(1), 7, 1, 1)
    with pytest.raises(ValueError):
        one_shot_phases(0)


def test_multi_marked_reduces_to_single_marked_at_r1():
    for n in (1, 2, 3, 4):
        assert sorted(one_shot_phases_multi(n, 1)) == sorted(one_shot_phases(n))


def test_multi_marked_converges_for_all_counts_and_subsets():
    # Exhaustive subsets at small sizes; sampled at larger ones.
    from itertools import combinations

    for n in (2, 3, 4):
        n_states = 1 << n
        for r in range(1, n_states):
            subsets = combinations(range(n_states), r) if n_states <= 8 else \
                [tuple(range(r)), tuple(range(n_states - r, n_states))]
            for subset in subsets:
                state = exact_search_multi(n, set(subset))
                amps = state.amplitudes
                assert all(amps[i] in (1, 256) for i in subset)
                assert all(amps[i] == 0 for i in range(n_states) if i not in subset)


def test_multi_marked_converges_at_scale():
    for n, r in ((6, 3), (8, 5), (10, 7)):
        marked = set(list(range(0, 1 << n, (1 << n) // r))[:r])
        state = exact_search_multi(n, marked)
        assert all(state.amplitudes[i] in (1, 256) for i in marked)
        assert sum(1 for a in state.amplitudes if a != 0) == r


def test_multi_marked_validates_inputs():
    with pytest.raises(ValueError):
        one_shot_phases_multi(2, 0)
    with pytest.raises(ValueError):
        one_shot_phases_multi(2, 4)
    with pytest.raises(ValueError):
        phase_iterate_multi(StateVector(1), set(), 1, 1)
    with pytest.raises(ValueError):
        phase_iterate_multi(StateVector(1), {3}, 1, 1)


def test_symbolic_subspace_search_matches_dense_engine_exactly():
    from chronus.quantum.subspace import (
        exact_subspace_search,
        subspace_iterate,
        uniform_subspace,
    )

    for n, r in ((2, 1), (2, 3), (3, 4), (4, 2), (4, 5), (6, 7)):
        dense = exact_search_multi(n, set(range(r)))
        symbolic = exact_subspace_search(n, r)
        assert symbolic.marked_amplitude == dense.amplitudes[0]
        assert symbolic.unmarked_amplitude == 0
    # Iterated trajectories agree too, step by step.
    dense = StateVector(3)
    for q in range(3):
        dense.apply("H", q)
    symbolic = uniform_subspace(3, 2)
    alpha, beta = one_shot_phases_multi(3, 2)[0]
    for _ in range(3):
        dense = phase_iterate_multi(dense, {0, 1}, alpha, beta)
        symbolic = subspace_iterate(symbolic, alpha, beta)
        assert symbolic.marked_amplitude == dense.amplitudes[0]
        assert symbolic.unmarked_amplitude == dense.amplitudes[2]


def test_phase_search_workload_persists_in_phyllotaxis_memory():
    import json

    from chronus.execution import NativeMathReferenceBackend

    backend = NativeMathReferenceBackend()
    result = backend.execute(json.dumps({
        "num_qubits": 6, "marked_count": 7, "store": True,
    }).encode(), "EXACT_PHASE_SEARCH")
    assert result["iterations"] == 1
    assert result["state"]["unmarked_amplitude"] == 0
    memory = result["memory"]
    record = memory["theseus_record"]
    assert record["scale_index"] == 6  # PV lineage carries the search scale
    assert 0 <= record["coordinate"]["lane"] < 32  # golden-ratio lane
    retrieved = backend.execute(json.dumps({
        "object_id": record["object_id"], "tenant_id": "phase-search",
    }).encode(), "THESEUS_RETRIEVE")
    import base64
    stored = json.loads(base64.b64decode(retrieved["data"][7:]))
    assert stored == result["state"]  # exact round trip through Theseus
    assert memory["cassini_parity"] == 1  # even index parity metadata


def test_phase_search_workload_validates():
    import json

    from chronus.execution import NativeMathReferenceBackend

    backend = NativeMathReferenceBackend()
    with pytest.raises(ValueError):
        backend.execute(json.dumps({"num_qubits": 0, "marked_count": 1}).encode(),
                        "EXACT_PHASE_SEARCH")
    with pytest.raises(ValueError):
        backend.execute(json.dumps({"num_qubits": 3, "marked_count": 8}).encode(),
                        "EXACT_PHASE_SEARCH")


def test_multi_marked_closed_form_matches_brute_force_minimum():
    # Brute-force phase sweep for n=2, r=2 must rediscover the closed form.
    n, r = 2, 2
    found = set()
    for alpha in range(1, 257):
        for beta in range(1, 257):
            state = StateVector(n)
            for q in range(n):
                state.apply("H", q)
            phase_iterate_multi(state, {0, 1}, alpha, beta)
            amps = state.amplitudes
            if amps[0] in (1, 256) and amps[1] in (1, 256) \
                    and amps[2] == 0 and amps[3] == 0:
                found.add((alpha, beta))
    assert set(one_shot_phases_multi(n, r)) <= found
