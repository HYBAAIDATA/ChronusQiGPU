"""2,500-qubit instances of the exact matrix product state; the register size is read from the register.

Every value checked here is exact. The instances are low-entanglement circuits (GHZ, product states and a
depth-2 brickwork), which is why they fit in bond dimension 2.
"""

import sys
from fractions import Fraction
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.tensor import ExactAmplitude, ExactMPS, cyclotomic, evaluate_circuit  # noqa: E402

F8 = cyclotomic(8)
WIDTH = 2500


def _ghz(width):
    return [("h", (0,), ())] + [("cnot", (q, q + 1), ()) for q in range(width - 1)]


def _brickwork(width):
    """Depth-2 brickwork: H, CZ on even pairs, T; then H, CZ on odd pairs, T."""
    gates = [("h", (q,), ()) for q in range(width)]
    gates += [("cz", (q, q + 1), ()) for q in range(0, width - 1, 2)]
    gates += [("t", (q,), ()) for q in range(width)]
    gates += [("h", (q,), ()) for q in range(width)]
    gates += [("cz", (q, q + 1), ()) for q in range(1, width - 1, 2)]
    gates += [("t", (q,), ()) for q in range(width)]
    return gates


def _pattern(width):
    return tuple(1 if (q * q + 3 * q) % 7 < 3 else 0 for q in range(width))


def _brickwork_closed_form(bits):
    """Unnormalised amplitude <x| T CZ_odd H T CZ_even H |0> for an even number of qubits.

    With D = T CZ (diagonal): <x|psi> = 2^-n zeta^|x| (-1)^odd(x) sum_y zeta^|y| (-1)^even(y) (-1)^(x.y), and
    the sum over y factorises over the even pairs (y_2j, y_2j+1): f(u, v) = sum_ab zeta^(a+b) (-1)^(ab+ua+vb).
    """
    n = len(bits)
    value = F8.zeta(sum(bits) % 8)
    if sum(bits[q] * bits[q + 1] for q in range(1, n - 1, 2)) % 2:
        value = F8.neg(value)
    for j in range(0, n, 2):
        value = F8.mul(value, _pair_factor(bits[j], bits[j + 1]))
    return value


def _pair_factor(u, v):
    """f(u, v) = sum over a, b in {0, 1} of zeta^(a + b) (-1)^(ab + ua + vb)."""
    total = F8.zero
    for a in (0, 1):
        for b in (0, 1):
            term = F8.zeta(a + b)
            total = F8.sub(total, term) if (a * b + u * a + v * b) % 2 else F8.add(total, term)
    return total


class _Dense:
    """Small dense check in Q(zeta_8) (bit q of an index is qubit q), unnormalised H = [[1, 1], [1, -1]]."""

    def __init__(self, n):
        self.n = n
        self.amplitudes = [F8.one] + [F8.zero] * ((1 << n) - 1)

    def apply(self, name, qubits):
        amps = self.amplitudes
        if name == "h":
            bit = 1 << qubits[0]
            for index in range(1 << self.n):
                if not index & bit:
                    a0, a1 = amps[index], amps[index | bit]
                    amps[index], amps[index | bit] = F8.add(a0, a1), F8.sub(a0, a1)
        elif name == "t":
            for index in range(1 << self.n):
                if (index >> qubits[0]) & 1:
                    amps[index] = F8.mul(amps[index], F8.zeta(1))
        elif name == "cz":
            for index in range(1 << self.n):
                if (index >> qubits[0]) & 1 and (index >> qubits[1]) & 1:
                    amps[index] = F8.neg(amps[index])
        else:
            raise ValueError(name)


def test_ghz_2500_qubits():
    register = evaluate_circuit(WIDTH, _ghz(WIDTH), max_bond=2)
    n = register.num_sites
    assert n == 2500
    bonds = register.bond_dimensions()
    assert len(bonds) == n - 1 and set(bonds) == {2}
    assert register.probability("0" * n) == Fraction(1, 2)
    assert register.probability("1" * n) == Fraction(1, 2)
    assert register.probability("1" + "0" * (n - 1)) == 0
    assert register.probability("0" * (n // 2) + "1" * (n - n // 2)) == 0
    assert register.amplitude("0" * n) == ExactAmplitude(F8, 1, 2)
    for q in (0, n // 2, n - 1):
        assert register.marginal_probabilities(q) == (Fraction(1, 2), Fraction(1, 2))
    assert register.scale == 2


def test_ghz_with_t_on_every_qubit_2500_qubits():
    register = evaluate_circuit(WIDTH, _ghz(WIDTH), max_bond=2)
    n = register.num_sites
    for q in range(n):
        register.t(q)
    amplitude = register.amplitude("1" * n)
    assert amplitude.value == F8.zeta(n % 8) and amplitude.scale == 2
    assert amplitude == ExactAmplitude(F8, F8.zeta(n % 8), 2)
    assert n % 8 == 4 and amplitude == ExactAmplitude(F8, -1, 2)
    assert register.amplitude("0" * n) == ExactAmplitude(F8, 1, 2)
    assert register.probability("1" * n) == Fraction(1, 2)
    assert register.probability("0" * n) == Fraction(1, 2)
    assert set(register.bond_dimensions()) == {2}


def test_product_state_h_t_h_on_2500_qubits():
    register = ExactMPS(WIDTH)
    for q in range(register.num_sites):
        register.h(q).t(q).h(q)
    n = register.num_sites
    assert set(register.bond_dimensions()) == {1}
    bits = _pattern(n)
    ones = sum(bits)
    zeta = F8.zeta(1)
    # H T H |0> = ((1 + zeta) |0> + (1 - zeta) |1>) / 2 on every qubit.
    expected = F8.div(F8.mul((F8.one + zeta) ** (n - ones), (F8.one - zeta) ** ones), F8.from_int(2 ** n))
    amplitude = register.amplitude(bits)
    assert amplitude == ExactAmplitude(F8, expected)
    assert amplitude.scale == 1 and F8.eq(amplitude.value, expected)
    plus = F8.div(F8.mul(F8.one + zeta, F8.conj(F8.one + zeta)), F8.from_int(4))
    minus = F8.div(F8.mul(F8.one - zeta, F8.conj(F8.one - zeta)), F8.from_int(4))
    assert F8.eq(register.probability(bits), F8.mul(plus ** (n - ones), minus ** ones))
    root_two = F8.positive_sqrt(2)
    assert F8.eq(plus, F8.div(F8.add(F8.from_int(2), root_two), F8.from_int(4)))
    assert F8.eq(minus, F8.div(F8.sub(F8.from_int(2), root_two), F8.from_int(4)))
    assert not plus.is_rational() and ones == 715
    for q in (0, n - 1):
        assert register.marginal_probabilities(q) == (plus, minus)


def test_brickwork_closed_form_and_dense_check_at_small_sizes():
    for width in range(2, 11):
        dense = _Dense(width)
        for name, qubits, _ in _brickwork(width):
            dense.apply(name, qubits)
        register = evaluate_circuit(width, _brickwork(width))
        assert register.scale == 4 ** width
        table = register.to_dense()
        for index, value in enumerate(dense.amplitudes):
            bits = tuple((index >> q) & 1 for q in range(width))
            assert F8.eq(table[bits], value)
            if width % 2 == 0:
                assert F8.eq(_brickwork_closed_form(bits), value)
        assert register.amplitude(_pattern(width)) == ExactAmplitude(F8, dense.amplitudes[
            sum(bit << q for q, bit in enumerate(_pattern(width)))], 4 ** width)
        assert max(register.bond_dimensions()) <= 2


def test_brickwork_2500_qubits():
    register = evaluate_circuit(WIDTH, _brickwork(WIDTH), max_bond=2)
    n = register.num_sites
    bonds = register.bond_dimensions()
    assert len(bonds) == n - 1 and set(bonds) == {2}
    assert register.scale == 4 ** n
    for bits in (tuple([0] * n), _pattern(n)):
        amplitude = register.amplitude(bits)
        expected = F8.div(_brickwork_closed_form(bits), F8.from_int(2 ** n))
        assert amplitude == ExactAmplitude(F8, expected)
        assert amplitude.scale == 1
    zeros = register.amplitude(tuple([0] * n))
    pair = F8.add(F8.sub(F8.one, F8.zeta(2)), F8.mul(F8.from_int(2), F8.zeta(1)))
    assert F8.eq(zeros.value, F8.div(pair ** (n // 2), F8.from_int(2 ** n)))
    assert F8.eq(pair, _pair_factor(0, 0))
    # |f(0,0)|^2 = |f(1,1)|^2 = 6 and |f(0,1)|^2 = |f(1,0)|^2 = 2, so P(0...0) = 6^1250 / 2^5000 = (3/8)^1250.
    for u, v, size in ((0, 0, 6), (1, 1, 6), (0, 1, 2), (1, 0, 2)):
        factor = _pair_factor(u, v)
        assert F8.eq(F8.mul(factor, F8.conj(factor)), F8.from_int(size))
    assert zeros.probability() == Fraction(3, 8) ** (n // 2)
    # By the pair factorisation every single-qubit marginal is (6 + 2) / 16 = 1/2; the middle one is computed here.
    assert register.marginal_probabilities(n // 2) == (Fraction(1, 2), Fraction(1, 2))
