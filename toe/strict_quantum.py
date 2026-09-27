"""Strict quantum-mathematical control plane for TOE and PYTHIA.

This module is deliberately smaller than the research stack and has one hard
boundary: every scalar is exact ``Fraction`` arithmetic over Q(i). There is no
random sampling, floating-point normalization, heuristic score, or simulated
hardware claim.

The module prepares an exact finite-dimensional state and applies an exactly
unitary rational rotation. Its output is a certificate for a mining work
window. It does *not* replace Bitcoin SHA-256d or declare a share valid.
Consensus remains the independent SHA-256d target check.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any


@dataclass(frozen=True)
class QComplex:
    """Exact complex number in Q(i)."""

    re: Fraction = Fraction(0)
    im: Fraction = Fraction(0)

    def __add__(self, other: "QComplex") -> "QComplex":
        return QComplex(self.re + other.re, self.im + other.im)

    def __sub__(self, other: "QComplex") -> "QComplex":
        return QComplex(self.re - other.re, self.im - other.im)

    def __mul__(self, other: "QComplex | Fraction | int") -> "QComplex":
        if isinstance(other, (Fraction, int)):
            return QComplex(self.re * other, self.im * other)
        return QComplex(
            self.re * other.re - self.im * other.im,
            self.re * other.im + self.im * other.re,
        )

    def conjugate(self) -> "QComplex":
        return QComplex(self.re, -self.im)

    def norm_sq(self) -> Fraction:
        return self.re * self.re + self.im * self.im


@dataclass(frozen=True)
class QMatrix:
    """Small exact complex matrix over Q(i)."""

    rows: tuple[tuple[QComplex, ...], ...]

    def __post_init__(self) -> None:
        if not self.rows or any(len(row) != len(self.rows) for row in self.rows):
            raise ValueError("strict quantum matrix must be non-empty and square")

    @property
    def dimension(self) -> int:
        return len(self.rows)

    def dagger(self) -> "QMatrix":
        return QMatrix(
            tuple(
                tuple(self.rows[c][r].conjugate() for c in range(self.dimension))
                for r in range(self.dimension)
            )
        )

    def multiply(self, other: "QMatrix") -> "QMatrix":
        if self.dimension != other.dimension:
            raise ValueError("strict quantum matrix dimensions differ")
        n = self.dimension
        return QMatrix(
            tuple(
                tuple(
                    sum((self.rows[r][k] * other.rows[k][c] for k in range(n)), QComplex())
                    for c in range(n)
                )
                for r in range(n)
            )
        )

    def apply(self, state: "QState") -> "QState":
        if self.dimension != len(state.amplitudes):
            raise ValueError("unitary/state dimensions differ")
        return QState(
            tuple(
                sum((self.rows[r][c] * state.amplitudes[c] for c in range(self.dimension)), QComplex())
                for r in range(self.dimension)
            )
        )

    def unitary_error(self) -> Fraction:
        """Exact max absolute entry error of U†U-I."""
        product = self.dagger().multiply(self)
        zero = Fraction(0)
        errors = []
        for r in range(self.dimension):
            for c in range(self.dimension):
                expected = QComplex(Fraction(int(r == c)), zero)
                delta = product.rows[r][c] - expected
                # Q(i) has no ordering; squared modulus is exact.
                errors.append(delta.norm_sq())
        return max(errors)


@dataclass(frozen=True)
class QState:
    """Exact, possibly unnormalised state; Born probabilities are ratios."""

    amplitudes: tuple[QComplex, ...]

    @property
    def norm_sq(self) -> Fraction:
        return sum((amp.norm_sq() for amp in self.amplitudes), Fraction(0))

    def born_probabilities(self) -> tuple[Fraction, ...]:
        denominator = self.norm_sq
        if denominator == 0:
            raise ValueError("null state has no Born distribution")
        return tuple(amp.norm_sq() / denominator for amp in self.amplitudes)

    def apply(self, unitary: QMatrix) -> "QState":
        return unitary.apply(self)

    def maximum_likelihood_basis(self) -> tuple[int, Fraction]:
        probabilities = self.born_probabilities()
        index = max(range(len(probabilities)), key=lambda i: (probabilities[i], -i))
        return index, probabilities[index]


def rational_rotation() -> QMatrix:
    """Exact SO(2)⊂U(2) rotation from the 3-4-5 Pythagorean triple."""
    a, b = Fraction(3, 5), Fraction(4, 5)
    return QMatrix(((QComplex(a), QComplex(-b)), (QComplex(b), QComplex(a))))


def _chunk_sums(payload: bytes, dimension: int) -> tuple[int, ...]:
    if not payload:
        raise ValueError("strict quantum payload is empty")
    if dimension < 2:
        raise ValueError("strict quantum dimension must be at least 2")
    width = (len(payload) + dimension - 1) // dimension
    values = [sum(payload[i : i + width]) for i in range(0, len(payload), width)]
    values.extend([0] * (dimension - len(values)))
    return tuple(values[:dimension])


def state_from_bytes(payload: bytes, dimension: int = 2) -> QState:
    """Deterministically encode bytes as exact integer amplitudes."""
    values = _chunk_sums(payload, dimension)
    return QState(tuple(QComplex(Fraction(value)) for value in values))


def _fraction_pair(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def certify_work_window(header76: bytes, nonce_start: int, nonce_count: int) -> dict[str, Any]:
    """Create a strict mathematical certificate for one nonce work window."""
    if len(header76) != 76:
        raise ValueError("strict quantum work certificate requires a 76-byte header prefix")
    if not 0 <= nonce_start < 1 << 32:
        raise ValueError("nonce_start must be a uint32")
    if not 1 <= nonce_count <= 1 << 32:
        raise ValueError("nonce_count must be in 1..2^32")
    payload = header76 + nonce_start.to_bytes(4, "little")
    initial = state_from_bytes(payload, dimension=2)
    unitary = rational_rotation()
    evolved = initial.apply(unitary)
    probabilities = evolved.born_probabilities()
    selected, selected_probability = evolved.maximum_likelihood_basis()
    if unitary.unitary_error() != 0:
        raise ValueError("exact unitary certificate failed")
    if evolved.norm_sq != initial.norm_sq:
        raise ValueError("exact unitary evolution changed state norm")
    return {
        "mode": "strict_quantum_q_i",
        "dimension": 2,
        "field": "Q(i)",
        "unitary": [
            [
                {
                    "re": cell.re.numerator,
                    "re_den": cell.re.denominator,
                    "im": cell.im.numerator,
                    "im_den": cell.im.denominator,
                }
                for cell in row
            ]
            for row in unitary.rows
        ],
        "unitary_error_sq": _fraction_pair(unitary.unitary_error()),
        "initial_norm_sq": _fraction_pair(initial.norm_sq),
        "evolved_norm_sq": _fraction_pair(evolved.norm_sq),
        "born_probabilities": [_fraction_pair(p) for p in probabilities],
        "selected_basis": selected,
        "selected_probability": _fraction_pair(selected_probability),
        "nonce_start": nonce_start,
        "nonce_count": nonce_count,
        "nonce_end_exclusive": nonce_start + nonce_count,
        "consensus_authority": False,
        "theorem_proven": False,
        "consensus_rule": "sha256d(header80)[::-1] <= negotiated_target",
    }


def verify_certificate(certificate: dict[str, Any]) -> bool:
    """Fail-closed verification of the public certificate invariants."""
    return (
        certificate.get("mode") == "strict_quantum_q_i"
        and certificate.get("field") == "Q(i)"
        and certificate.get("consensus_authority") is False
        and certificate.get("theorem_proven") is False
        and certificate.get("unitary_error_sq") == {"numerator": 0, "denominator": 1}
        and certificate.get("initial_norm_sq") == certificate.get("evolved_norm_sq")
        and certificate.get("nonce_count", 0) >= 1
        and certificate.get("nonce_end_exclusive") == certificate.get("nonce_start") + certificate.get("nonce_count")
    )


__all__ = [
    "QComplex",
    "QMatrix",
    "QState",
    "rational_rotation",
    "state_from_bytes",
    "certify_work_window",
    "verify_certificate",
]
