"""Finite exact tensor Hilbert mathematics owned by TURING.

This module uses a sparse C^n basis with Gaussian-rational amplitudes.
It never assumes a complex state on a smooth manifold. No dense allocation
is required for the 32 x 600 tensor basis. Exact evolution is supported
for involutory Hermitian generators at rational multiples of pi/2 only:
U(k*pi/2) = cos(k*pi/2) I - i sin(k*pi/2) H.
General matrix exponentiation is explicitly unsupported rather than
approximated or advertised as exact.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class ExactComplex:
    re: Fraction
    im: Fraction = Fraction(0)

    def __post_init__(self):
        object.__setattr__(self, "re", Fraction(self.re))
        object.__setattr__(self, "im", Fraction(self.im))

    @classmethod
    def of(cls, x: "ExactComplex | int | Fraction") -> "ExactComplex":
        return x if isinstance(x, ExactComplex) else cls(x)

    def __add__(self, other: "ExactComplex | int | Fraction") -> "ExactComplex":
        z = ExactComplex.of(other)
        return ExactComplex(self.re + z.re, self.im + z.im)

    __radd__ = __add__

    def __neg__(self) -> "ExactComplex":
        return ExactComplex(-self.re, -self.im)

    def __sub__(self, other: "ExactComplex | int | Fraction") -> "ExactComplex":
        return self + -ExactComplex.of(other)

    def __mul__(self, other: "ExactComplex | int | Fraction") -> "ExactComplex":
        z = ExactComplex.of(other)
        return ExactComplex(self.re*z.re - self.im*z.im,
                            self.re*z.im + self.im*z.re)

    __rmul__ = __mul__

    def conj(self) -> "ExactComplex":
        return ExactComplex(self.re, -self.im)

    def norm2(self) -> Fraction:
        return self.re*self.re + self.im*self.im


I = ExactComplex(0, 1)
ONE = ExactComplex(1)
ZERO = ExactComplex(0)


@dataclass(frozen=True)
class TensorHilbert:
    factors: tuple[int, ...]

    def __post_init__(self):
        object.__setattr__(self, "factors", tuple(self.factors))
        if not self.factors or any(type(n) is not int or n < 1 for n in self.factors):
            raise ValueError("all Hilbert factor dimensions must be positive integers")

    @property
    def dimension(self) -> int:
        from math import prod
        return prod(self.factors)

    def index(self, coordinates: tuple[int, ...]) -> int:
        if len(coordinates) != len(self.factors):
            raise ValueError("wrong tensor rank")
        index = 0
        for i, size in zip(coordinates, self.factors):
            if type(i) is not int or not 0 <= i < size:
                raise ValueError("tensor coordinate outside range")
            index = index * size + i
        return index

    def coordinates(self, index: int) -> tuple[int, ...]:
        if type(index) is not int or not 0 <= index < self.dimension:
            raise ValueError("tensor basis index outside range")
        result = []
        for size in reversed(self.factors):
            index, remainder = divmod(index, size)
            result.append(remainder)
        return tuple(reversed(result))


@dataclass(frozen=True)
class SparseState:
    space: TensorHilbert
    amplitudes: Mapping[int, ExactComplex] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "amplitudes",
                           MappingProxyType(dict(self.amplitudes)))
        for index, value in self.amplitudes.items():
            if type(index) is not int or not 0 <= index < self.space.dimension:
                raise ValueError("amplitude basis index outside range")
            if not isinstance(value, ExactComplex):
                raise TypeError("amplitudes must be exact Gaussian rationals")

    @classmethod
    def basis(cls, space: TensorHilbert, coordinates: tuple[int, ...]) -> "SparseState":
        return cls(space, {space.index(coordinates): ONE})

    def norm2(self) -> Fraction:
        return sum((z.norm2() for z in self.amplitudes.values()), Fraction(0))

    def normalized(self) -> bool:
        return self.norm2() == 1

    def born_distribution(self) -> dict[int, Fraction]:
        if not self.normalized():
            raise ValueError("Born probabilities require exact unit normalization")
        return {k: z.norm2() for k, z in self.amplitudes.items() if z.norm2()}

    def expectation_diagonal(self, values: Mapping[int, Fraction]) -> Fraction:
        if not self.normalized():
            raise ValueError("observable requires normalized state")
        return sum((z.norm2()*Fraction(values.get(k, 0))
                    for k, z in self.amplitudes.items()), Fraction(0))


@dataclass(frozen=True)
class SignedInvolution:
    """H|i> = sign(i) |permutation(i)> with H*=H and H^2=I.

    Sparse map entries override the identity; all unspecified entries map
    to themselves with +1. The map is verified on the complete finite basis.
    """
    space: TensorHilbert
    images: Mapping[int, tuple[int, int]]

    def __post_init__(self):
        object.__setattr__(self, "images",
                           MappingProxyType({
                               src: tuple(pair) for src, pair in self.images.items()
                           }))
        for src, (dst, sign) in self.images.items():
            if not (type(src) is int and type(dst) is int and
                    0 <= src < self.space.dimension and
                    0 <= dst < self.space.dimension and type(sign) is int and
                    sign in (-1, 1)):
                raise ValueError("invalid signed involution entry")
            back = self.images.get(dst, (dst, 1))
            if back != (src, sign):
                raise ValueError("Hermitian involution must reverse with the same sign")

    def apply(self, state: SparseState) -> SparseState:
        if state.space != self.space:
            raise ValueError("space mismatch")
        out: dict[int, ExactComplex] = {}
        for src, z in state.amplitudes.items():
            dst, sign = self.images.get(src, (src, 1))
            out[dst] = out.get(dst, ZERO) + sign*z
        return SparseState(self.space, {i: z for i, z in out.items() if z != ZERO})

    def quarter_turn(self, state: SparseState, steps: int = 1) -> SparseState:
        """Exactly exp(-i*pi*steps/2 H) with NO truncation or float."""
        if type(steps) is not int:
            raise TypeError("steps must be integer")
        if not isinstance(state, SparseState) or state.space != self.space:
            raise ValueError("space mismatch")
        phase = steps % 4
        if phase == 0:
            return state
        if phase == 2:
            return SparseState(state.space, {k: -z for k, z in state.amplitudes.items()})
        rotated = self.apply(state)
        scalar = -I if phase == 1 else I
        return SparseState(rotated.space,
                           {k: scalar*z for k, z in rotated.amplitudes.items()})

    def transition_probability(self, state: SparseState,
                               target: int, steps: int = 1) -> Fraction:
        result = self.quarter_turn(state, steps)
        if not result.normalized():
            raise ValueError("input is not a normalized quantum state")
        if type(target) is not int or not 0 <= target < self.space.dimension:
            raise ValueError("target outside basis")
        return result.amplitudes.get(target, ZERO).norm2()


def phase_injection(state: SparseState,
                    phases: Mapping[int, ExactComplex]) -> SparseState:
    """Apply an exactly unit-modulus diagonal phase and verify it."""
    # Validate EVERY supplied phase, including unoccupied indices, before
    # any output is constructed; an absent amplitude does not waive gates.
    for idx, phase in phases.items():
        if type(idx) is not int or not 0 <= idx < state.space.dimension:
            raise ValueError("phase index outside finite Hilbert space")
        if not isinstance(phase, ExactComplex) or phase.norm2() != 1:
            raise ValueError("phase must have exact unit norm")
    out: dict[int, ExactComplex] = {}
    for idx, z in state.amplitudes.items():
        out[idx] = phases.get(idx, ONE) * z
    return SparseState(state.space, out)
