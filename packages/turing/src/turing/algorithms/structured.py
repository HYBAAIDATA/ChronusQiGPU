"""Structured-oracle algorithms evaluated exactly on the stabilizer tableau.

Every instance here is a Clifford circuit (Deutsch-Jozsa and Bernstein-Vazirani
with affine oracles f(x) = a.x xor b, Simon with a GF(2)-linear oracle
f(x) = A x) or a dyadic-phase circuit (phase estimation of a / 2^t with the
semiclassical inverse QFT). That is why they evaluate exactly at thousands of
qubits: the tableau has 2n(2n + 1) bits, and the dyadic phase is carried as an
integer exponent modulo 2^t. Register sizes are read from the circuits.

Out of scope at this size: Shor's modular exponentiation and general
non-Clifford circuits do not fold this way (order finding for an n-bit
modulus needs an exact sum over Q = 2^(2n) terms), and optimal Grover search
over N = 2^2500 items needs about (pi/4) * 2^1250 iterations. See
docs/algorithms.md for the figures.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Optional

from .clifford import CliffordCircuit, StabilizerTableau
from .gf2 import AffineSubspace, nullspace
from .oracles import AffineOracle, LinearOracle

__all__ = [
    "DyadicPhaseEstimate",
    "StructuredBernsteinVaziraniResult",
    "StructuredDeutschJozsaResult",
    "StructuredSimonResult",
    "affine_oracle_circuit",
    "bernstein_vazirani_clifford",
    "deutsch_jozsa_clifford",
    "dyadic_phase_estimation",
    "linear_oracle_circuit",
    "simon_clifford",
    "simon_kernel_matrix",
]


def _require(oracle: object, kind: type) -> None:
    if not isinstance(oracle, kind):
        raise TypeError(f"this structured path needs a {kind.__name__}, which exposes its GF(2) structure; "
                        f"use the dense modules for other oracles")


def affine_oracle_circuit(oracle: AffineOracle) -> tuple[CliffordCircuit, range]:
    """H^n on the data register, the phase oracle as CNOTs onto an ancilla in |->, then H^n."""
    _require(oracle, AffineOracle)
    circuit = CliffordCircuit()
    data = circuit.allocate(oracle.num_inputs)
    ancilla = circuit.allocate(1)[0]
    circuit.x(ancilla)
    circuit.h(ancilla)
    for q in data:
        circuit.h(q)
    bits = oracle.a
    while bits:
        low = bits & -bits
        circuit.cnot(data[low.bit_length() - 1], ancilla)
        bits ^= low
    if oracle.b:
        circuit.x(ancilla)
    for q in data:
        circuit.h(q)
    return circuit, data


@dataclass(frozen=True)
class StructuredDeutschJozsaResult:
    num_qubits: int
    data_qubits: int
    verdict: str
    probability_all_zero: Fraction
    data_support: AffineSubspace


def deutsch_jozsa_clifford(oracle: AffineOracle) -> StructuredDeutschJozsaResult:
    """Verdict and exact probability of 0^n, read from the evaluated tableau."""
    circuit, data = affine_oracle_circuit(oracle)
    tableau = circuit.evaluate()
    support = tableau.outcome_support(list(data))
    probability = support.uniform_probability if support.contains(0) else Fraction(0)
    if probability == 1:
        verdict = "constant"
    elif probability == 0:
        verdict = "balanced"
    else:
        raise ArithmeticError(f"P(0^n) = {probability}; expected exactly 0 or 1 for an affine oracle")
    return StructuredDeutschJozsaResult(num_qubits=tableau.num_qubits, data_qubits=len(data), verdict=verdict,
                                        probability_all_zero=probability, data_support=support)


@dataclass(frozen=True)
class StructuredBernsteinVaziraniResult:
    num_qubits: int
    data_qubits: int
    hidden_string: int
    probability: Fraction
    deterministic_bits: int


def bernstein_vazirani_clifford(oracle: AffineOracle) -> StructuredBernsteinVaziraniResult:
    """Every output bit is deterministic; s is read from the tableau with probability exactly 1."""
    circuit, data = affine_oracle_circuit(oracle)
    tableau = circuit.evaluate()
    deterministic = sum(1 for q in data if tableau.is_deterministic(q))
    support = tableau.outcome_support(list(data))
    if support.dimension != 0 or deterministic != len(data):
        raise ArithmeticError("Bernstein-Vazirani output register is not deterministic")
    return StructuredBernsteinVaziraniResult(num_qubits=tableau.num_qubits, data_qubits=len(data),
                                             hidden_string=support.offset,
                                             probability=support.uniform_probability,
                                             deterministic_bits=deterministic)


def simon_kernel_matrix(s: int, num_inputs: int) -> tuple[int, ...]:
    """Deterministic A over GF(2) with kernel exactly {0, s}.

    A = B (I + s e_k^T) with k the lowest set bit of s and B = I + superdiagonal
    (invertible), so A x = 0 iff x in {0, s}. Row j of A is returned as an int.
    """
    if not isinstance(num_inputs, int) or isinstance(num_inputs, bool) or num_inputs < 1:
        raise ValueError("num_inputs must be a positive int")
    if not isinstance(s, int) or isinstance(s, bool) or not 0 < s < 1 << num_inputs:
        raise ValueError(f"s must be a nonzero vector of {num_inputs} bits")
    k = (s & -s).bit_length() - 1
    projector_rows = [(1 << j) ^ (((s >> j) & 1) << k) for j in range(num_inputs)]
    return tuple(projector_rows[j] ^ projector_rows[j + 1] if j + 1 < num_inputs else projector_rows[j]
                 for j in range(num_inputs))


def linear_oracle_circuit(oracle: LinearOracle) -> tuple[CliffordCircuit, range, range]:
    """H^n on x, y ^= A x as CNOTs, H^n on x."""
    _require(oracle, LinearOracle)
    circuit = CliffordCircuit()
    xreg = circuit.allocate(oracle.num_inputs)
    yreg = circuit.allocate(oracle.num_outputs)
    for q in xreg:
        circuit.h(q)
    for j, row in enumerate(oracle.rows):
        bits = row
        while bits:
            low = bits & -bits
            circuit.cnot(xreg[low.bit_length() - 1], yreg[j])
            bits ^= low
    for q in xreg:
        circuit.h(q)
    return circuit, xreg, yreg


@dataclass(frozen=True)
class StructuredSimonResult:
    num_qubits: int
    register_qubits: int
    support: AffineSubspace
    hidden_period: int
    outcome_probability: Fraction


def simon_clifford(oracle: LinearOracle) -> StructuredSimonResult:
    """Exact first-register support (an affine subspace) from the tableau, then s by elimination.

    Nothing is sampled: the support is derived from the stabilizer group, shown
    to be the orthogonal complement of s (uniform, 2^-(n-1) each), and s is
    recovered as its orthogonal complement by GF(2) elimination.
    """
    _require(oracle, LinearOracle)
    n = oracle.num_inputs
    kernel = nullspace(oracle.rows, n)
    if len(kernel) > 1:
        raise ValueError(f"Simon promise violated: ker A has dimension {len(kernel)}, so f is "
                         f"2^{len(kernel)}-to-1 rather than injective or 2-to-1")
    promised = kernel[0] if kernel else 0
    circuit, xreg, _ = linear_oracle_circuit(oracle)
    tableau: StabilizerTableau = circuit.evaluate()
    support = tableau.outcome_support(list(xreg))
    complement = support.orthogonal_complement()
    if len(complement) > 1 or support.offset != 0:
        raise ArithmeticError("first-register support is not the orthogonal complement of a single vector")
    s = complement[0] if complement else 0
    if s != promised:
        raise ArithmeticError("recovered period disagrees with the kernel of A")
    return StructuredSimonResult(num_qubits=tableau.num_qubits, register_qubits=n, support=support,
                                 hidden_period=s, outcome_probability=support.uniform_probability)


@dataclass(frozen=True)
class DyadicPhaseEstimate:
    numerator: int
    precision_qubits: int
    probability: Fraction
    bit_probabilities: tuple[Fraction, ...]

    @property
    def phase(self) -> Fraction:
        return Fraction(self.numerator, 1 << self.precision_qubits)


def dyadic_phase_estimation(phase: Fraction, precision_qubits: Optional[int] = None) -> DyadicPhaseEstimate:
    """Phase estimation of phi = a / 2^t with the semiclassical inverse QFT.

    After the controlled powers U^(2^k), register qubit k is
    (|0> + zeta^(e_k) |1>)/sqrt(2) with zeta = zeta_(2^t) and e_k = a 2^k mod 2^t.
    The inverse QFT is applied qubit by qubit: bit m of a is read from qubit
    t - 1 - m after the rotation by the exact integer exponent
    (a mod 2^m) 2^(t-1-m) fixed by the bits already read. The residual exponent
    is then 0 or 2^(t-1), i.e. the qubit is |+> or |->, and H gives that bit with
    probability exactly 1. Roots of unity are never evaluated numerically.
    The register size t is read from the denominator of phi unless given.
    """
    if isinstance(phase, bool) or not isinstance(phase, (int, Fraction)):
        raise TypeError("phase must be an exact rational")
    phi = Fraction(phase)
    phi = Fraction(phi.numerator % phi.denominator, phi.denominator)
    denominator = phi.denominator
    needed = denominator.bit_length() - 1
    if 1 << needed != denominator:
        raise ValueError(f"phase {phi} is not dyadic; its denominator is not a power of two")
    t = max(needed, 1) if precision_qubits is None else precision_qubits
    if not isinstance(t, int) or isinstance(t, bool) or t < max(needed, 1):
        raise ValueError(f"precision_qubits must be an int >= {max(needed, 1)}")
    size = 1 << t
    mask = size - 1
    half = size >> 1
    a = phi.numerator * (size // denominator)
    recovered = 0
    bit_probabilities = []
    probability = Fraction(1)
    for m in range(t):
        k = t - 1 - m
        exponent = (a << k) & mask
        correction = (recovered << k) & mask
        residual = (exponent - correction) & mask
        if residual == 0:
            bit = 0
        elif residual == half:
            bit = 1
        else:
            raise ArithmeticError("residual phase is neither 0 nor pi; the phase is not dyadic at this size")
        bit_probabilities.append(Fraction(1))
        probability *= bit_probabilities[-1]
        recovered |= bit << m
    if recovered != a:
        raise ArithmeticError("semiclassical readout disagrees with the eigenphase numerator")
    return DyadicPhaseEstimate(numerator=recovered, precision_qubits=t, probability=probability,
                               bit_probabilities=tuple(bit_probabilities))
