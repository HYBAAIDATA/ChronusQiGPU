"""Exact symbolic thermodynamic obligations for hash-computation boundaries.

No decimal estimate is produced.  The Landauer term remains the symbolic
quantity ``bits_erased * k_B * T * ln(2)`` because ``ln(2)`` is irrational and
the temperature and device parameters require physical measurement.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from turing_universal_quantum_computer.canonical_serialization import canonical_sha256


@dataclass(frozen=True)
class LandauerExpression:
    bits_erased: int
    temperature_kelvin: Fraction

    def __post_init__(self) -> None:
        if self.bits_erased < 0:
            raise ValueError("bits_erased must be non-negative")
        temperature = Fraction(self.temperature_kelvin)
        if temperature <= 0:
            raise ValueError("temperature_kelvin must be positive")
        object.__setattr__(self, "temperature_kelvin", temperature)

    @property
    def coefficient_of_kb_ln2_joules(self) -> Fraction:
        return self.bits_erased * self.temperature_kelvin

    def as_dict(self) -> dict:
        return {
            "expression": "bits_erased * k_B * temperature_kelvin * ln(2)",
            "bits_erased": self.bits_erased,
            "temperature_kelvin": {
                "$rational": {
                    "numerator": self.temperature_kelvin.numerator,
                    "denominator": self.temperature_kelvin.denominator,
                }
            },
            "coefficient_of_kb_ln2_joules": {
                "$rational": {
                    "numerator": self.coefficient_of_kb_ln2_joules.numerator,
                    "denominator": self.coefficient_of_kb_ln2_joules.denominator,
                }
            },
            "numerical_value_asserted": False,
        }


@dataclass(frozen=True)
class ThermodynamicBoundaryReport:
    sha256d_output_many_to_one: bool
    reversible_embedding_possible: bool
    end_to_end_reset_obligations_remain: bool
    landauer_applies_per_erased_bit: bool
    pure_math_energy_claim: bool
    statement: str
    proof_digest: str


def thermodynamic_boundary_report() -> ThermodynamicBoundaryReport:
    unsigned = {
        "sha256d_output_many_to_one": True,
        "reversible_embedding_possible": True,
        "end_to_end_reset_obligations_remain": True,
        "landauer_applies_per_erased_bit": True,
        "pure_math_energy_claim": False,
        "statement": (
            "A SHA-256d input-to-digest map is many-to-one. Its classical "
            "circuit may be reversibly embedded with retained ancilla, but "
            "state preparation, reset, comparison, and I/O boundaries must "
            "account for every erased bit. Exact mathematics alone certifies "
            "no physical energy."
        ),
    }
    return ThermodynamicBoundaryReport(
        **unsigned,
        proof_digest=canonical_sha256(unsigned),
    )


__all__ = [
    "LandauerExpression",
    "ThermodynamicBoundaryReport",
    "thermodynamic_boundary_report",
]
