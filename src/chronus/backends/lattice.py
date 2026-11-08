"""Exact Z[phi] lattice arithmetic and fail-closed verification primitives."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Protocol, Sequence


class HardwareUnavailableError(RuntimeError):
    """A requested physical device or its driver is unavailable."""


class LatticeOverflowError(OverflowError):
    """A fixed-width accelerator path cannot represent the exact calculation."""


class ParityVerificationError(RuntimeError):
    """Device output differs from the exact mathematical reference."""


@dataclass(frozen=True)
class PhiElement:
    """An element (a + b*phi) / denominator with integer coefficients."""

    a: int
    b: int
    denominator: int = 1

    def __post_init__(self):
        if any(
            not isinstance(value, int) or isinstance(value, bool)
            for value in (self.a, self.b, self.denominator)
        ):
            raise TypeError("lattice coefficients must be integers")
        if self.denominator <= 0:
            raise ValueError("denominator must be positive")

    @classmethod
    def from_q5(cls, rational: Fraction, sqrt5: Fraction) -> "PhiElement":
        """Convert r + s*sqrt(5) to (a + b*phi)/denominator exactly."""
        a = rational - sqrt5
        b = 2 * sqrt5
        from math import lcm

        denominator = lcm(a.denominator, b.denominator)
        return cls(
            a.numerator * (denominator // a.denominator),
            b.numerator * (denominator // b.denominator),
            denominator,
        )

    def multiply(self, other: "PhiElement") -> "PhiElement":
        return PhiElement(
            self.a * other.a + self.b * other.b,
            self.a * other.b + self.b * other.a + self.b * other.b,
            self.denominator * other.denominator,
        )

    def trace(self) -> Fraction:
        return Fraction(2 * self.a + self.b, self.denominator)

    def norm(self) -> Fraction:
        return Fraction(
            self.a * self.a + self.a * self.b - self.b * self.b,
            self.denominator * self.denominator,
        )


def phi_power(order: int) -> PhiElement:
    if not isinstance(order, int) or isinstance(order, bool) or order < 0:
        raise ValueError("order must be a non-negative integer")
    result, base = PhiElement(1, 0), PhiElement(0, 1)
    while order:
        if order & 1:
            result = result.multiply(base)
        order >>= 1
        if order:
            base = base.multiply(base)
    return result


def verify_fold(
    inputs: Sequence[PhiElement], outputs: Sequence[PhiElement], order: int
) -> None:
    """Compare every output against the exact reference; do not rely on checksums."""
    if len(inputs) != len(outputs):
        raise ParityVerificationError("output length differs from input length")
    factor = phi_power(order)
    for index, (source, output) in enumerate(zip(inputs, outputs)):
        expected = source.multiply(factor)
        if Fraction(expected.a, expected.denominator) != Fraction(
            output.a, output.denominator
        ) or Fraction(expected.b, expected.denominator) != Fraction(
            output.b, output.denominator
        ):
            raise ParityVerificationError(
                f"exact lattice parity failed at index {index}"
            )


class PhysicalAcceleratorAdapter(Protocol):
    """A physical backend must report device evidence and verify exact outputs."""

    @property
    def backend_id(self) -> str: ...

    def probe_silicon(self) -> dict: ...

    def dispatch_pv_fold(
        self, values: list[PhiElement], order: int
    ) -> tuple[list[PhiElement], dict]: ...
