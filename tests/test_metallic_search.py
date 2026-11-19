"""Metallic-family search restructure: exact experiments and closed form."""

import pytest

from chronus.quantum import P, StateVector
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

pytestmark = pytest.mark.simulated


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


def test_jform_family_reproduces_published_telemetry_vector():
    # Externally reported n=10 Bitcoin-nonce trace: u=249, k=249, alpha=33,
    # beta=147, marked index 42. Every number must reproduce exactly.
    from chronus.quantum.metallic_search import jform_iterate, jform_one_shot_phases

    u = pow(30, 10, P)
    assert u == 249
    assert (33, 147) in jform_one_shot_phases(10)
    state = StateVector(10)
    for q in range(10):
        state.apply("H", q)
    assert state.amplitudes[42] == 249
    jform_iterate(state, 42, 33, 147)
    assert state.amplitudes[42] == 1
    assert all(a == 0 for i, a in enumerate(state.amplitudes) if i != 42)
    # Trace intermediates: marked after oracle 250, mean 56.
    mean = ((33 * u) % P + 1023 * u) % P * pow(1024, -1, P) % P
    assert (33 * u) % P == 250 and mean == 56


def test_both_operator_families_agree_at_nonce_space_scale():
    from chronus.quantum.subspace import (
        exact_jform_subspace_search,
        exact_subspace_search,
    )

    for n in (10, 16, 20, 32):
        ours = exact_subspace_search(n, 1)
        jform = exact_jform_subspace_search(n, 1)
        assert ours.marked_amplitude in (1, P - 1)
        assert jform.marked_amplitude in (1, P - 1)
        assert ours.unmarked_amplitude == jform.unmarked_amplitude == 0


def test_n1000_published_vectors_reproduce_exactly():
    # Externally reported n=1000 traces: single-marked and six multi-marked rows.
    from chronus.quantum.metallic_search import jform_one_shot_phases
    from chronus.quantum.subspace import exact_jform_subspace_search

    assert pow(30, 1000, P) == 241 and pow(2, 1000, P) == 256
    assert (17, 120) in jform_one_shot_phases(1000)
    claimed = [(2, 199, 239), (4, 102, 237), (8, 85, 233),
               (16, 128, 225), (32, 171, 209), (64, 154, 177)]
    for marked_count, beta, mu in claimed:
        pairs = jform_one_shot_phases(1000, marked_count)
        assert pairs[0][0] == 17  # invariant oracle phase
        assert any(pair[1] == beta for pair in pairs)
        n_mod, u = pow(2, 1000, P), pow(30, 1000, P)
        assert pow(n_mod, -1, P) * ((n_mod * u + marked_count) % P) % P == mu
        result = exact_jform_subspace_search(1000, marked_count)
        assert result.marked_amplitude == 1 and result.unmarked_amplitude == 0


def test_scaling_slide_climbs_with_lucas_ladder():
    import json

    from chronus.backends.metallic import metallic_sequence
    from chronus.execution import NativeMathReferenceBackend

    backend = NativeMathReferenceBackend()
    result = backend.execute(
        json.dumps({"num_qubits": 10, "marked_count": 1}).encode(),
        "EXACT_PHASE_SEARCH",
    )
    slide = result["scaling_slide"]
    assert [rung["num_qubits"] for rung in slide] == [8, 9, 10, 11, 12]
    for rung in slide:
        assert rung["lucas_trace"] == str(metallic_sequence(1, rung["num_qubits"]))
        assert rung["uniform_amplitude"] == pow(30, rung["num_qubits"], P)
    # The slide ascends the Lucas ladder: L_11 = 199 at n=11.
    assert slide[3]["lucas_trace"] == "199"


def test_phase_search_surface_modes():
    import json

    from chronus.backends.lattice import HardwareUnavailableError
    from chronus.execution import ExecutionRouter, execution_router

    payload = json.dumps({"num_qubits": 6, "marked_count": 2, "surface": "accelerator"}).encode()
    with pytest.raises(HardwareUnavailableError):
        ExecutionRouter().execute(payload, "EXACT_PHASE_SEARCH")

    auto = ExecutionRouter().execute(
        json.dumps({"num_qubits": 6, "marked_count": 2, "surface": "auto"}).encode(),
        "EXACT_PHASE_SEARCH",
    )
    assert auto.result["surface"] == "substrate"

    class FakePhaseAccelerator:
        name = "fake-phase-gpu"
        execution_mode = "PHYSICAL_ACCELERATOR"
        supported_workloads = frozenset({"EXACT_PHASE_SEARCH"})

        def supports(self, workload_type):
            return True

        def probe_silicon(self):
            return {"device_name": "fake", "known_answer_test": "passed"}

        def execute(self, payload, workload_type):
            return {"execution_mode": "PHYSICAL_ACCELERATOR",
                    "surface": "client-accelerator", "fake": True}

    execution_router.register_backend(FakePhaseAccelerator())
    try:
        climbed = ExecutionRouter().execute(
            json.dumps({"num_qubits": 6, "marked_count": 2, "surface": "accelerator"}).encode(),
            "EXACT_PHASE_SEARCH",
        )
        assert climbed.result["surface"] == "client-accelerator"
        assert "scaling_slide" in climbed.result  # slide accompanies climb-in
    finally:
        del execution_router._backends["fake-phase-gpu"]


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
