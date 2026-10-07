"""Cross-implementation parity: ``kellogg.exact_tensor`` vs
``turing_universal_quantum_computer.exact_tensor``.

Two Q(zeta_8) substrates coexist in-tree (the audit's P1 #6). Both claim
the same Clifford+T exact plane: ``F4 = Q(sqrt(2)) + iQ(sqrt(2))``,
identical ``GATES`` inventory, and the same ``ExactStateVector`` API.
This suite applies one shared gate program to both implementations and
requires amplitude-identical output — a structural equivalence check at
the exact-fraction level, not a float comparison.
"""

from fractions import Fraction

import pytest

import kellogg.exact_tensor as K
import turing_universal_quantum_computer.exact_tensor as T


def _amps(state):
    """Exact amplitude signature — raw F4 channel Fractions."""
    return tuple((a.a, a.b, a.c, a.d) for a in state.amplitudes)


def _probs(state):
    """Exact Born-weight signature — raw Qsqrt2 channel Fractions."""
    return tuple((p.a, p.b) for p in state.probabilities_exact())


def _f4(value):
    return (value.a, value.b, value.c, value.d)


def _q(value):
    return (value.a, value.b)


def test_gate_inventories_are_identical():
    assert sorted(K.GATES) == sorted(T.GATES)
    for name in K.GATES:
        kg, tg = K.GATES[name], T.GATES[name]
        assert tuple(tuple(_f4(v) for v in row) for row in kg) == tuple(
            tuple(_f4(v) for v in row) for row in tg
        ), f"gate {name} matrices differ"


@pytest.mark.parametrize("gate", sorted(K.GATES))
def test_single_gate_parity_from_basis_states(gate):
    for index in (0, 1):
        k_state = K.ExactStateVector.basis(1, index)
        t_state = T.ExactStateVector.basis(1, index)
        assert _amps(k_state.apply_single(0, K.GATES[gate])) == _amps(
            t_state.apply_single(0, T.GATES[gate])
        )


def test_shared_gate_program_parity():
    """One program on both substrates must give identical amplitudes."""
    k_state = K.ExactStateVector.basis(2, 0)
    t_state = T.ExactStateVector.basis(2, 0)
    program = (
        ("single", (0, "H")),
        ("single", (1, "T")),
        ("cnot", (0, 1)),
        ("single", (1, "S")),
        ("cz", (0, 1)),
        ("single", (0, "Z")),
        ("single", (1, "Tdg")),
        ("cnot", (1, 0)),
        ("single", (0, "H")),
    )
    for kind, args in program:
        if kind == "single":
            qubit, gate = args
            k_state = k_state.apply_single(qubit, K.GATES[gate])
            t_state = t_state.apply_single(qubit, T.GATES[gate])
        elif kind == "cnot":
            k_state = k_state.apply_cnot(*args)
            t_state = t_state.apply_cnot(*args)
        else:
            k_state = k_state.apply_cz(*args)
            t_state = t_state.apply_cz(*args)
    assert _amps(k_state) == _amps(t_state)
    assert _probs(k_state) == _probs(t_state)
    assert _f4(k_state.norm_squared()) == _f4(t_state.norm_squared())
    assert k_state.normalized_exact() == t_state.normalized_exact() is True


def test_bell_state_entanglement_parity():
    """H then CNOT — measure, density, Schmidt all agree exactly."""
    k_state = K.ExactStateVector.basis(2, 0).apply_single(0, K.GATE_H).apply_cnot(0, 1)
    t_state = T.ExactStateVector.basis(2, 0).apply_single(0, T.GATE_H).apply_cnot(0, 1)
    assert _amps(k_state) == _amps(t_state)
    assert k_state.measure_deterministic() == t_state.measure_deterministic()
    k_rho = k_state.reduced_density((0,))
    t_rho = t_state.reduced_density((0,))
    assert [[_f4(v) for v in row] for row in k_rho] == [
        [_f4(v) for v in row] for row in t_rho
    ]
    assert k_state.schmidt_rank((0,)) == t_state.schmidt_rank((0,)) == 2


def test_gate_identities_parity():
    """T^2 = S and S^2 = Z hold identically on both substrates."""
    for index in (0, 1):
        k_t2 = K.ExactStateVector.basis(1, index).apply_single(
            0, K.GATE_T
        ).apply_single(0, K.GATE_T)
        t_t2 = T.ExactStateVector.basis(1, index).apply_single(
            0, T.GATE_T
        ).apply_single(0, T.GATE_T)
        assert _amps(k_t2) == _amps(t_t2)
        assert _amps(k_t2) == _amps(
            K.ExactStateVector.basis(1, index).apply_single(0, K.GATE_S)
        )
        assert _amps(t_t2) == _amps(
            T.ExactStateVector.basis(1, index).apply_single(0, T.GATE_S)
        )


def test_tensor_product_parity():
    k1 = K.ExactStateVector.basis(1, 0).apply_single(0, K.GATE_H)
    t1 = T.ExactStateVector.basis(1, 0).apply_single(0, T.GATE_H)
    k2 = K.ExactStateVector.basis(1, 1).apply_single(0, K.GATE_S)
    t2 = T.ExactStateVector.basis(1, 1).apply_single(0, T.GATE_S)
    assert _amps(k1.tensor(k2)) == _amps(t1.tensor(t2))


def test_z_eighths_all_powers_parity():
    for eighths in range(8):
        k_state = K.ExactStateVector.basis(2, 3).z_eighths(eighths, qubit=1)
        t_state = T.ExactStateVector.basis(2, 3).z_eighths(eighths, qubit=1)
        assert _amps(k_state) == _amps(t_state)


def test_qft_three_qubit_parity():
    program_state_k = (
        K.ExactStateVector.basis(3, 0)
        .apply_single(0, K.GATE_H)
        .apply_single(2, K.GATE_T)
        .apply_cnot(0, 2)
    )
    program_state_t = (
        T.ExactStateVector.basis(3, 0)
        .apply_single(0, T.GATE_H)
        .apply_single(2, T.GATE_T)
        .apply_cnot(0, 2)
    )
    assert _amps(program_state_k.qft()) == _amps(program_state_t.qft())
    assert _amps(program_state_k.qft(inverse=True)) == _amps(
        program_state_t.qft(inverse=True)
    )


def test_inner_product_and_fidelity_parity():
    k_a = K.ExactStateVector.basis(2, 0).apply_single(0, K.GATE_H)
    t_a = T.ExactStateVector.basis(2, 0).apply_single(0, T.GATE_H)
    k_b = K.ExactStateVector.basis(2, 0).apply_cnot(0, 1)
    t_b = T.ExactStateVector.basis(2, 0).apply_cnot(0, 1)
    assert _f4(k_a.inner(k_b)) == _f4(t_a.inner(t_b))
    assert _q(k_a.fidelity_squared(k_b)) == _q(t_a.fidelity_squared(t_b))


def test_controlled_and_toffoli_parity():
    k_state = K.ExactStateVector.basis(3, 7)
    t_state = T.ExactStateVector.basis(3, 7)
    assert _amps(k_state.apply_toffoli(0, 1, 2)) == _amps(
        t_state.apply_toffoli(0, 1, 2)
    )
    assert _amps(
        K.ExactStateVector.basis(2, 3).apply_controlled(0, 1, K.GATE_X)
    ) == _amps(
        T.ExactStateVector.basis(2, 3).apply_controlled(0, 1, T.GATE_X)
    )


def test_evolve_pauli_z_parity():
    for quarter_turns in range(4):
        k_state = K.ExactStateVector.basis(2, 1).evolve_pauli_z(quarter_turns, qubit=1)
        t_state = T.ExactStateVector.basis(2, 1).evolve_pauli_z(quarter_turns, qubit=1)
        assert _amps(k_state) == _amps(t_state)


def test_canonical_digest_parity():
    payload = {"b": [1, 2, 3], "a": {"x": "y"}, "n": 42}
    assert K.canonical_digest(payload) == T.canonical_digest(payload)


def test_density_helpers_parity():
    k_state = K.ExactStateVector.basis(2, 0).apply_single(0, K.GATE_H).apply_cnot(0, 1)
    t_state = T.ExactStateVector.basis(2, 0).apply_single(0, T.GATE_H).apply_cnot(0, 1)
    k_rho = k_state.reduced_density((0,))
    t_rho = t_state.reduced_density((0,))
    assert _f4(K.density_trace(k_rho)) == _f4(T.density_trace(t_rho))
    assert _f4(K.density_purity(k_rho)) == _f4(T.density_purity(t_rho))
    assert K.density_is_pure(k_rho) == T.density_is_pure(t_rho) is False


def test_fail_closed_parity():
    """Both refuse the same out-of-domain work identically.

    Honest asymmetry: TUQC raises bare ``NotImplementedError``; kellogg
    refined the refusal into ``NotInF4`` (a NotImplementedError subclass)
    and exposes ``rz``/``phase_gate`` TUQC lacks. The refusal boundary is
    the same; the error type is not — that difference is asserted, not
    hidden.
    """
    assert issubclass(K.NotInF4, NotImplementedError)
    with pytest.raises(K.NotInF4):
        K.ExactStateVector.basis(4, 0).qft()
    with pytest.raises(NotImplementedError):
        T.ExactStateVector.basis(4, 0).qft()
    # TURING's exact_tensor is now an alias of Kellogg's module (one
    # implementation, no fork), so rz() and NotInF4 are the same objects.
    assert T is K
    assert hasattr(T, "rz")
    with pytest.raises(K.NotInF4):
        K.rz(Fraction(1, 7))
