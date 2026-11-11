import sys
from fractions import Fraction
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.algebra import CyclotomicField  # noqa: E402
from turing.algorithms.clifford import CliffordCircuit  # noqa: E402
from turing.tensor import (  # noqa: E402
    DEFAULT_MAX_BOND,
    QQ,
    ExactAmplitude,
    ExactMPS,
    ExactTensor,
    cyclotomic,
    evaluate_circuit,
    rank,
)

F8 = cyclotomic(8)
Q8 = CyclotomicField(8)

# ---------------------------------------------------------------------------------------------
# Independent dense reference over Z[zeta_8]: an amplitude is a 4-tuple of ints (c0, c1, c2, c3)
# meaning c0 + c1 z + c2 z^2 + c3 z^3 with z^4 = -1. Gates are the unnormalised integer matrices,
# so the reference never divides; its normalisation is the product of the gate scales.
# ---------------------------------------------------------------------------------------------

ZERO = (0, 0, 0, 0)
UNIT = (1, 0, 0, 0)
MINUS = (-1, 0, 0, 0)
I_UNIT = (0, 0, 1, 0)
MINUS_I = (0, 0, -1, 0)
ROOT_TWO = (0, 1, 0, -1)


def z_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2], a[3] + b[3])


def z_mul(a, b):
    out = [0, 0, 0, 0]
    for i, x in enumerate(a):
        if x:
            for j, y in enumerate(b):
                if y:
                    if i + j < 4:
                        out[i + j] += x * y
                    else:
                        out[i + j - 4] -= x * y
    return tuple(out)


def z_power(k):
    k %= 8
    out = [0, 0, 0, 0]
    out[k % 4] = 1 if k < 4 else -1
    return tuple(out)


def to_field(a):
    return Q8.element(a)


REFERENCE_GATES = {
    "x": (((ZERO, UNIT), (UNIT, ZERO)), 1),
    "y": (((ZERO, MINUS_I), (I_UNIT, ZERO)), 1),
    "z": (((UNIT, ZERO), (ZERO, MINUS)), 1),
    "h": (((UNIT, UNIT), (UNIT, MINUS)), 2),
    "s": (((UNIT, ZERO), (ZERO, I_UNIT)), 1),
    "t": (((UNIT, ZERO), (ZERO, z_power(1))), 1),
    "u1": (((UNIT, I_UNIT), (I_UNIT, UNIT)), 2),
    "cz": (((UNIT, ZERO, ZERO, ZERO), (ZERO, UNIT, ZERO, ZERO), (ZERO, ZERO, UNIT, ZERO),
            (ZERO, ZERO, ZERO, MINUS)), 1),
    "cnot": (((UNIT, ZERO, ZERO, ZERO), (ZERO, UNIT, ZERO, ZERO), (ZERO, ZERO, ZERO, UNIT),
              (ZERO, ZERO, UNIT, ZERO)), 1),
    "swap": (((UNIT, ZERO, ZERO, ZERO), (ZERO, ZERO, UNIT, ZERO), (ZERO, UNIT, ZERO, ZERO),
              (ZERO, ZERO, ZERO, UNIT)), 1),
    "sqrt_iswap": (((ROOT_TWO, ZERO, ZERO, ZERO), (ZERO, UNIT, I_UNIT, ZERO), (ZERO, I_UNIT, UNIT, ZERO),
                    (ZERO, ZERO, ZERO, ROOT_TWO)), 2),
}
TWO_QUBIT = ("cz", "cnot", "swap", "sqrt_iswap")


class DenseReference:
    """2^n amplitudes in Z[zeta_8]; bit q of a basis index is qubit q."""

    def __init__(self, n):
        self.n = n
        self.amplitudes = [UNIT] + [ZERO] * ((1 << n) - 1)
        self.scale = 1

    def one(self, q, matrix, scale):
        bit = 1 << q
        amps = self.amplitudes
        for index in range(1 << self.n):
            if not index & bit:
                a0, a1 = amps[index], amps[index | bit]
                amps[index] = z_add(z_mul(matrix[0][0], a0), z_mul(matrix[0][1], a1))
                amps[index | bit] = z_add(z_mul(matrix[1][0], a0), z_mul(matrix[1][1], a1))
        self.scale *= scale

    def two(self, qa, qb, matrix, scale):
        ba, bb = 1 << qa, 1 << qb
        amps = self.amplitudes
        for index in range(1 << self.n):
            if not index & ba and not index & bb:
                slots = (index, index | bb, index | ba, index | ba | bb)
                values = [amps[j] for j in slots]
                for r in range(4):
                    total = ZERO
                    for c in range(4):
                        if values[c] != ZERO and matrix[r][c] != ZERO:
                            total = z_add(total, z_mul(matrix[r][c], values[c]))
                    amps[slots[r]] = total
        self.scale *= scale

    def apply(self, name, qubits, params):
        if name == "phase":
            matrix, scale = ((UNIT, ZERO), (ZERO, z_power(params[0]))), 1
        else:
            matrix, scale = REFERENCE_GATES[name]
        if len(qubits) == 1:
            self.one(qubits[0], matrix, scale)
        else:
            self.two(qubits[0], qubits[1], matrix, scale)


def _register_gate(name, qubits, params):
    """The same gate in the form accepted by evaluate_circuit."""
    if name in ("u1", "sqrt_iswap"):
        matrix, scale = REFERENCE_GATES[name]
        return ("unitary", qubits, ([[to_field(v) for v in row] for row in matrix], scale))
    return (name, qubits, params)


def _family():
    """A deterministic family of circuits on 1 to 10 qubits from an integer recurrence (no randomness)."""
    menu = ("h", "t", "cnot", "s", "cz", "x", "phase", "swap", "y", "sqrt_iswap", "z", "u1", "h", "t", "cnot")
    circuits = []
    state = 2026
    for n in (1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 10):
        gates = []
        two_qubit_budget = n + 1
        for _ in range(3 * n + 2):
            state = (state * 1103515245 + 12345) % (1 << 31)
            name = menu[state % len(menu)]
            a = (state >> 8) % n
            if name in TWO_QUBIT and (n == 1 or two_qubit_budget == 0):
                name = "t" if name in ("cz", "swap") else "h"
            if name in TWO_QUBIT:
                two_qubit_budget -= 1
                distance = 1 + (state >> 16) % min(3, n - 1)
                b = a + distance if a + distance < n else a - distance
                if b < 0:
                    b = a + 1 if a + 1 < n else a - 1
                qubits = (a, b) if (state >> 20) & 1 else (b, a)
                gates.append((name, qubits, ()))
            elif name == "phase":
                gates.append((name, (a,), ((state >> 12) % 8,)))
            else:
                gates.append((name, (a,), ()))
        circuits.append((n, gates))
    circuits.append((8, _layered(8, 3)))
    circuits.append((10, _layered(10, 3)))
    return circuits


def _layered(n, depth):
    """Brick layers of sqrt(iSWAP) and CNOT with H, T, a phase and a CZ across the register."""
    gates = []
    for layer in range(depth):
        gates += [("h", (q,), ()) for q in range(n) if (q + layer) % 3 != 0]
        gates += [("t", (q,), ()) for q in range(n) if q % 2 == layer % 2]
        if layer % 2 == 0:
            gates += [("sqrt_iswap", (q, q + 1), ()) for q in range(0, n - 1, 2)]
        else:
            gates += [("cnot", (q + 1, q), ()) for q in range(1, n - 1, 2)]
        gates.append(("cz", (0, n - 1), ()))
        gates.append(("phase", (layer % n,), (3,)))
    return gates


def _run(n, gates):
    reference = DenseReference(n)
    for name, qubits, params in gates:
        reference.apply(name, qubits, params)
    register = evaluate_circuit(n, [_register_gate(*gate) for gate in gates], field=F8)
    return reference, register


def _digits(index, n):
    return tuple((index >> q) & 1 for q in range(n))


def _raises(exception, function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except exception as error:
        return error
    raise AssertionError(f"{function!r} did not raise {exception.__name__}")


# ---------------------------------------------------------------------------------------------
# Agreement with the dense reference
# ---------------------------------------------------------------------------------------------

def test_every_amplitude_matches_the_dense_reference():
    family = _family()
    assert any("t" == name for _, gates in family for name, _, _ in gates)
    largest = 1
    inverse_root_two = F8.div(to_field(ROOT_TWO), F8.from_int(2))
    for n, gates in family:
        reference, register = _run(n, gates)
        largest = max((largest,) + register.bond_dimensions())
        assert register.num_sites == n
        assert register.scale == reference.scale
        assert register.is_normalized()
        dense = register.to_dense()
        for index, value in enumerate(reference.amplitudes):
            assert F8.eq(dense[_digits(index, n)], to_field(value))
        checked = range(1 << n) if n <= 6 else range(0, 1 << n, (1 << n) // 12 + 1)
        halvings = reference.scale.bit_length() - 1
        for index in checked:
            expected = to_field(reference.amplitudes[index])
            amplitude = register.amplitude(index)
            assert amplitude == ExactAmplitude(F8, expected, reference.scale)
            normalised = expected
            for _ in range(halvings):
                normalised = F8.mul(normalised, inverse_root_two)
            assert F8.eq(amplitude.to_field_element(), normalised)
            assert register.amplitude(_digits(index, n)) == amplitude
            assert register.amplitude("".join(str(d) for d in _digits(index, n))) == amplitude
    assert largest == 32


def test_bond_dimensions_are_the_exact_schmidt_ranks():
    for n, gates in _family():
        if n > 8:
            continue
        reference, register = _run(n, gates)
        ranks = []
        for cut in range(1, n):
            rows, columns = 1 << cut, 1 << (n - cut)
            entries = [to_field(reference.amplitudes[r + (c << cut)]) for r in range(rows) for c in range(columns)]
            ranks.append(rank(ExactTensor(F8, (rows, columns), entries)))
        assert register.bond_dimensions() == tuple(ranks)


def test_marginal_probabilities_match_the_dense_reference():
    for n, gates in _family():
        if n > 7:
            continue
        reference, register = _run(n, gates)
        probabilities = [F8.div(F8.mul(to_field(a), F8.conj(to_field(a))), F8.from_int(reference.scale))
                         for a in reference.amplitudes]
        for q in range(n):
            marginals = register.marginal_probabilities(q)
            for b in (0, 1):
                expected = F8.zero
                for index, p in enumerate(probabilities):
                    if (index >> q) & 1 == b:
                        expected = F8.add(expected, p)
                assert F8.eq(marginals[b], expected)
                assert F8.eq(register.marginal_probability(q, b), expected)
            assert F8.eq(F8.add(marginals[0], marginals[1]), F8.one)
        total = F8.zero
        for index in range(1 << n):
            total = F8.add(total, register.probability(index))
        assert F8.eq(total, F8.one)


def test_clifford_circuits_agree_with_the_stabilizer_tableau():
    state = 99
    for n in (2, 3, 4, 5, 6, 7, 8):
        circuit = CliffordCircuit()
        circuit.allocate(n)
        gates = []
        for _ in range(4 * n):
            state = (state * 1103515245 + 12345) % (1 << 31)
            name = ("h", "s", "x", "y", "z", "cnot", "cnot", "h")[state % 8]
            a = (state >> 8) % n
            qubits = (a, (a + 1 + (state >> 16) % (n - 1)) % n) if name == "cnot" else (a,)
            getattr(circuit, name)(*qubits)
            gates.append((name, qubits, ()))
        register = evaluate_circuit(n, gates)
        tableau = circuit.evaluate()
        support = tableau.outcome_support(range(n))
        for index in range(1 << n):
            expected = support.uniform_probability if support.contains(index) else 0
            assert register.probability(index) == expected
        for q in range(n):
            probabilities = tableau.probabilities(q)
            assert register.marginal_probabilities(q) == (probabilities[0], probabilities[1])


def test_clifford_agreement_on_a_wider_register():
    n = 32
    circuit = CliffordCircuit()
    register_qubits = circuit.allocate(n)
    gates = [("h", (q,), ()) for q in register_qubits if q % 2 == 0]
    gates += [("cnot", (q, q + 1), ()) for q in range(0, n - 1, 2)]
    for q in range(1, n, 3):
        gates += [("s", (q,), ()), ("h", (q,), ())]
    gates += [("cnot", (q + 1, q), ()) for q in range(1, n - 1, 2)]
    gates += [("y", (q,), ()) for q in range(0, n, 5)]
    for name, qubits, _ in gates:
        getattr(circuit, name)(*qubits)
    register = evaluate_circuit(circuit.num_qubits, gates)
    tableau = circuit.evaluate()
    support = tableau.outcome_support(range(n))
    assert register.num_sites == n and 0 < support.dimension < n
    for q in range(n):
        probabilities = tableau.probabilities(q)
        assert register.marginal_probabilities(q) == (probabilities[0], probabilities[1])
    members = []
    for mask in range(12):
        vector = support.offset
        for i, generator in enumerate(support.basis):
            if (mask >> i) & 1:
                vector ^= generator
        members.append(vector)
    for index in members:
        assert register.probability(index) == support.uniform_probability
    outside = [support.offset ^ (1 << q) for q in range(n) if not support.contains(support.offset ^ (1 << q))]
    assert outside
    for index in outside:
        assert register.probability(index) == 0


# ---------------------------------------------------------------------------------------------
# Gates, conventions and validation
# ---------------------------------------------------------------------------------------------

def test_named_gates_and_symbolic_hadamard_normalisation():
    register = ExactMPS(1)
    register.h(0)
    assert register.scale == 2
    assert register.amplitude("0") == ExactAmplitude(F8, 1, 2)
    assert register.amplitude("1") == ExactAmplitude(F8, 1, 2)
    register.h(0)
    assert register.scale == 4 and register.amplitude("0") == ExactAmplitude(F8, 1)
    assert register.amplitude("1").is_zero()
    register.x(0).t(0)
    assert register.amplitude("1") == ExactAmplitude(F8, F8.zeta(1))
    register.s(0).z(0).y(0)
    # Y Z S T X H H |0> = Y Z S T |1> = Y (-i zeta |1>) = -i zeta (-i) |0> = -zeta |0>
    assert register.amplitude("0") == ExactAmplitude(F8, F8.neg(F8.zeta(1)))
    register.phase(0, 3)
    assert register.amplitude("0") == ExactAmplitude(F8, F8.neg(F8.zeta(1)))
    register.x(0).phase(0, 3)
    assert register.amplitude("1") == ExactAmplitude(F8, F8.neg(F8.zeta(4)))


def test_two_qubit_gate_orientation_and_routing():
    for control, target in ((0, 1), (1, 0), (0, 3), (3, 0), (1, 4), (4, 2)):
        register = ExactMPS(5)
        register.x(control).cnot(control, target)
        expected = [0] * 5
        expected[control] = expected[target] = 1
        assert register.probability(tuple(expected)) == 1
        assert register.bond_dimensions() == (1, 1, 1, 1)
    register = ExactMPS(4).h(0).cnot(0, 3)
    assert register.bond_dimensions() == (2, 2, 2)
    assert register.probability("1001") == Fraction(1, 2) and register.probability("1000") == 0
    register = ExactMPS(3).x(0).swap(0, 2)
    assert register.probability("001") == 1
    reference, register = _run(5, [("h", (4,), ()), ("sqrt_iswap", (4, 0), ()), ("t", (0,), ()),
                                   ("cz", (0, 3), ()), ("u1", (2,), ()), ("sqrt_iswap", (1, 3), ())])
    dense = register.to_dense()
    for index, value in enumerate(reference.amplitudes):
        assert F8.eq(dense[_digits(index, 5)], to_field(value))


def test_qudit_registers():
    field = cyclotomic(3)
    w = field.zeta(1)
    w2 = field.zeta(2)
    fourier = [[1, 1, 1], [1, w, w2], [1, w2, w]]
    csum = [[1 if (t1 == s1 and t2 == (s1 + s2) % 3) else 0 for s1 in range(3) for s2 in range(3)]
            for t1 in range(3) for t2 in range(3)]
    register = ExactMPS(3, 3, field)
    register.apply_one(0, fourier, 3).apply_two(0, 1, csum).apply_two(1, 2, csum).apply_one(2, fourier, 3)
    assert register.bond_dimensions() == (3, 3)
    assert register.is_normalized()
    amplitudes = {}
    for a in range(3):
        b, c = a, a
        for k in range(3):
            key = (a, b, k)
            amplitudes[key] = field.add(amplitudes.get(key, field.zero), field.zeta(c * k % 3))
    for a in range(3):
        for b in range(3):
            for k in range(3):
                expected = amplitudes.get((a, b, k), field.zero)
                assert register.amplitude((a, b, k)) == ExactAmplitude(field, expected, 9)
    mixed = ExactMPS(3, (2, 3, 2), F8)
    mixed.h(0).cnot(0, 2).apply_one(1, [[0, 0, 1], [1, 0, 0], [0, 1, 0]])
    assert mixed.local_dims == (2, 3, 2)
    assert mixed.probability((1, 1, 1)) == Fraction(1, 2) and mixed.probability((0, 1, 0)) == Fraction(1, 2)
    assert mixed.bond_dimensions() == (2, 2)
    assert mixed.amplitude(1 + 2 * 1 + 6 * 1) == mixed.amplitude((1, 1, 1))
    _raises(ValueError, mixed.h, 1)
    _raises(ValueError, mixed.swap, 0, 1)


def test_gate_validation():
    register = ExactMPS(3)
    _raises(ValueError, register.apply_one, 0, [[1, 1], [1, 1]], 2)
    _raises(ValueError, register.apply_one, 0, [[1, 1], [1, -1]], 1)
    _raises(ValueError, register.apply_one, 0, [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    _raises(ValueError, register.apply_two, 0, 0, [[1, 0], [0, 1]])
    _raises(ValueError, register.apply_one, 3, [[1, 0], [0, 1]])
    _raises(TypeError, register.h, True)
    _raises(ValueError, register.apply, "toffoli", (0, 1, 2))
    _raises(ValueError, register.apply, "cnot", (0,))
    _raises(ValueError, register.apply, "h", (0,), (1,))
    _raises(ValueError, register.apply_one, 0, [[1, 0], [0, 1]], 0)
    _raises(ValueError, ExactMPS, 0)
    _raises(ValueError, ExactMPS, 2, 1)
    _raises(ValueError, ExactMPS, 2, max_bond=0)
    rational = ExactMPS(2, field=QQ)
    rational.h(0).cnot(0, 1)
    assert rational.probability("11") == Fraction(1, 2)
    _raises(ValueError, rational.t, 0)
    _raises(ValueError, rational.s, 0)
    _raises(ValueError, ExactMPS(1).phase, 0, 1, 16)
    _raises(ValueError, register.amplitude, "012")
    _raises(ValueError, register.amplitude, 8)
    _raises(ValueError, register.amplitude, (0, 1))
    assert register.scale == 1 and register.bond_dimensions() == (1, 1)


def test_evaluate_circuit_parsing_and_field_choice():
    gates = [("h", 0), ("phase", (0,), (3, 16)), ("cnot", [0, 1])]
    register = evaluate_circuit(2, gates)
    assert register.field == cyclotomic(16)
    assert register.amplitude("11") == ExactAmplitude(cyclotomic(16), cyclotomic(16).zeta(3), 2)
    third = cyclotomic(3).zeta(1)
    unitary = [[1, 0], [0, third]]
    assert evaluate_circuit(1, [("unitary", (0,), (unitary,))]).field == cyclotomic(24)
    assert evaluate_circuit(1, [("unitary", (0,), {"matrix": unitary, "scale": 1})]).field == cyclotomic(24)
    tensor_gate = ExactTensor.from_nested(cyclotomic(3), [[0, third], [1, 0]])
    lifted = evaluate_circuit(1, [("unitary", (0,), (tensor_gate,))])
    assert lifted.field == cyclotomic(24)
    assert lifted.amplitude("1") == ExactAmplitude(cyclotomic(24), 1)
    assert lifted.apply("unitary", 0, (tensor_gate,)).amplitude("1").is_zero()
    assert lifted.amplitude("0") == ExactAmplitude(cyclotomic(24), cyclotomic(24).coerce(third))
    _raises(ValueError, evaluate_circuit, 2, [("h",)])
    _raises(ValueError, evaluate_circuit, 2, [("rx", (0,), ())])
    _raises(ValueError, evaluate_circuit, 2, [("h", (0,), "x")])
    _raises(ValueError, evaluate_circuit, 0, [])
    assert evaluate_circuit(3, []).bond_dimensions() == (1, 1)
    assert DEFAULT_MAX_BOND == 64


def test_exact_amplitude_equality_is_numeric():
    root_two = F8.positive_sqrt(2)
    half_root_two = F8.div(root_two, F8.from_int(2))
    assert ExactAmplitude(F8, 1, 2) == ExactAmplitude(F8, half_root_two)
    assert ExactAmplitude(F8, 1, 2) != ExactAmplitude(F8, F8.neg(half_root_two))
    assert ExactAmplitude(F8, 2, 8) == ExactAmplitude(F8, 1, 2)
    assert ExactAmplitude(F8, 1, Fraction(1, 2)) == ExactAmplitude(F8, root_two)
    assert hash(ExactAmplitude(F8, 1, 2)) == hash(ExactAmplitude(F8, half_root_two))
    assert ExactAmplitude(QQ, 1, 2) != ExactAmplitude(QQ, Fraction(1, 2))
    assert ExactAmplitude(QQ, 3, 9) == ExactAmplitude(QQ, 1)
    assert ExactAmplitude(QQ, 0, 2) == ExactAmplitude(QQ, 0, 3)
    assert ExactAmplitude(F8, 1, 2).probability() == Fraction(1, 2)
    assert ExactAmplitude(F8, 1, 3) != ExactAmplitude(F8, 1, 2)
    _raises(ValueError, ExactAmplitude(QQ, 1, 2).to_field_element)
    _raises(ValueError, ExactAmplitude, F8, 1, 0)
    _raises(ValueError, ExactAmplitude, F8, 1, -2)


def test_max_bond_refuses_instead_of_truncating():
    register = ExactMPS(4, max_bond=2)
    register.h(0).h(1).cnot(1, 2)
    before = [register.amplitude(index) for index in range(16)]
    error = _raises(ValueError, register.cnot, 0, 3)
    message = str(error)
    assert "exact rank 4" in message and "max_bond = 2" in message and "between sites 1 and 2" in message
    assert register.bond_dimensions() == (1, 2, 1)
    assert [register.amplitude(index) for index in range(16)] == before
    assert register.scale == 4
    gates = [("h", (0,), ()), ("h", (1,), ()), ("cnot", (1, 2), ()), ("cnot", (0, 3), ())]
    error = _raises(ValueError, evaluate_circuit, 4, gates, 3)
    assert "exact rank 4" in str(error)
    accepted = evaluate_circuit(4, gates, 4)
    assert accepted.bond_dimensions() == (2, 4, 2)
    assert accepted.probability("1111") == Fraction(1, 4)
    adjacent = ExactMPS(2, max_bond=1).h(0)
    error = _raises(ValueError, adjacent.cnot, 0, 1)
    assert "between sites 0 and 1" in str(error) and "exact rank 2" in str(error)
    assert adjacent.bond_dimensions() == (1,) and adjacent.probability("10") == Fraction(1, 2)


def test_determinism_and_tensor_train_view():
    n, gates = _family()[-3]
    first = evaluate_circuit(n, [_register_gate(*gate) for gate in gates], field=F8)
    second = evaluate_circuit(n, [_register_gate(*gate) for gate in gates], field=F8)
    for k in range(n):
        assert first.core(k) == second.core(k)
    train = first.as_tensor_train()
    assert train.ranks == (1,) + first.bond_dimensions() + (1,)
    assert train.compress().ranks == train.ranks
    assert F8.eq(train.norm_squared(), first.norm_squared())
    copy = first.copy().h(0)
    assert copy.scale == 2 * first.scale and first.core(0) == second.core(0)
