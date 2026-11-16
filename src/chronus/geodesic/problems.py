"""Small bounded, exact search problems for cross-domain experiments.

SAT, discrete Ising Hamiltonians and rational quadratic loss landscapes
are implemented without oracle shortcuts. They expose the same finite
energy/candidate protocol to a geometry-order benchmark. This does NOT
implement lattice QCD, arbitrary neural optimisation or a quantum solver.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Protocol


class FiniteProblem(Protocol):
    @property
    def domain_size(self) -> int: ...
    def objective(self, candidate: int) -> Fraction: ...
    def describe(self) -> dict[str, object]: ...


def _candidate(candidate: int, size: int) -> None:
    if type(candidate) is not int or not 0 <= candidate < size:
        raise ValueError("candidate outside finite search domain")


@dataclass(frozen=True)
class SATProblem:
    """Finite CNF; objective is exact integer number of unsatisfied clauses."""
    variable_count: int
    clauses: tuple[tuple[int, ...], ...]

    def __post_init__(self):
        if type(self.variable_count) is not int or not 1 <= self.variable_count <= 12:
            raise ValueError("SAT supports 1..12 Boolean variables")
        if not self.clauses or any(not clause for clause in self.clauses):
            raise ValueError("at least one nonempty clause required")
        if any(type(lit) is not int or lit == 0 or abs(lit) > self.variable_count
               for clause in self.clauses for lit in clause):
            raise ValueError("literals must be nonzero signed variable indices")

    @property
    def domain_size(self) -> int:
        return 1 << self.variable_count

    def objective(self, candidate: int) -> Fraction:
        _candidate(candidate, self.domain_size)
        def true_literal(literal: int) -> bool:
            bit = bool(candidate & (1 << (abs(literal) - 1)))
            return bit if literal > 0 else not bit
        return Fraction(sum(not any(true_literal(v) for v in clause)
                            for clause in self.clauses))

    def describe(self) -> dict[str, object]:
        return {"type":"SAT_CNF", "variable_count":self.variable_count,
                "clauses":[list(c) for c in self.clauses],
                "classification":"EXACT_BOUNDED_FINITE_PROBLEM"}


@dataclass(frozen=True)
class IsingProblem:
    """Exact finite Ising energy E(s) = sum J_ij*s_i*s_j + sum h_i*s_i."""
    spin_count: int
    couplings: tuple[tuple[int, int, Fraction], ...]
    fields: tuple[Fraction, ...] = ()

    def __post_init__(self):
        if type(self.spin_count) is not int or not 1 <= self.spin_count <= 12:
            raise ValueError("Ising supports 1..12 spins")
        object.__setattr__(self, "fields", tuple(Fraction(v) for v in self.fields))
        object.__setattr__(self, "couplings", tuple(
            (i,j,Fraction(weight)) for i,j,weight in self.couplings))
        if self.fields and len(self.fields) != self.spin_count:
            raise ValueError("field count must equal spin count")
        for i,j,w in self.couplings:
            if (type(i) is not int or type(j) is not int or i == j or
                    not 0 <= i < self.spin_count or not 0 <= j < self.spin_count):
                raise ValueError("invalid Ising coupling")

    @property
    def domain_size(self) -> int:
        return 1 << self.spin_count

    def objective(self, candidate: int) -> Fraction:
        _candidate(candidate, self.domain_size)
        spins = tuple(1 if candidate & (1 << i) else -1
                      for i in range(self.spin_count))
        return (sum((w*spins[i]*spins[j] for i,j,w in self.couplings),
                    Fraction(0)) +
                sum((h*s for h,s in zip(self.fields, spins)), Fraction(0)))

    def describe(self) -> dict[str, object]:
        return {"type":"ISING_DISCRETE", "spin_count":self.spin_count,
                "couplings":[[i,j,str(w)] for i,j,w in self.couplings],
                "fields":[str(h) for h in self.fields],
                "classification":"EXACT_FINITE_LATTICE_NOT_QCD"}


@dataclass(frozen=True)
class QuadraticLandscape:
    """Discrete linear least-squares objective over a bounded binary domain."""
    dimension: int
    matrix: tuple[tuple[Fraction, ...], ...]
    targets: tuple[Fraction, ...]

    def __post_init__(self):
        if type(self.dimension) is not int or not 1 <= self.dimension <= 12:
            raise ValueError("landscape dimension must be 1..12")
        object.__setattr__(self, "matrix", tuple(
            tuple(Fraction(x) for x in row) for row in self.matrix))
        object.__setattr__(self, "targets", tuple(Fraction(x) for x in self.targets))
        if not self.matrix or len(self.matrix) != len(self.targets) or any(
                len(row) != self.dimension for row in self.matrix):
            raise ValueError("matrix and target shapes mismatch")

    @property
    def domain_size(self) -> int:
        return 1 << self.dimension

    def objective(self, candidate: int) -> Fraction:
        _candidate(candidate, self.domain_size)
        bits = tuple(int(bool(candidate & (1 << i)))
                     for i in range(self.dimension))
        return sum(((
            sum((weight*bits[i] for i,weight in enumerate(row)), Fraction(0)) -
            target) ** 2 for row,target in zip(self.matrix,self.targets)), Fraction(0))

    def describe(self) -> dict[str, object]:
        return {"type":"RATIONAL_QUADRATIC_LANDSCAPE",
                "dimension":self.dimension,
                "matrix":[[str(x) for x in row] for row in self.matrix],
                "targets":[str(x) for x in self.targets],
                "classification":"EXACT_DISCRETE_LOSS_NOT_CONTINUOUS_NEURAL_NETWORK"}
