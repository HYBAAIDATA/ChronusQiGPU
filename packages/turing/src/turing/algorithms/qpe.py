"""Quantum phase estimation for exact rational eigenphases.

For an eigenphase phi = a/b and a t-qubit register (T = 2^t) the exact outcome
distribution is P(y) = |(1/T) sum_{j<T} zeta_b^(a j) zeta_T^(-j y)|^2, an element
of the real subfield of Q(zeta_L), L = lcm(b, T). The inner sum runs over an
arithmetic progression of exponents, so |.|^2 is evaluated from closed-form
pairwise-difference counts. When phi * 2^t is an integer y0, P(y0) = 1 exactly.

The F_257 instance uses the permutation unitary U|x> = |g x mod p> on the
multiplicative group of F_257, whose eigenphases are k/256. Because 256 = 2^8,
every eigenphase is recovered with probability exactly 1 by an 8-qubit
register; the register size is computed from p - 1, and g = 3 is checked in
code to have multiplicative order 256 modulo 257.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import lcm

from ..algebra.cyclotomic import CyclotomicElement, CyclotomicField, is_prime, progression_difference_counts
from ..algebra.reduction import multiplicative_order

__all__ = [
    "MultiplyByGeneratorEstimation",
    "PhaseEstimation",
    "PhaseRecovery",
    "estimate_multiply_by_generator",
    "multiply_by_generator_eigenphases",
    "outcome_probability",
    "phase_estimation",
    "recover_phase",
]


def _normalise_phase(phase: object) -> Fraction:
    if isinstance(phase, bool) or not isinstance(phase, (int, Fraction)):
        raise TypeError("phase must be an int or fractions.Fraction (an exact rational)")
    value = Fraction(phase)
    return Fraction(value.numerator % value.denominator, value.denominator)


def _check_register(t: int) -> int:
    if not isinstance(t, int) or isinstance(t, bool) or t < 1:
        raise ValueError(f"register size t must be a positive int, got {t!r}")
    return 1 << t


def _step(phase: Fraction, size: int, y: int, modulus: int) -> int:
    return (phase.numerator * (modulus // phase.denominator) - y * (modulus // size)) % modulus


def outcome_probability(phase: object, t: int, y: int) -> CyclotomicElement:
    """Exact P(y) for eigenphase ``phase`` and a t-qubit register."""
    phi = _normalise_phase(phase)
    size = _check_register(t)
    if not isinstance(y, int) or isinstance(y, bool) or not 0 <= y < size:
        raise ValueError(f"outcome y must lie in 0 .. {size - 1}")
    modulus = lcm(phi.denominator, size)
    field = CyclotomicField(modulus)
    step = _step(phi, size, y, modulus)
    return field.from_exponents(progression_difference_counts(step, size, modulus), denominator=size * size)


@dataclass(frozen=True)
class PhaseEstimation:
    phase: Fraction
    precision_qubits: int
    field: CyclotomicField
    probabilities: tuple[CyclotomicElement, ...]

    def total_probability(self) -> CyclotomicElement:
        total = self.field.zero
        for p in self.probabilities:
            total = total + p
        return total


def phase_estimation(phase: object, t: int) -> PhaseEstimation:
    """Exact outcome distribution over all 2^t register values."""
    phi = _normalise_phase(phase)
    size = _check_register(t)
    modulus = lcm(phi.denominator, size)
    field = CyclotomicField(modulus)
    probabilities = []
    for y in range(size):
        step = _step(phi, size, y, modulus)
        probabilities.append(field.from_exponents(progression_difference_counts(step, size, modulus),
                                                  denominator=size * size))
    return PhaseEstimation(phase=phi, precision_qubits=t, field=field, probabilities=tuple(probabilities))


@dataclass(frozen=True)
class PhaseRecovery:
    outcome: int
    phase: Fraction
    probability: Fraction


def recover_phase(phase: object, t: int) -> PhaseRecovery:
    """Recover phi when phi * 2^t is an integer, verifying P(y0) = 1 exactly."""
    phi = _normalise_phase(phase)
    size = _check_register(t)
    scaled = phi * size
    if scaled.denominator != 1:
        raise ValueError(f"phase {phi} is not a multiple of 1/2^{t}; exact recovery with probability 1 "
                         f"needs phi * 2^t to be an integer (use phase_estimation for the exact distribution)")
    y0 = scaled.numerator % size
    probability = outcome_probability(phi, t, y0)
    if probability != 1:
        raise ArithmeticError(f"P({y0}) = {probability!r}, expected exactly 1")
    return PhaseRecovery(outcome=y0, phase=Fraction(y0, size), probability=probability.to_rational())


def multiply_by_generator_eigenphases(p: int, g: int) -> tuple[Fraction, ...]:
    """Eigenphases k/(p-1) of U|x> = |g x mod p> on F_p^*, each eigen-relation checked exactly.

    With m = p - 1 and x = g^e, the vector u_k with entries zeta_m^(-k e) satisfies
    U u_k = zeta_m^k u_k; entries are tracked by their exponents modulo m.
    """
    if not isinstance(p, int) or isinstance(p, bool) or not is_prime(p):
        raise ValueError(f"p must be a prime, got {p!r}")
    if not isinstance(g, int) or isinstance(g, bool) or not 1 <= g < p:
        raise ValueError(f"g must lie in 1 .. {p - 1}")
    m = p - 1
    order = multiplicative_order(g, p)
    if order != m:
        raise ValueError(f"{g} has multiplicative order {order} modulo {p}, not {m}; it does not generate F_{p}^*")
    log = [0] * p
    value = 1
    for e in range(m):
        log[value] = e
        value = value * g % p
    phases = []
    for k in range(m):
        for x in range(1, p):
            image = g * x % p
            if (-k * log[x] - (k - k * log[image])) % m:
                raise ArithmeticError(f"eigen-relation fails for k = {k} at x = {x}")
        phases.append(Fraction(k, m))
    return tuple(phases)


@dataclass(frozen=True)
class MultiplyByGeneratorEstimation:
    prime: int
    generator: int
    generator_order: int
    precision_qubits: int
    recoveries: tuple[PhaseRecovery, ...]


def estimate_multiply_by_generator(p: int = 257, g: int = 3) -> MultiplyByGeneratorEstimation:
    """Phase estimation for every eigenphase of multiplication by g on F_p^*.

    The register size t is computed from p - 1 = 2^t; it must be a power of two
    (a Fermat prime p) for every eigenphase to be recovered with probability 1.
    """
    phases = multiply_by_generator_eigenphases(p, g)
    m = p - 1
    t = m.bit_length() - 1
    if 1 << t != m:
        raise ValueError(f"p - 1 = {m} is not a power of two; the eigenphases k/{m} are not dyadic")
    recoveries = []
    for k, phase in enumerate(phases):
        recovery = recover_phase(phase, t)
        if recovery.outcome != k:
            raise ArithmeticError(f"eigenphase {phase} recovered as {recovery.outcome}")
        recoveries.append(recovery)
    return MultiplyByGeneratorEstimation(prime=p, generator=g, generator_order=multiplicative_order(g, p),
                                         precision_qubits=t, recoveries=tuple(recoveries))
