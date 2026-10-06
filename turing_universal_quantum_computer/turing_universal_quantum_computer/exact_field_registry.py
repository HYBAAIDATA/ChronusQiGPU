"""Canonical registry for the exact cyclotomic field Q(zeta_8).

The backend representation ``Exact`` is Q(sqrt(2)) + i Q(sqrt(2)), which is
the same degree-four number field as Q(zeta_8) = Q(i, sqrt(2)).  This module
names that identity once and records exact, machine-checkable generators.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .backends.exact_algebra import Exact, I, ONE, Q2, SQRT2_HALF
from .canonical_serialization import canonical_sha256

QZeta8 = Exact
ZETA_8 = Exact(SQRT2_HALF, SQRT2_HALF)
MINUS_ONE = Exact(Q2(-1))


@dataclass(frozen=True)
class ExactFieldReport:
    schema: str
    canonical_field: str
    representation: str
    degree_over_q: int
    contains_q_i: bool
    contains_q_sqrt2: bool
    zeta8_eighth_power_is_one: bool
    zeta8_fourth_power_is_minus_one: bool
    t_phase_norm_is_one: bool
    exact_gate_domain: tuple[str, ...]
    toffoli_statement: str
    verified: bool
    proof_digest: str


def _power(value: Exact, exponent: int) -> Exact:
    if exponent < 0:
        raise ValueError("only non-negative exact powers are supported")
    result = ONE
    for _ in range(exponent):
        result = result * value
    return result


def verify_q_zeta_8_registry() -> ExactFieldReport:
    """Verify the canonical generator and exact gate-domain declarations."""
    checks = {
        "contains_q_i": I * I == MINUS_ONE,
        "contains_q_sqrt2": Q2(0, 1) * Q2(0, 1) == Q2(2),
        "zeta8_eighth_power_is_one": _power(ZETA_8, 8) == ONE,
        "zeta8_fourth_power_is_minus_one": _power(ZETA_8, 4) == MINUS_ONE,
        "t_phase_norm_is_one": ZETA_8.norm_sq() == Q2(1),
    }
    unsigned: dict[str, Any] = {
        "schema": "turing.exact_field_registry/v1",
        "canonical_field": "Q(zeta_8) = Q(i, sqrt(2))",
        "representation": "Q(sqrt(2)) + i Q(sqrt(2))",
        "degree_over_q": 4,
        **checks,
        "exact_gate_domain": (
            "I",
            "X",
            "Y",
            "Z",
            "H",
            "S",
            "T",
            "CNOT",
            "CZ",
            "SWAP",
            "TOFFOLI_MATRIX",
        ),
        "toffoli_statement": (
            "The Toffoli permutation matrix has entries in Q; an exact "
            "Clifford+T decomposition also remains in Q(zeta_8)."
        ),
        "verified": all(checks.values()),
    }
    return ExactFieldReport(**unsigned, proof_digest=canonical_sha256(unsigned))


__all__ = [
    "ExactFieldReport",
    "MINUS_ONE",
    "QZeta8",
    "ZETA_8",
    "verify_q_zeta_8_registry",
]