import sys
from fractions import Fraction
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.algebra import CyclotomicField  # noqa: E402
from turing.algorithms.clifford import (  # noqa: E402
    CliffordCircuit,
    PauliOperator,
    StabilizerTableau,
    ghz_circuit,
    paulis_commute,
)

F8 = CyclotomicField(8)
ZETA8 = F8.zeta(1)
IMAGINARY_UNIT = ZETA8 ** 2
ROOT_TWO = ZETA8 - ZETA8 ** 3
INVERSE_ROOT_TWO = ROOT_TWO / 2


class DenseState:
    """Exact dense reference: 2^n amplitudes in Q(zeta_8); qubit q is bit q of the index."""

    def __init__(self, n):
        self.n = n
        self.amplitudes = [F8.one] + [F8.zero] * ((1 << n) - 1)

    def h(self, q):
        bit = 1 << q
        out = list(self.amplitudes)
        for index in range(1 << self.n):
            if not index & bit:
                a0, a1 = self.amplitudes[index], self.amplitudes[index | bit]
                out[index] = (a0 + a1) * INVERSE_ROOT_TWO
                out[index | bit] = (a0 - a1) * INVERSE_ROOT_TWO
        self.amplitudes = out

    def s(self, q):
        self.amplitudes = [a * IMAGINARY_UNIT if (i >> q) & 1 else a for i, a in enumerate(self.amplitudes)]

    def z(self, q):
        self.amplitudes = [-a if (i >> q) & 1 else a for i, a in enumerate(self.amplitudes)]

    def x(self, q):
        self.amplitudes = [self.amplitudes[i ^ (1 << q)] for i in range(1 << self.n)]

    def y(self, q):
        out = []
        for i in range(1 << self.n):
            partner = self.amplitudes[i ^ (1 << q)]
            out.append(partner * IMAGINARY_UNIT if (i >> q) & 1 else -(partner * IMAGINARY_UNIT))
        self.amplitudes = out

    def cnot(self, c, t):
        self.amplitudes = [self.amplitudes[i ^ (1 << t)] if (i >> c) & 1 else self.amplitudes[i]
                           for i in range(1 << self.n)]

    def basis_probabilities(self):
        return [a.abs2().to_rational() for a in self.amplitudes]

    def probability(self, q, b, basis_probabilities=None):
        if basis_probabilities is None:
            basis_probabilities = self.basis_probabilities()
        return sum(p for i, p in enumerate(basis_probabilities) if (i >> q) & 1 == b)

    def collapse(self, q, b):
        p = self.probability(q, b)
        assert p in (Fraction(1, 2), Fraction(1))
        factor = ROOT_TWO if p == Fraction(1, 2) else F8.one
        self.amplitudes = [a * factor if (i >> q) & 1 == b else F8.zero for i, a in enumerate(self.amplitudes)]

    def apply_pauli(self, pauli):
        """(-1)^sign i^|x & z| X^x Z^z applied exactly; phases are powers of zeta_8."""
        base = 2 * (pauli.x & pauli.z).bit_count() + 4 * pauli.sign
        out = [F8.zero] * (1 << self.n)
        for i, a in enumerate(self.amplitudes):
            if a:
                exponent = base + 4 * ((pauli.z & i).bit_count() & 1)
                out[i ^ pauli.x] = _times_zeta8_power(a, exponent)
        return out


def _times_zeta8_power(element, exponent):
    """zeta_8^e * a by rotating power-basis coordinates (zeta_8^4 = -1); exact, no general product."""
    coefficients = [Fraction(0)] * 4
    for k, c in enumerate(element.coefficients):
        if c:
            position = k + exponent % 8
            coefficients[position % 4] += -c if (position // 4) % 2 else c
    return F8.element(coefficients)


FIXED_CIRCUITS = (
    (1, (("h", 0),)),
    (1, (("h", 0), ("s", 0))),
    (1, (("x", 0), ("h", 0), ("y", 0), ("s", 0), ("z", 0))),
    (2, (("h", 0), ("cnot", 0, 1))),
    (2, (("h", 0), ("s", 0), ("cnot", 0, 1), ("h", 1), ("y", 1))),
    (3, (("h", 0), ("cnot", 0, 1), ("cnot", 1, 2))),
    (3, (("h", 0), ("h", 1), ("cnot", 0, 2), ("s", 2), ("cnot", 1, 2), ("h", 0), ("y", 1), ("z", 2),
         ("s", 0), ("h", 2))),
    (3, (("x", 1), ("h", 2), ("cnot", 2, 1), ("s", 1), ("h", 1), ("cnot", 1, 0), ("y", 0), ("h", 0),
         ("s", 2), ("cnot", 0, 2))),
    # Y-heavy stabilizer groups: products such as XX * YY = -ZZ carry a phase i^2.
    (2, (("h", 0), ("cnot", 0, 1), ("s", 0), ("s", 1), ("h", 0), ("h", 1))),
    (2, (("h", 0), ("cnot", 0, 1), ("s", 0), ("s", 1), ("h", 0), ("h", 1), ("s", 1))),
    (2, (("h", 0), ("s", 0), ("h", 1), ("cnot", 0, 1), ("s", 1), ("h", 1), ("cnot", 1, 0), ("s", 0))),
    (3, (("h", 0), ("cnot", 0, 1), ("cnot", 1, 2), ("s", 0), ("s", 1), ("s", 2), ("h", 0), ("h", 1),
         ("h", 2))),
    (3, (("h", 0), ("h", 1), ("h", 2), ("s", 0), ("cnot", 0, 1), ("s", 1), ("cnot", 1, 2), ("s", 2),
         ("h", 2), ("cnot", 2, 0), ("s", 0), ("h", 1))),
)


def _generated_circuits():
    """Deterministic gate sequences from a fixed integer recurrence (no randomness)."""
    circuits = []
    state = 12345
    for n in (2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 4, 4, 5):
        gates = []
        for _ in range(6 * n):
            state = (state * 1103515245 + 12345) % (1 << 31)
            kind = ("h", "s", "x", "y", "z", "cnot", "cnot", "s", "h")[state % 9]
            a = (state >> 8) % n
            if kind == "cnot":
                b = (a + 1 + (state >> 16) % (n - 1)) % n
                gates.append(("cnot", a, b))
            else:
                gates.append((kind, a))
        circuits.append((n, tuple(gates)))
    return circuits


def _build(n, gates):
    circuit = CliffordCircuit()
    circuit.allocate(n)
    dense = DenseState(n)
    for name, *qubits in gates:
        getattr(circuit, name)(*qubits)
        getattr(dense, name)(*qubits)
    return circuit, dense


def _dense_sign(dense, pauli, negated=None):
    image = dense.apply_pauli(pauli)
    if image == dense.amplitudes:
        return 0
    if image == (negated if negated is not None else [-a for a in dense.amplitudes]):
        return 1
    return None


def _assert_consistent(tableau, dense):
    n = tableau.num_qubits
    basis_probabilities = dense.basis_probabilities()
    for q in range(n):
        probabilities = tableau.probabilities(q)
        for b in (0, 1):
            assert probabilities[b] == dense.probability(q, b, basis_probabilities)
    for generator in tableau.stabilizer_generators():
        assert dense.apply_pauli(generator) == dense.amplitudes
    joint = tableau.outcome_support(range(n))
    reversed_order = list(reversed(range(n)))
    marginal = tableau.outcome_support(reversed_order)
    for index, probability in enumerate(basis_probabilities):
        assert probability == (joint.uniform_probability if joint.contains(index) else 0)
        permuted = sum(((index >> q) & 1) << i for i, q in enumerate(reversed_order))
        assert probability == (marginal.uniform_probability if marginal.contains(permuted) else 0)
    assert tableau.is_valid()


def _assert_membership_matches_dense(tableau, dense):
    n = tableau.num_qubits
    negated = [-a for a in dense.amplitudes]
    for x in range(1 << n):
        for z in range(1 << n):
            pauli = PauliOperator(n, x, z, 0)
            assert tableau.stabilizer_sign(pauli) == _dense_sign(dense, pauli, negated)


def test_pauli_products_match_dense_matrices():
    n = 2
    paulis = [PauliOperator(n, x, z, 0) for x in range(4) for z in range(4)]
    for p in paulis:
        for q in paulis:
            if not paulis_commute(p, q):
                continue
            product = p * q
            for index in range(1 << n):
                state = DenseState(n)
                state.amplitudes = [F8.one if i == index else F8.zero for i in range(1 << n)]
                state.amplitudes = state.apply_pauli(q)
                composed = state.apply_pauli(p)
                single = DenseState(n)
                single.amplitudes = [F8.one if i == index else F8.zero for i in range(1 << n)]
                assert composed == single.apply_pauli(product)
    assert PauliOperator.from_label("ZX") * PauliOperator.from_label("XZ") == PauliOperator.from_label("+YY")


def test_small_circuits_match_the_dense_q_zeta8_evaluation():
    for n, gates in FIXED_CIRCUITS + tuple(_generated_circuits()):
        circuit, dense = _build(n, gates)
        tableau = circuit.evaluate()
        assert tableau.num_qubits == n
        _assert_consistent(tableau, dense)
        if n <= 3:
            _assert_membership_matches_dense(tableau, dense)
        patterns = range(1 << n) if n <= 3 else (0, (1 << n) - 1, 0b0101, 0b1010)
        for pattern in patterns:
            branch_tableau = tableau.copy()
            branch_dense = DenseState(n)
            branch_dense.amplitudes = list(dense.amplitudes)
            for q in range(n):
                probabilities = branch_tableau.probabilities(q)
                wanted = (pattern >> q) & 1
                choice = wanted if probabilities[wanted] else 1 - wanted
                outcome = branch_tableau.measure(q, choose=choice if not probabilities[choice] == 1 else None)
                assert outcome.outcome == choice
                assert outcome.probability == branch_dense.probability(q, choice)
                assert outcome.deterministic == (outcome.probability == 1)
                branch_dense.collapse(q, choice)
                _assert_consistent(branch_tableau, branch_dense)
                if n <= 3:
                    _assert_membership_matches_dense(branch_tableau, branch_dense)


def _check_ghz(width):
    circuit = ghz_circuit(width)
    tableau = circuit.evaluate()
    n = tableau.num_qubits
    assert n == circuit.num_qubits == width
    assert tableau.tableau_bits == 2 * n * (2 * n + 1)
    assert tableau.probabilities(0) == {0: Fraction(1, 2), 1: Fraction(1, 2)}
    for i in range(n - 1):
        neighbours = PauliOperator.from_sparse(n, {i: "Z", i + 1: "Z"})
        assert tableau.stabilizer_sign(neighbours) == 0
    assert tableau.contains(PauliOperator(n, (1 << n) - 1, 0, 0))
    support = tableau.outcome_support(range(n))
    assert support.dimension == 1 and support.uniform_probability == Fraction(1, 2)
    assert support.contains(0) and support.contains((1 << n) - 1)
    assert tableau.stabilizers_commute()
    assert tableau.stabilizer_rank() == n
    for choice in (0, 1):
        branch = tableau.copy()
        outcome = branch.measure(0, choose=choice)
        assert outcome.probability == Fraction(1, 2) and not outcome.deterministic
        assert branch.stabilizer_sign(PauliOperator.from_sparse(n, {0: "Z"})) == choice
        assert all(branch.is_deterministic(q) for q in range(n))
        collapsed = branch.outcome_support(range(n))
        assert collapsed.dimension == 0 and collapsed.uniform_probability == 1
        assert collapsed.offset == (0 if choice == 0 else (1 << n) - 1)
        for q in (1, n // 2, n - 1):
            assert branch.probabilities(q) == {choice: Fraction(1), 1 - choice: Fraction(0)}
        assert branch.stabilizers_commute() and branch.stabilizer_rank() == n
    return tableau


def test_ghz_1000_qubits():
    tableau = _check_ghz(1000)
    generators = tableau.stabilizer_generators()
    assert all(paulis_commute(p, q) for i, p in enumerate(generators) for q in generators[i + 1:])


def test_ghz_2500_qubits():
    _check_ghz(2500)


def test_measurement_rules_and_errors():
    tableau = StabilizerTableau(2)
    tableau.h(0).cnot(0, 1)
    try:
        tableau.measure(0)
    except ValueError as error:
        assert "choose" in str(error)
    else:
        raise AssertionError("uniform outcomes need an explicit branch")
    tableau.measure(0, choose=1)
    try:
        tableau.measure(1, choose=0)
    except ValueError:
        pass
    else:
        raise AssertionError("outcome 0 of qubit 1 has probability 0")
    assert tableau.measure(1).outcome == 1
    for bad in (lambda: StabilizerTableau(0), lambda: StabilizerTableau(2).cnot(1, 1),
                lambda: StabilizerTableau(2).h(2), lambda: CliffordCircuit().h(0)):
        try:
            bad()
        except ValueError:
            pass
        else:
            raise AssertionError("invalid register use must fail")


def test_pauli_operators():
    p = PauliOperator.from_label("-XZY")
    assert p.label() == "-XZY" and p.weight == 3
    q = PauliOperator.from_label("+ZZI")
    assert not paulis_commute(p, q)
    assert PauliOperator.from_label("XX") * PauliOperator.from_label("ZZ") == PauliOperator.from_label("-YY")
    assert PauliOperator.from_sparse(3, {0: "X", 2: "Y"}) == PauliOperator.from_label("XIY")
    try:
        PauliOperator.from_label("XQ")
    except ValueError:
        pass
    else:
        raise AssertionError("Q is not a Pauli symbol")


def test_gate_identities_on_the_tableau():
    def same_state(a, b):
        return all(b.contains(g) for g in a.stabilizer_generators())

    base = StabilizerTableau(3)
    base.h(0).cnot(0, 2).s(2).h(1)
    for sequence, equivalent in (
        ((("h", 0), ("h", 0)), ()),
        ((("s", 1), ("s", 1), ("s", 1), ("s", 1)), ()),
        ((("h", 2), ("s", 2), ("s", 2), ("h", 2)), (("x", 2),)),
        ((("s", 0), ("s", 0)), (("z", 0),)),
        ((("x", 1), ("z", 1)), (("z", 1), ("x", 1))),
    ):
        left = base.copy()
        right = base.copy()
        for name, *qubits in sequence:
            getattr(left, name)(*qubits)
        for name, *qubits in equivalent:
            getattr(right, name)(*qubits)
        assert same_state(left, right) and same_state(right, left)
